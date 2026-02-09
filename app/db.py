"""
MySQL connection and user CRUD. Creates users table if not exists.
"""
import logging
import pymysql
from contextlib import contextmanager
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Set to False if init_db() failed (e.g. MySQL not running or wrong credentials)
db_available = True

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ADMINS_TABLE = """
CREATE TABLE IF NOT EXISTS admins (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_REMINDERS_TABLE = """
CREATE TABLE IF NOT EXISTS reminders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  message VARCHAR(2000) NOT NULL,
  run_at DATETIME NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_run_at_status (run_at, status),
  INDEX idx_user_id (user_id)
);
"""

CREATE_NOTIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS notifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  title VARCHAR(255) NOT NULL DEFAULT '',
  body TEXT NOT NULL,
  source VARCHAR(50) NOT NULL DEFAULT 'reminder',
  audio_path VARCHAR(512) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_created (user_id, created_at)
);
"""

CREATE_DAILY_BRIEFS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_briefs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  brief_date DATE NOT NULL,
  text_content TEXT NOT NULL,
  audio_path VARCHAR(512) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_date (user_id, brief_date),
  INDEX idx_user_date (user_id, brief_date)
);
"""


@contextmanager
def get_connection():
    conn = pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
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


def _ensure_database_exists():
    """Create the database if it does not exist (connect without database first)."""
    # Escape backticks in identifier for safe SQL
    db_name = config.MYSQL_DATABASE.replace("`", "``")
    conn = pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS `%s`" % db_name)
        conn.commit()
    finally:
        conn.close()


def init_db() -> bool:
    """Create database if not exists, then create users and admins tables if not exists. Returns True on success."""
    global db_available
    try:
        _ensure_database_exists()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_USERS_TABLE)
                cur.execute(CREATE_ADMINS_TABLE)
                cur.execute(CREATE_REMINDERS_TABLE)
                cur.execute(CREATE_NOTIFICATIONS_TABLE)
                cur.execute(CREATE_DAILY_BRIEFS_TABLE)
                # Add audio_path to notifications if missing (existing installs)
                try:
                    cur.execute(
                        "SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'notifications' AND COLUMN_NAME = 'audio_path'",
                        (config.MYSQL_DATABASE,),
                    )
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE notifications ADD COLUMN audio_path VARCHAR(512) NULL AFTER source")
                except Exception:
                    pass
        return True
    except Exception as e:
        logger.warning("MySQL init_db failed: %s. Set MYSQL_* in .env and ensure MySQL is running.", e)
        db_available = False
        return False


def seed_default_admin(email: str, password_hash: str) -> None:
    """Insert the default admin if no admin exists. Idempotent."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM admins LIMIT 1")
            if cur.fetchone():
                return
            cur.execute(
                "INSERT INTO admins (email, password_hash) VALUES (%s, %s)",
                (email.strip().lower(), password_hash),
            )


def get_admin_by_email(email: str) -> Optional[dict]:
    """Get admin by email (includes password_hash for verification)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, created_at FROM admins WHERE email = %s",
                (email.strip().lower(),),
            )
            return cur.fetchone()


def create_user(email: str, password_hash: str, name: str = "") -> int:
    """Insert user; returns id. Raises on duplicate email."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s)",
                (email.strip().lower(), password_hash, (name or "").strip()[:255]),
            )
            return cur.lastrowid


def update_user_password(email: str, password_hash: str) -> bool:
    """Update password_hash for a user by email. Returns True if a row was updated."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (password_hash, email.strip().lower()),
            )
            return cur.rowcount > 0


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by id (no password_hash in safe usage)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, name, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()


def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email (includes password_hash for verification)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, name, created_at FROM users WHERE email = %s",
                (email.strip().lower(),),
            )
            return cur.fetchone()


# ----- Reminders -----


def create_reminder(user_id: int, message: str, run_at) -> int:
    """Insert reminder. run_at: datetime. Returns id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reminders (user_id, message, run_at, status) VALUES (%s, %s, %s, 'pending')",
                (user_id, (message or "").strip()[:2000], run_at),
            )
            return cur.lastrowid


