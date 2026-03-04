"""Authentication: local username/password + optional Google SSO."""

import os
import sqlite3
import uuid
from typing import Optional

from passlib.context import CryptContext

from .db import DB_PATH, get_db

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def register_user(username: str, password: str, db_path: str = DB_PATH) -> bool:
    """Create a new user. Returns True on success, False if username taken."""
    con = get_db(db_path)
    try:
        con.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username.strip().lower(), hash_password(password)),
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()


def authenticate_user(username: str, password: str, db_path: str = DB_PATH) -> Optional[str]:
    """Verify credentials. Returns username on success, None on failure."""
    con = get_db(db_path)
    try:
        row = con.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return username.strip().lower()
        return None
    finally:
        con.close()


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


def google_sso_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID)
