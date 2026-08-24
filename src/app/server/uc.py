"""Unity Catalog SQL warehouse helper using databricks-sql-connector."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from databricks import sql as dbsql

from .config import (
    IS_DATABRICKS_APP,
    LOCAL_PROFILE,
    WAREHOUSE_ID,
    get_oauth_token,
    get_workspace_client,
    get_workspace_host,
)


def _http_path() -> str:
    return f"/sql/1.0/warehouses/{WAREHOUSE_ID}"


def _hostname() -> str:
    host = get_workspace_host()
    return host.replace("https://", "").replace("http://", "").rstrip("/")


@contextmanager
def connect():
    """Open a connection to the configured SQL warehouse.

    Locally we use the SDK's CLI profile (token-credential provider).
    In Databricks Apps we use the auto-injected service principal OAuth token.
    """
    if IS_DATABRICKS_APP:
        token = get_oauth_token()
        conn = dbsql.connect(
            server_hostname=_hostname(),
            http_path=_http_path(),
            access_token=token,
        )
    else:
        # Use the SDK's authentication callable so token refresh is handled.
        w = get_workspace_client()
        cred_provider = lambda: w.config.authenticate  # noqa: E731
        conn = dbsql.connect(
            server_hostname=_hostname(),
            http_path=_http_path(),
            credentials_provider=cred_provider,
        )
    try:
        yield conn
    finally:
        conn.close()


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Run a SELECT and return rows as list of dicts (with native types preserved)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]


def execute(sql: str, params: tuple | None = None) -> None:
    """Run a non-SELECT statement (no result set)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
