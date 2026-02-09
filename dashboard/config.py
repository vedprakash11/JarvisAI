"""
Dashboard config: API URL, MySQL (admin table), log file path.
Uses same .env as main app (MYSQL_*, JARVIS_API_URL, etc.).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
# JarvisAI API base URL (must be running for status to load)
JARVIS_API_URL = os.getenv("JARVIS_API_URL", "http://127.0.0.1:8000")
# MySQL (same as main app - for admins table)
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "jarvisai")
# Log file path (same as main app LOG_FILE, or override)
LOG_FILE = os.getenv("LOG_FILE", "logs/jarvisai.log")
# Resolve relative to project root
if not Path(LOG_FILE).is_absolute():
    LOG_FILE = str(BASE_DIR / LOG_FILE)
# Dashboard port
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
# Flask session secret (use JWT_SECRET or a random string in production)
SECRET_KEY = os.getenv("SESSION_SECRET", os.getenv("JWT_SECRET", "dashboard-dev-secret-change-in-production"))
