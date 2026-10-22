"""
What-If World - start the app.

Run:  python3 app.py
Then open http://localhost:8000 in your browser.
No extra packages needed (standard library only).
"""

import json
import os
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

from engine import HERE, World

PORT = int(os.environ.get("WHATIF_PORT", "8000"))
world = World()
lock = Lock()  # one week at a time


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def everything(self):
        return {"config": world.cfg, "state": world.state, "history": world.history}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self.send(200, f.read(), "text/html")
        elif self.path == "/api/world":
            self.send(200, self.everything())
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        try:
            with lock:
                if self.path == "/api/step":
                    world.step(body.get("event"))
                elif self.path == "/api/undo":
                    world.undo()
                elif self.path == "/api/reset":
                    world.reset()
                else:
                    return self.send(404, {"error": "not found"})
            self.send(200, self.everything())
        except Exception as e:
            traceback.print_exc()
            self.send(500, {"error": str(e)})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    print(f"What-If World is running at {url}  (stop with Ctrl+C)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
