# run.py — BeiSmart KE entry point
# Run this from the project root: py run.py

import sys
import os
import socket

# Add backend/ to path so all imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.app import app

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    ip = get_local_ip()
    print("\n" + "="*50)
    print("  BeiSmart KE is running!")
    print(f"  Local:   http://127.0.0.1:5000")
    print(f"  Network: http://{ip}:5000  ← open this on your phone")
    print("="*50 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
