"""WSGI web application. Production: gunicorn app:application --bind 0.0.0.0:$PORT."""
from dataclasses import asdict
import json
from pathlib import Path
from model import Config, simulate, compare
from identification import simc_pi

ROOT = Path(__file__).resolve().parent
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8")}


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    code, kind, payload = 200, "application/json; charset=utf-8", None
    try:
        if method == "GET" and path in ASSETS:
            name, kind = ASSETS[path]
            payload = (ROOT / "static" / name).read_bytes()
        elif method == "GET" and path == "/health":
            payload = {"status": "ok", "engine": "python"}
        elif method == "GET" and path == "/api/config":
            payload = asdict(Config())
        elif method == "POST" and path in ("/api/simulate", "/api/compare", "/api/tune"):
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if length < 0 or length > 65536:
                code, payload = 413, {"error": "El cuerpo de la petición supera 64 KiB."}
            else:
                data = json.loads(environ["wsgi.input"].read(length) or b"{}")
                if not isinstance(data, dict):
                    raise ValueError("Se requiere un objeto JSON.")
                if path == "/api/tune":
                    payload = simc_pi(**data)
                else:
                    defaults = Config()
                    for key in data:
                        if hasattr(defaults,key) and isinstance(getattr(defaults,key),tuple):
                            data[key] = tuple(tuple(v) if isinstance(v,list) else v for v in data[key])
                    config = Config(**data)
                    # Bound public API work; offline tools retain their full limit.
                    if config.dt <= 0 or config.duration / config.dt > 10000:
                        raise ValueError("Máximo 10000 pasos por solicitud web.")
                    config.validate()
                    payload = compare(config) if path == "/api/compare" else simulate(config)
        else:
            code, payload = 404, {"error": "Ruta no encontrada."}
    except (TypeError,ValueError,OverflowError) as exc:
        code, payload = 400, {"error": str(exc)}
    if not isinstance(payload, bytes):
        payload = json.dumps(payload,allow_nan=False).encode("utf-8")
    status = {200:"OK",400:"Bad Request",404:"Not Found",413:"Payload Too Large"}[code]
    headers = [("Content-Type",kind),("Content-Length",str(len(payload))),
               ("X-Content-Type-Options","nosniff"),
               ("Referrer-Policy","same-origin"),
               ("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"),
               ("Cache-Control","no-store" if path.startswith('/api') else "no-cache")]
    start_response(str(code)+" "+status,headers)
    return [payload]


if __name__ == "__main__":
    import os
    from wsgiref.simple_server import make_server
    host = os.getenv("HOST","127.0.0.1")
    port = int(os.getenv("PORT","8000"))
    print(f"Flotación Control · http://{host}:{port}",flush=True)
    make_server(host,port,application).serve_forever()
