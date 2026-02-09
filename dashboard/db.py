"""
Dashboard MySQL connection: read from admins table (same DB as main app).
"""
from contextlib import contextmanager
from typing import Optional

import pymysql

from dashboard.config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
)


@contextmanager
def get_connection():
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_admin_by_email(email: str) -> Optional[dict]:
    """Get admin by email (includes password_hash for verification)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, password_hash, created_at FROM admins WHERE email = %s",
                    (email.strip().lower(),),
                )
                return cur.fetchone()
    except Exception:
        return None
