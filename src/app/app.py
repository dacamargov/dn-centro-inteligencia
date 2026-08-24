"""dichter & neira · Centro de Inteligencia — entrypoint FastAPI.

Monta:
  * los routers REST bajo /api/*
  * el build estático de React bajo / (frontend/dist)

Correr en local:
    cd app && uv sync
    DATABRICKS_PROFILE=<tu-perfil> uv run uvicorn app:app --reload
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.routes import (
    campo,
    dashboard,
    demo,
    genie,
    kpis,
    lakebase_studio,
    pdv,
    precios,
    recommendations,
    social,
    targets,
    targets_drill,
    visitas,
)

app = FastAPI(title="dichter & neira · Centro de Inteligencia", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # solo demo — Databricks Apps ya hace de proxy de auth
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Routers REST ------------------------------------------------------------
app.include_router(kpis.router)
app.include_router(visitas.router)
app.include_router(recommendations.router)
app.include_router(precios.router)
app.include_router(social.router)
app.include_router(dashboard.router)
app.include_router(genie.router)
app.include_router(targets.router)
app.include_router(targets_drill.router)
app.include_router(pdv.router)
app.include_router(campo.router)
app.include_router(lakebase_studio.router)
app.include_router(demo.router)


@app.on_event("startup")
def _prewarm_caches():
    """Calienta el cache del catálogo en background: la primera sugerencia ya
    sale caliente, sin pagar el round-trip al warehouse dentro del SLA."""
    lakebase_studio.prewarm()
    _retomar_flujo_campo()


def _retomar_flujo_campo():
    """Reengancha la jornada del copiloto si la demo quedó encendida.

    El flujo es un hilo del proceso, así que un redespliegue lo mata mientras los
    jobs siguen corriendo: el resto del tablero late y la pestaña Campo aparece
    congelada, sin ninguna señal de por qué. Esto lo levanta solo si los jobs
    están activos, y en background para no retrasar el arranque.
    """
    import threading

    def _worker():
        try:
            from server.lakebase import is_configured

            if not is_configured():
                return
            if not demo.demo_status().get("running"):
                return
            from server.campo_flujo import flujo

            flujo.arrancar(ritmo=6.0)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "no pude retomar el flujo de campo: %s", exc
            )

    threading.Thread(target=_worker, name="flujo-retomar", daemon=True).start()


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "dn-centro-inteligencia"}


# ---- Static frontend ---------------------------------------------------------
HERE = Path(__file__).parent.resolve()
FRONTEND_DIST = HERE / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/") or full_path == "healthz":
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # If the request maps to a real file inside dist/ (favicon, manifest, etc.),
        # serve that file. Otherwise fall back to index.html (SPA routing).
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            try:
                candidate.relative_to(FRONTEND_DIST.resolve())
                if candidate.is_file():
                    return FileResponse(candidate)
            except ValueError:
                pass  # path tries to escape dist; ignore
        index = FRONTEND_DIST / "index.html"
        if not index.exists():
            return JSONResponse({"detail": "frontend not built"}, status_code=503)
        return FileResponse(index)
else:
    @app.get("/")
    def root():
        return {
            "ok": True,
            "message": "Frontend not built yet. Run `cd frontend && npm install && npm run build`.",
        }
