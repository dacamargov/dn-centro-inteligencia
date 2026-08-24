"""Previsualiza el frontend construido contra el app ya desplegado.

Sirve `app/frontend/dist` en localhost y reenvía `/api` y `/healthz` al app en
Databricks agregando el token OAuth. Sirve para revisar cambios de interfaz con
dato real sin tener que levantar el backend en local.

    DATABRICKS_HOST=... TOKEN=$(databricks auth token -p PERFIL | jq -r .access_token) \
        python3 scripts/preview.py

Luego abre http://localhost:5199
"""
import os
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

APP_URL = os.environ["APP_URL"].rstrip("/")
TOKEN = os.environ["TOKEN"]
DIST = Path(__file__).resolve().parent.parent / "app" / "frontend" / "dist"
PORT = int(os.environ.get("PORT", "5199"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIST), **kw)

    def log_message(self, *a):  # silencio: el ruido tapa los errores útiles
        pass

    def _proxy(self, body: bytes | None = None):
        req = urllib.request.Request(
            APP_URL + self.path,
            data=body,
            method=self.command,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": self.headers.get("Content-Type", "application/json"),
            },
        )
        try:
            with urllib.request.urlopen(req) as r:
                payload, code = r.read(), r.status
        except urllib.error.HTTPError as e:
            payload, code = e.read(), e.code
        except Exception as e:  # noqa: BLE001
            payload, code = str(e).encode(), 502
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.startswith(("/api/", "/healthz")):
            return self._proxy()
        # SPA: cualquier ruta desconocida devuelve el index para que enrute React.
        if not (DIST / self.path.lstrip("/")).is_file():
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self._proxy(self.rfile.read(n) if n else b"{}")


if __name__ == "__main__":
    print(f"preview en http://localhost:{PORT}  →  {APP_URL}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
