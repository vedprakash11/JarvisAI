"""
Run the Flask admin dashboard.
Start from project root: python run_dashboard.py
Ensure JarvisAI API is running (run.py) and LOG_FILE matches (e.g. logs/jarvisai.log).
"""
import sys
import os

# Run from project root so dashboard and config resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dashboard.app import app
from dashboard.config import DASHBOARD_PORT

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False)
