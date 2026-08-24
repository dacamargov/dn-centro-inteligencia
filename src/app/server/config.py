"""Configuration & dual-mode auth (local profile vs Databricks Apps service principal)."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

# Detect environment: Databricks Apps inject DATABRICKS_APP_NAME (and CLIENT_ID/SECRET).
IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

# ---- Static config (env-overridable) -----------------------------------------
# All values come from env (app.yaml in Databricks Apps, or your shell locally).
# No internal IDs are baked in — see resources/04_app.yml in the bundle.
DASHBOARD_ID = (os.environ.get("DASHBOARD_ID") or "").strip() or None
GENIE_SPACE_ID = (os.environ.get("GENIE_SPACE_ID") or "").strip() or None
CATALOG = os.environ.get("CATALOG", "main")
SCHEMA = os.environ.get("SCHEMA", "ditcher_neira")
# Prefijo de tabla usado por todas las rutas. Ninguna consulta escribe el
# catálogo o el esquema a mano: así el repo corre en cualquier workspace
# cambiando solo las variables del bundle.
FQ = f"{CATALOG}.{SCHEMA}"
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")

# Nombre del fabricante que contrata el estudio. Todas las métricas de
# "nuestro" desempeño (disponibilidad, share of shelf, precio) se filtran por
# él; el resto del catálogo es competencia.
CLIENTE = os.environ.get("CLIENTE", "Nestlé")

# Lakebase — disabled by default (empty host → is_configured() returns False).
# The app shows a friendly "no configurado" message instead of querying Postgres.
LAKEBASE_HOST = os.environ.get("LAKEBASE_HOST") or os.environ.get("PGHOST", "")
LAKEBASE_DB = os.environ.get("LAKEBASE_DB") or os.environ.get("PGDATABASE", "dncentro")
LAKEBASE_PORT = int(os.environ.get("LAKEBASE_PORT") or os.environ.get("PGPORT") or 5432)
LAKEBASE_INSTANCE_NAME = (os.environ.get("LAKEBASE_INSTANCE_NAME") or "").strip()

# Local profile to use when not running inside Databricks Apps
LOCAL_PROFILE = os.environ.get("DATABRICKS_PROFILE") or "DEFAULT"


# ---- Workspace helpers --------------------------------------------------------
@lru_cache(maxsize=1)
def get_workspace_client():
    """Return a configured WorkspaceClient.

    In Databricks Apps the SDK auto-detects service principal credentials.
    Locally we use the configured CLI profile.
    """
    from databricks.sdk import WorkspaceClient
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    return WorkspaceClient(profile=LOCAL_PROFILE)


def get_workspace_host() -> str:
    """Return https://host (DATABRICKS_HOST in Apps is just hostname, no scheme)."""
    if IS_DATABRICKS_APP:
        host = os.environ.get("DATABRICKS_HOST", "").strip()
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host
    return get_workspace_client().config.host


def get_oauth_token() -> Optional[str]:
    """OAuth token suitable for Bearer auth against workspace APIs."""
    w = get_workspace_client()
    if w.config.token:
        return w.config.token
    auth_headers = w.config.authenticate()  # returns dict {'Authorization': 'Bearer ...'}
    if auth_headers and "Authorization" in auth_headers:
        return auth_headers["Authorization"].replace("Bearer ", "")
    return None


def get_current_user_email(request=None) -> str:
    """Current user email. In Databricks Apps, the gateway forwards the user's
    identity via `X-Forwarded-Email` (and `X-Forwarded-User`/`-Preferred-Username`).
    Falls back to the SDK's me() (which returns the SP in Apps — last resort).
    """
    if request is not None:
        for header in ("x-forwarded-email", "x-forwarded-user", "x-forwarded-preferred-username"):
            v = request.headers.get(header)
            if v:
                return v
    try:
        w = get_workspace_client()
        me = w.current_user.me()
        return me.user_name or me.display_name or "unknown"
    except Exception:
        return os.environ.get("USER", "unknown")
