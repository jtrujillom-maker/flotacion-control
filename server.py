"""Python simulation API; no external dependencies. Local development server."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from model import Config, simulate, compare


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data):
        body = json.dumps(data, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"status": "ok", "engine": "python"})
        elif self.path == "/api/config":
            from dataclasses import asdict
            self.respond(200, asdict(Config()))
        else:
            self.respond(404, {"error": "Use GET /health, GET /api/config, POST /api/simulate or POST /api/compare"})

    def do_POST(self):
        if self.path not in ("/api/simulate", "/api/compare"):
            self.respond(404, {"error": "unknown endpoint"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 65536:
                self.respond(413, {"error": "maximum request size 64 KiB"})
                return
            data = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
            # JSON arrays become tuples to preserve consistent parameter handling.
            defaults = Config()
            for key in data:
                if hasattr(defaults, key) and isinstance(getattr(defaults, key), tuple):
                    data[key] = tuple(tuple(x) if isinstance(x, list) else x for x in data[key])
            config = Config(**data)
            result = compare(config) if self.path == "/api/compare" else simulate(config)
            self.respond(200, result)
        except (ValueError, TypeError, OverflowError) as exc:
            self.respond(400, {"error": str(exc)})


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"Python simulation API: http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
