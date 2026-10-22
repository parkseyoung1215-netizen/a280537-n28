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
from urllib.parse import parse_qs, urlparse

from engine import HERE, World, list_branches

PORT = int(os.environ.get("WHATIF_PORT", "8000"))
lock = Lock()  # one change at a time

names = list_branches() or ["main"]
branches = {n: World(n) for n in names}
active = "main" if "main" in branches else names[0]


def branch_info():
    return [{"name": n, "week": w.state["week"], "parent": w.parent} for n, w in branches.items()]


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def everything(self):
        w = branches[active]
        return {"config": w.cfg, "active": active, "branches": branch_info(),
                "state": w.state, "history": w.history}

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self.send(200, f.read(), "text/html")
        elif url.path == "/api/world":
            self.send(200, self.everything())
        elif url.path == "/api/branch":
            name = parse_qs(url.query).get("name", [""])[0]
            if name not in branches:
                return self.send(404, {"error": "no such branch"})
            w = branches[name]
            self.send(200, {"name": name, "state": w.state, "history": w.history, "parent": w.parent})
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        global active
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        try:
            with lock:
                w = branches[active]
                if self.path == "/api/step":
                    w.step(body.get("event"))
                elif self.path == "/api/undo":
                    w.undo()
                elif self.path == "/api/reset":
                    w.reset()
                elif self.path == "/api/branch/new":
                    name = str(body.get("name") or "").strip()[:40]
                    if not name or name in branches:
                        return self.send(400, {"error": "이름이 비어 있거나 이미 있는 갈래예요"})
                    branches[name] = w.fork(name, body.get("from_week", w.state["week"]))
                    active = name
                elif self.path == "/api/branch/switch":
                    if body.get("name") not in branches:
                        return self.send(404, {"error": "no such branch"})
                    active = body["name"]
                elif self.path == "/api/branch/delete":
                    name = body.get("name")
                    if name not in branches or len(branches) == 1:
                        return self.send(400, {"error": "지울 수 없는 갈래예요"})
                    branches.pop(name).delete()
                    if active == name:
                        active = next(iter(branches))
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
