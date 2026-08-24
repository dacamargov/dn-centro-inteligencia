"""Acceso a Lakebase (Postgres) para el estado operacional de la demo.

Aquí viven el perfil de cada punto de venta, la bitácora de sugerencias del
copiloto de campo y el historial del chat de Genie: escrituras pequeñas y
constantes, y lecturas por clave con presupuesto de milisegundos. Es justo el
patrón que Delta hace mal y Postgres hace bien.

Autenticación:
- En Databricks Apps: el service principal se identifica con DATABRICKS_CLIENT_ID
  y el rol de Postgres con ese mismo nombre lo crea el recurso `database` del app.
- En local: el desarrollador conecta con su email; el handshake OAuth crea el rol
  homónimo en el primer uso.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Optional

import psycopg2
from .config import (
    LAKEBASE_DB,
    LAKEBASE_HOST,
    LAKEBASE_INSTANCE_NAME,
    LAKEBASE_PORT,
    get_current_user_email,
    get_workspace_client,
)

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Token y conexiones
#
# El token OAuth de Lakebase dura ~1h, pero emitirlo cuesta 150-300 ms de ida y
# vuelta al control plane. Sin caché, cada sugerencia arrastraría ese costo antes
# de ejecutar una sola consulta útil y el SLA de 100 ms sería inalcanzable.
#
# Con el token cacheado, `connect()` se reduce al handshake TCP+TLS+Postgres
# (~30-80 ms). Probamos además un pool de conexiones, pero el endpoint cierra las
# conexiones ociosas muy rápido y el pre-ping terminaba costando más de lo que
# ahorraba: una conexión nueva por llamada resultó más simple y más estable.
# ──────────────────────────────────────────────────────────────────────────────

_TOKEN_TTL_S = 50 * 60   # el token vale ~60 min; renovamos antes para dejar margen

_token_lock = threading.Lock()
_cached_token: Optional[tuple[float, str]] = None    # (momento de emisión, token)


def _mint_oauth_token_raw() -> str:
    """Devuelve el token que hace de contraseña de Postgres.

    Hay dos modelos según cómo esté provisionado Lakebase:
    * Endpoint autoscaling (LAKEBASE_INSTANCE_NAME definido): se emite una
      credencial acotada a la base vía la API postgres/credentials.
    * Recurso `database` del app o instancia provisionada (sin INSTANCE_NAME):
      el token OAuth del service principal autentica directo, porque el recurso
      ya lo federó dentro de la instancia.
    """
    if LAKEBASE_INSTANCE_NAME:
        w = get_workspace_client()
        resp = w.api_client.do(
            "POST",
            "/api/2.0/postgres/credentials",
            body={"endpoint": LAKEBASE_INSTANCE_NAME},
        )
        token = resp.get("token") if isinstance(resp, dict) else None
        if not token:
            raise RuntimeError(f"Could not mint Lakebase credential: {resp}")
        return token
    from .config import get_oauth_token
    token = get_oauth_token()
    if not token:
        raise RuntimeError("Could not obtain OAuth token for Lakebase")
    return token


def _mint_oauth_token() -> str:
    """Devuelve el token cacheado y solo emite uno nuevo si venció."""
    global _cached_token
    with _token_lock:
        now = time.monotonic()
        if _cached_token is not None:
            mint_time, tok = _cached_token
            if (now - mint_time) < _TOKEN_TTL_S:
                return tok
        tok = _mint_oauth_token_raw()
        _cached_token = (now, tok)
        return tok


def _invalidate_token():
    """Fuerza la emisión de un token nuevo en la próxima llamada."""
    global _cached_token
    with _token_lock:
        _cached_token = None


def _pg_user() -> str:
    # En Apps, el application id del service principal es el nombre del rol de
    # Postgres que creó el recurso `database`. En local, el email del desarrollador.
    client_id = os.environ.get("DATABRICKS_CLIENT_ID")
    if client_id:
        return client_id
    return get_current_user_email()


def is_configured() -> bool:
    return bool(LAKEBASE_HOST)


@contextmanager
def connect():
    """Abre una conexión nueva por llamada, reusando el token OAuth cacheado."""
    if not is_configured():
        raise RuntimeError(
            "Lakebase not configured (LAKEBASE_HOST / LAKEBASE_INSTANCE_NAME missing)"
        )
    token = _mint_oauth_token()   # cached, instant after first call
    user = _pg_user()
    try:
        conn = psycopg2.connect(
            host=LAKEBASE_HOST,
            port=LAKEBASE_PORT,
            dbname=LAKEBASE_DB,
            user=user,
            password=token,
            sslmode="require",
            connect_timeout=10,
        )
    except psycopg2.OperationalError as exc:
        # Token might be expired/rotated mid-session → invalidate and retry once
        log.warning("Lakebase connect failed, retrying with fresh token: %s", exc)
        _invalidate_token()
        token = _mint_oauth_token()
        conn = psycopg2.connect(
            host=LAKEBASE_HOST,
            port=LAKEBASE_PORT,
            dbname=LAKEBASE_DB,
            user=user,
            password=token,
            sslmode="require",
            connect_timeout=10,
        )
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def log_genie_interaction(
    *,
    conversation_id: str,
    message_id: str,
    user_email: Optional[str],
    question: str,
    answer: Optional[str],
    sql_query: Optional[str],
    status: Optional[str],
    row_count: Optional[int],
    has_result: bool,
    error: Optional[str],
    duration_ms: Optional[int],
) -> None:
    """Guarda un turno del chat de Genie.

    Se traga los errores a propósito: un hipo de Lakebase no puede romper el chat
    delante de la audiencia.
    """
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.genie_interactions
                      (conversation_id, message_id, user_email, question, answer,
                       sql_query, status, row_count, has_result, error, duration_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conversation_id, message_id, user_email, question, answer,
                        sql_query, status, row_count, has_result, error, duration_ms,
                    ),
                )
            conn.commit()
    except Exception as exc:
        log.warning("Lakebase log_genie_interaction failed: %s", exc)
