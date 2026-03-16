"""
UK Property Market Copilot – FastAPI web application.

Routes:
  GET  /               → redirect to /chat
  GET  /login          → login page
  POST /login          → authenticate
  GET  /register       → register page
  POST /register       → create account
  GET  /logout         → clear session
  GET  /chat           → chat UI
  POST /chat/message   → send message, get AI reply
  GET  /dashboard      → analytics dashboard
  GET  /records        → property records explorer
  POST /feedback       → submit answer feedback
  GET  /health         → Railway health check
"""

import json
import os
import uuid
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Form, Request, Response, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature

from .auth import authenticate_user, register_user, google_sso_enabled, GOOGLE_CLIENT_ID, verify_google_token, get_or_create_google_user
from .copilot import chat as copilot_chat
from .db import DB_PATH, get_db, query

AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me")

if not AUTH_SECRET:
    if os.getenv("DEBUG", "false").lower() == "true":
        AUTH_SECRET = "dev-only-insecure-secret"
        print("WARNING: AUTH_SECRET not set. Using insecure default for development only.")
    else:
        print("ERROR: AUTH_SECRET is required in production.", file=sys.stderr)
        sys.exit(1)

COOKIE_NAME = "uk_prop_session"
SIGNER = URLSafeTimedSerializer(AUTH_SECRET)

app = FastAPI(title="UK Property Market Copilot")

# Static files & templates
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "web/static")), name="static")
app.mount("/assets", StaticFiles(directory=os.path.join(BASE_DIR, "web/assets")), name="assets")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "web"))

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# add directly below it:
CHAT_RATE_MINUTE = os.getenv("CHAT_RATE_MINUTE", "10/minute")
CHAT_RATE_DAY = os.getenv("CHAT_RATE_DAY", "100/day")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Session helpers ──────────────────────────────────────────────────────────

def set_session(response: Response, username: str):
    token = SIGNER.dumps({"u": username})
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=86400 * 7)


def get_session(request: Request) -> Optional[str]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = SIGNER.loads(token, max_age=86400 * 7)
        return data.get("u")
    except BadSignature:
        return None


def require_login(request: Request) -> Optional[str]:
    username = get_session(request)
    if not username:
        return None
    return username


# ── DB helpers ───────────────────────────────────────────────────────────────

def save_session_messages(session_id: str, username: str, messages: list, db_path: str = DB_PATH):
    con = get_db(db_path)
    con.execute(
        """INSERT INTO copilot_sessions (session_id, username, messages)
           VALUES (?, ?, ?)
           ON CONFLICT(session_id) DO UPDATE SET messages=excluded.messages""",
        (session_id, username, json.dumps(messages)),
    )
    con.commit()
    con.close()


def load_session_messages(session_id: str, db_path: str = DB_PATH) -> list:
    con = get_db(db_path)
    row = con.execute(
        "SELECT messages FROM copilot_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    con.close()
    return json.loads(row["messages"]) if row else []


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return RedirectResponse("/chat")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "google_sso": google_sso_enabled(),
        "google_client_id": GOOGLE_CLIENT_ID,
    })


@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password.",
            "google_sso": google_sso_enabled(),
            "google_client_id": GOOGLE_CLIENT_ID,
        })
    resp = RedirectResponse("/chat", status_code=303)
    set_session(resp, user)
    return resp


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, error: str = ""):
    return templates.TemplateResponse("register.html", {"request": request, "error": error})


@app.post("/register")
async def register_post(request: Request, username: str = Form(...), password: str = Form(...)):
    ok = register_user(username, password)
    if not ok:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Username already taken. Please choose another.",
        })
    resp = RedirectResponse("/chat", status_code=303)
    set_session(resp, username.strip().lower())
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp

@app.post("/google-login")
async def google_login(request: Request):
    body = await request.json()
    credential = body.get("credential", "")
    if not credential:
        return JSONResponse({"error": "Missing credential"}, status_code=400)

    email = verify_google_token(credential)
    if not email:
        return JSONResponse({"error": "Invalid Google token"}, status_code=401)

    username = get_or_create_google_user(email)
    resp = JSONResponse({"status": "ok"})
    set_session(resp, username)
    return resp


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    username = require_login(request)
    if not username:
        return RedirectResponse("/login")
    session_id = request.cookies.get("chat_session") or str(uuid.uuid4())
    messages = load_session_messages(session_id)
    resp = templates.TemplateResponse("chat.html", {
        "request": request,
        "username": username,
        "session_id": session_id,
        "messages": messages,
    })
    resp.set_cookie("chat_session", session_id, httponly=True, samesite="lax")
    return resp


