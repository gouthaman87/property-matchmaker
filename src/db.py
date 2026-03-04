"""Database connection and helper utilities."""

import os
import sqlite3
from typing import Any

DB_PATH = os.getenv("DB_PATH", "data/uk_property.db")


def get_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA cache_size=-64000")  # 64 MB cache
    return con


def query(sql: str, params: tuple = (), db_path: str = DB_PATH) -> list[dict]:
    con = get_db(db_path)
    try:
        cur = con.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()


def execute(sql: str, params: tuple = (), db_path: str = DB_PATH) -> int:
    con = get_db(db_path)
    try:
        cur = con.execute(sql, params)
        con.commit()
        return cur.rowcount
    finally:
        con.close()


def schema_summary(db_path: str = DB_PATH) -> str:
    """Return a concise schema description for the AI system prompt."""
    return """
SQLite database: UK residential property transactions (HM Land Registry Price Paid Data).

TABLE: property_records
  transaction_id TEXT PK, price INTEGER (GBP), date_of_transfer TEXT (YYYY-MM-DD HH:MM),
  postcode TEXT, property_type TEXT (D/S/T/F/O), old_new TEXT (Y=new build/N),
  duration TEXT (F=freehold/L=leasehold/U=unknown),
  paon TEXT (house number/name), saon TEXT (flat/unit), street TEXT,
  locality TEXT, town TEXT, district TEXT, county TEXT,
  ppd_category_type TEXT (A=standard/B=additional), record_status TEXT (A/C/D)
  
TABLE: epc_records (joinable to property_analytics on postcode)
  lmk_key TEXT PK, address1, address2, postcode,
  local_authority, property_type, built_form, construction_age_band,
  total_floor_area REAL (m²), habitable_rooms INTEGER,
  tenure, energy_rating TEXT (A-G), lodgement_date TEXT

VIEW: property_analytics  (excludes deleted records, record_status != 'D')
  transaction_id, price_num INTEGER, sale_date TEXT, sale_month TEXT (YYYY-MM), sale_year TEXT,
  postcode, postcode_area TEXT,
  property_type_clean TEXT (Detached/Semi-Detached/Terraced/Flat/Maisonette/Other),
  is_new_build INTEGER (1=yes/0=no),
  tenure_clean TEXT (Freehold/Leasehold/Unknown),
  paon, saon, street, locality,
  town_clean TEXT (uppercase), district_clean TEXT, county_clean TEXT,
  ppd_category_type, record_status

VIRTUAL TABLE: property_fts (FTS5 full-text search on address fields)
  Use: SELECT transaction_id FROM property_fts WHERE property_fts MATCH ?

TABLE: copilot_feedback (id, session_id, username, question, answer, rating, correction, created_at)
TABLE: copilot_sessions (session_id PK, username, created_at, messages JSON)
TABLE: users (id, username, password_hash, created_at)

NOTES:
- England and Wales only (HM Land Registry jurisdiction)
- Data from January 1995 to present
- Prices in GBP (£)
- Always use property_analytics view for user-facing queries (excludes deletions)
- For aggregations use AVG(price_num), COUNT(*), etc.
- county_clean / town_clean are uppercase — use UPPER() or LIKE for matching
""".strip()
