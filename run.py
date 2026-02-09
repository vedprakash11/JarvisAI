"""
Server startup script.
Run from project root: python run.py

Server binds to 0.0.0.0 so you can access it from mobile/other devices on the same network.
Note: With reload=True, saving a file triggers a restart. On Windows you may see
KeyboardInterrupt/CancelledError in the console during reload; that's normal and harmless.
"""
import socket
import uvicorn

def _local_ip():
    """Best-effort local network IP for mobile access (works on same LAN)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

if __name__ == "__main__":
    port = 8000
    ip = _local_ip()
    if ip:
        print(f"To access from mobile on the same network, open: http://{ip}:{port}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