@app.post("/chat/message")
@limiter.limit(CHAT_RATE_MINUTE)
@limiter.limit(CHAT_RATE_DAY)
async def chat_message(request: Request):
    username = require_login(request)
    if not username:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    body = await request.json()
    question = body.get("question", "").strip()
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not question:
        return JSONResponse({"error": "Empty question"}, status_code=400)

    messages = load_session_messages(session_id)
    messages.append({"role": "user", "content": question})

    reply, updated = copilot_chat(messages)
    save_session_messages(session_id, username, updated)

    return JSONResponse({"reply": reply, "session_id": session_id})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    username = require_login(request)
    if not username:
        return RedirectResponse("/login")

    db = DB_PATH

    # KPIs
    kpis_row = query(
        "SELECT COUNT(*) as total_sales, AVG(price_num) as avg_price, "
        "MIN(sale_year) as from_year, MAX(sale_year) as to_year FROM property_analytics",
        db_path=db,
    )
    kpis = kpis_row[0] if kpis_row else {}

    # Top counties by volume (last 5 years)
    top_counties = query(
        "SELECT county_clean, COUNT(*) as sales, AVG(price_num) as avg_price "
        "FROM property_analytics WHERE sale_year >= '2019' AND county_clean != '' "
        "GROUP BY county_clean ORDER BY sales DESC LIMIT 10",
        db_path=db,
    )

    # Monthly trend (last 36 months)
    monthly_trend = query(
        "SELECT sale_month, COUNT(*) as sales, AVG(price_num) as avg_price "
        "FROM property_analytics WHERE sale_month >= date('now', '-36 months', 'start of month') "
        "GROUP BY sale_month ORDER BY sale_month",
        db_path=db,
    )

    # Property type mix (last year)
    type_mix = query(
        "SELECT property_type_clean, COUNT(*) as cnt "
        "FROM property_analytics WHERE sale_year = strftime('%Y', 'now', '-1 year') "
        "GROUP BY property_type_clean ORDER BY cnt DESC",
        db_path=db,
    )

    # Tenure mix
    tenure_mix = query(
        "SELECT tenure_clean, COUNT(*) as cnt "
        "FROM property_analytics WHERE sale_year = strftime('%Y', 'now', '-1 year') "
        "GROUP BY tenure_clean ORDER BY cnt DESC",
        db_path=db,
    )

    # New build vs established
    new_build = query(
        "SELECT is_new_build, COUNT(*) as cnt, AVG(price_num) as avg_price "
        "FROM property_analytics WHERE sale_year = strftime('%Y', 'now', '-1 year') "
        "GROUP BY is_new_build",
        db_path=db,
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": username,
        "kpis": kpis,
        "top_counties": top_counties,
        "monthly_trend": json.dumps(monthly_trend),
        "type_mix": json.dumps(type_mix),
        "tenure_mix": json.dumps(tenure_mix),
        "new_build": json.dumps(new_build),
    })


@app.get("/records", response_class=HTMLResponse)
def records_page(request: Request, q: str = "", county: str = "", ptype: str = "",
                  tenure: str = "", year_from: str = "", year_to: str = "", page: int = 1):
    username = require_login(request)
    if not username:
        return RedirectResponse("/login")

    PAGE_SIZE = 50
    offset = (page - 1) * PAGE_SIZE

    conditions = ["1=1"]
    params: list = []

    if q:
        conditions.append(
            "(town_clean LIKE ? OR county_clean LIKE ? OR postcode LIKE ? OR street LIKE ?)"
        )
        like = f"%{q.upper()}%"
        params += [like, like, f"%{q.upper()}%", f"%{q.upper()}%"]
    if county:
        conditions.append("county_clean = ?")
        params.append(county.upper())
    if ptype:
        conditions.append("property_type_clean = ?")
        params.append(ptype)
    if tenure:
        conditions.append("tenure_clean = ?")
        params.append(tenure)
    if year_from:
        conditions.append("sale_year >= ?")
        params.append(year_from)
    if year_to:
        conditions.append("sale_year <= ?")
        params.append(year_to)

    where = " AND ".join(conditions)

    records = query(
        f"SELECT transaction_id, price_num, sale_date, postcode, property_type_clean, "
        f"tenure_clean, is_new_build, paon, street, town_clean, county_clean "
        f"FROM property_analytics WHERE {where} "
        f"ORDER BY sale_date DESC LIMIT {PAGE_SIZE} OFFSET {offset}",
        tuple(params),
        db_path=DB_PATH,
    )

    count_rows = query(
        f"SELECT COUNT(*) as cnt FROM property_analytics WHERE {where}",
        tuple(params),
        db_path=DB_PATH,
    )
    total = count_rows[0]["cnt"] if count_rows else 0

    counties = query(
        "SELECT DISTINCT county_clean FROM property_analytics WHERE county_clean != '' "
        "ORDER BY county_clean LIMIT 200",
        db_path=DB_PATH,
    )

    return templates.TemplateResponse("records.html", {
        "request": request,
        "username": username,
        "records": records,
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "pages": (total + PAGE_SIZE - 1) // PAGE_SIZE,
        "q": q, "county": county, "ptype": ptype,
        "tenure": tenure, "year_from": year_from, "year_to": year_to,
        "counties": [r["county_clean"] for r in counties],
    })


@app.post("/feedback")
async def feedback_post(request: Request):
    username = require_login(request)
    if not username:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    con = get_db(DB_PATH)
    con.execute(
        "INSERT INTO copilot_feedback (session_id, username, question, answer, rating, correction) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            body.get("session_id", ""),
            username,
            body.get("question", ""),
            body.get("answer", ""),
            body.get("rating", ""),
            body.get("correction", ""),
        ),
    )
    con.commit()
    con.close()
    return JSONResponse({"status": "ok"})