def get_due_reminders():
    """Return list of reminders where run_at <= UTC_TIMESTAMP() and status = 'pending' (run_at stored in UTC)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, message, run_at, created_at FROM reminders WHERE status = 'pending' AND run_at <= UTC_TIMESTAMP() ORDER BY run_at"
            )
            return cur.fetchall()


def mark_reminder_sent(reminder_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE reminders SET status = 'sent' WHERE id = %s", (reminder_id,))
            return cur.rowcount > 0


def mark_reminder_failed(reminder_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE reminders SET status = 'failed' WHERE id = %s", (reminder_id,))
            return cur.rowcount > 0


def get_reminders_for_user(user_id: int, limit: int = 50, offset: int = 0):
    """List reminders for user (all statuses). Returns (list of dicts, total)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM reminders WHERE user_id = %s",
                (user_id,),
            )
            total = (cur.fetchone() or {}).get("total", 0)
            cur.execute(
                "SELECT id, user_id, message, run_at, status, created_at FROM reminders WHERE user_id = %s ORDER BY run_at DESC LIMIT %s OFFSET %s",
                (user_id, limit, offset),
            )
            return cur.fetchall(), total


def get_upcoming_reminders_for_user(user_id: int, limit: int = 20):
    """Reminders for user that are pending and run_at is in the future (UTC). Order by run_at ASC."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, message, run_at, status, created_at FROM reminders
                   WHERE user_id = %s AND status = 'pending' AND run_at > UTC_TIMESTAMP()
                   ORDER BY run_at ASC LIMIT %s""",
                (user_id, limit),
            )
            return cur.fetchall()


def get_sent_reminders_today_for_user(user_id: int):
    """Reminders for user that were sent today (run_at date is today UTC). Order by run_at."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, message, run_at, status, created_at FROM reminders
                   WHERE user_id = %s AND status = 'sent'
                   AND run_at >= UTC_DATE() AND run_at < UTC_DATE() + INTERVAL 1 DAY
                   ORDER BY run_at ASC""",
                (user_id,),
            )
            return cur.fetchall()


# ----- Notifications (in-dashboard alerts) -----


def create_notification(user_id: Optional[int], title: str, body: str, source: str = "reminder", audio_path: Optional[str] = None) -> int:
    """Insert notification for dashboard alerts. user_id can be None for global. Returns id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notifications (user_id, title, body, source, audio_path) VALUES (%s, %s, %s, %s, %s)",
                (user_id, (title or "")[:255], body or "", (source or "reminder")[:50], (audio_path or "")[:512] or None),
            )
            return cur.lastrowid


def update_notification_audio(notification_id: int, audio_path: str) -> bool:
    """Set audio_path for an existing notification."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notifications SET audio_path = %s WHERE id = %s",
                ((audio_path or "")[:512], notification_id),
            )
            return cur.rowcount > 0


def get_notification_by_id(notification_id: int) -> Optional[dict]:
    """Get a single notification by id (no user check; use get_notification_for_user for scoped access)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, title, body, source, audio_path, created_at FROM notifications WHERE id = %s",
                (notification_id,),
            )
            return cur.fetchone()


def get_notification_for_user(notification_id: int, user_id: int) -> Optional[dict]:
    """Get a notification by id only if it belongs to this user or is global (user_id IS NULL). Returns None otherwise."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, title, body, source, audio_path, created_at FROM notifications
                   WHERE id = %s AND (user_id = %s OR user_id IS NULL)""",
                (notification_id, user_id),
            )
            return cur.fetchone()


def get_notifications_for_user(user_id: Optional[int], limit: int = 50, offset: int = 0):
    """Notifications for user (or global where user_id IS NULL). Returns list of dicts."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, title, body, source, audio_path, created_at FROM notifications
                   WHERE user_id = %s OR user_id IS NULL ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                (user_id, limit, offset),
            )
            return cur.fetchall()


# ----- Daily briefs -----


def get_daily_brief(user_id: int, brief_date) -> Optional[dict]:
    """Get brief for user and date. brief_date: date or YYYY-MM-DD string."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, brief_date, text_content, audio_path, created_at FROM daily_briefs WHERE user_id = %s AND brief_date = %s",
                (user_id, brief_date),
            )
            return cur.fetchone()


def upsert_daily_brief(user_id: int, brief_date, text_content: str, audio_path: Optional[str] = None) -> int:
    """Insert or update daily brief. Returns id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO daily_briefs (user_id, brief_date, text_content, audio_path)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE text_content = VALUES(text_content), audio_path = COALESCE(VALUES(audio_path), audio_path), created_at = CURRENT_TIMESTAMP""",
                (user_id, brief_date, text_content, (audio_path or "")[:512]),
            )
            cur.execute(
                "SELECT id FROM daily_briefs WHERE user_id = %s AND brief_date = %s",
                (user_id, brief_date),
            )
            row = cur.fetchone()
            return row["id"] if row else 0
