"""Taste Radar web app. Run: python3 -m radar.server  then open http://127.0.0.1:8790

POST /api/taste   {"likes": ["Phoebe Bridgers", "The Bear", "trail running"], "home": "Orlando, Florida, USA"}
                  -> the Qloo entities it understood, and the brands people with that taste also like
POST /api/check   {"brand": {...}, "home": "..."} -> whether that brand has a real free offer, and how to ask
"""
import hashlib
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import offers, qloo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
LOCK = threading.Lock()


def cached(kind, key, fn):
    """Remember answers for a day's worth of demos: the same brand is not re-checked on every visit."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, kind + "-" + hashlib.sha1(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16] + ".json")
    if os.path.exists(path):
        return json.load(open(path))
    value = fn()
    with LOCK:
        json.dump(value, open(path, "w"))
    return value


STOP = {"the", "a", "an", "of", "and", "magazine", "inc", "co", "company", "brand"}


def words(text):
    return {w for w in re.findall(r"[a-z0-9']+", text.lower().replace("’", "'")) if w not in STOP and len(w) > 1}


def best_match(asked, results):
    """Qloo's search always returns something, even for names it does not know ("Thrasher Magazine" -> Elle).
    Accept only a result that shares a real word with what the person typed."""
    want = words(asked)
    for r in results:
        if want & words(r["name"] or ""):
            return r
    return None


def taste(likes, home):
    likes = [l.strip() for l in likes if l.strip()][:6]
    with ThreadPoolExecutor(4) as pool:
        found = list(pool.map(lambda l: best_match(l, qloo.search(l)), likes))
    understood = [{"asked": l, "matched": f["name"] if f else None, "id": f["id"] if f else None} for l, f in zip(likes, found)]
    ids = [u["id"] for u in understood if u["id"]]
    brands = qloo.brands_for(ids, take=24) if ids else []
    return {"understood": understood, "brands": brands}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/health":
            return self.send(200, {"ok": True, "mock": qloo.MOCK})
        if self.path in ("/", "/index.html"):
            return self.send(200, open(os.path.join(ROOT, "docs", "index.html"), "rb").read(), "text/html; charset=utf-8")
        self.send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            if self.path == "/api/taste":
                return self.send(200, cached("taste", [body.get("likes"), qloo.MOCK], lambda: taste(body.get("likes", []), body.get("home", ""))))
            if self.path == "/api/check":
                brand = {"name": str(body["brand"]["name"])[:80], "website": str(body["brand"].get("website") or "")[:200]}
                home = str(body.get("home", ""))[:80]
                return self.send(200, cached("check", [brand, home], lambda: offers.check_brand(brand, home)))
            self.send(404, {"error": "not found"})
        except Exception as e:
            self.send(500, {"error": str(e)[:300]})


def main():
    port = int(os.environ.get("PORT", "8790"))
    host = os.environ.get("HOST", "127.0.0.1")
    print("Taste Radar on http://%s:%d %s" % (host, port, "(sample Qloo data)" if qloo.MOCK else ""))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
