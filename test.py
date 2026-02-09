"""
CLI testing interface (no auth).
Run from project root: python test.py
Uses local API (run.py must be running) or direct service calls.
Note: The API now requires login for /chat/*. For full chat with auth, use the web app at http://127.0.0.1:8000
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
    USE_REQUESTS = True
except ImportError:
    USE_REQUESTS = False

from jarvistitle import print_title

def chat_via_api(mode: str, message: str, session_id: str = None) -> tuple:
    url = "http://127.0.0.1:8000/chat/general" if mode == "general" else "http://127.0.0.1:8000/chat/realtime"
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    r = requests.post(url, json=payload, timeout=60)
    if not r.ok:
        detail = ""
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text or str(r.status_code)
        raise RuntimeError(f"Server error: {detail}")
    data = r.json()
    return data.get("reply", ""), data.get("session_id", "")


def chat_direct(mode: str, message: str, session_id: str = None) -> str:
    from app.services.chat_service import ChatService
    svc = ChatService()
    svc.vector_store.load() or svc.vector_store.build()
    sid = svc.get_or_create_session_id(session_id)
    if mode == "general":
        reply = svc.chat_general(sid, message)
    else:
        reply = svc.chat_realtime(sid, message)
    return reply, sid


def main():
    print_title()
    print("Which chatbot? 1 = General, 2 = Realtime")
    choice = input("Enter 1 or 2: ").strip() or "1"
    mode = "realtime" if choice == "2" else "general"
    session_id = None
    print(f"Using {mode} chatbot. Type your messages (empty line to exit).\n")
    while True:
        msg = input("You: ").strip()
        if not msg:
            break
        try:
            if USE_REQUESTS:
                reply, session_id = chat_via_api(mode, msg, session_id)
            else:
                reply, session_id = chat_direct(mode, msg, session_id)
            print(f"\nJarvis: {reply}\n")
        except Exception as e:
            print(f"Error: {e}\n")
    print("Bye.")


if __name__ == "__main__":
    main()
