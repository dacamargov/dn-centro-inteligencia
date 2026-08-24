"""GET /api/dashboard/embed-url — Lakeview dashboard embed URL."""
from fastapi import APIRouter

from ..config import DASHBOARD_ID, get_workspace_host

router = APIRouter()


@router.get("/api/dashboard/embed-url")
def embed_url():
    host = get_workspace_host().rstrip("/")
    return {
        "url": f"{host}/embed/dashboardsv3/{DASHBOARD_ID}" if DASHBOARD_ID else None,
        "dashboard_id": DASHBOARD_ID,
    }
