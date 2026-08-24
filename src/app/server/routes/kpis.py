"""GET /api/kpis — titulares de la medición continua en la ventana viva.

Todo se lee de `visitas`, el hecho principal: una fila = un SKU observado en
anaquel durante la visita de un auditor. Los porcentajes se calculan sobre las
observaciones del cliente; la competencia solo entra en el share of shelf.
"""
from fastapi import APIRouter, HTTPException, Query

from ..config import CLIENTE, FQ
from ..uc import query

router = APIRouter()


@router.get("/api/config")
def get_config():
    """Config que el frontend necesita para no quemar el nombre del cliente."""
    return {"cliente": CLIENTE}


@router.get("/api/kpis")
def get_kpis(window_min: int = Query(15, ge=1, le=120)):
    sql = f"""
        WITH win AS (
          SELECT * FROM {FQ}.visitas
          WHERE visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
        )
        SELECT
          COUNT(*)                                   AS observaciones,
          COUNT(DISTINCT store_id)                   AS pdv_visitados,
          COUNT(DISTINCT country_code)               AS paises,
          -- Disponibilidad y ejecución solo tienen sentido sobre el cliente:
          -- son el compromiso que D&N mide contra la meta del fabricante.
          ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100, 1)
                                                     AS disponibilidad_pct,
          ROUND(AVG(CASE WHEN es_cliente THEN CAST(ejecucion_perfecta AS INT) END) * 100, 1)
                                                     AS ejecucion_pct,
          ROUND(AVG(CASE WHEN es_cliente THEN CAST(planograma_ok AS INT) END) * 100, 1)
                                                     AS planograma_pct,
          -- Share of shelf = caras del cliente sobre el total de caras medidas.
          ROUND(SUM(CASE WHEN es_cliente THEN facings ELSE 0 END)
                / NULLIF(SUM(facings), 0) * 100, 1)  AS sos_cliente_pct,
          SUM(CASE WHEN es_cliente AND NOT en_stock THEN 1 ELSE 0 END)
                                                     AS quiebres,
          ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_promo AS INT) END) * 100, 1)
                                                     AS promo_pct
        FROM win
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    empty = {
        "observaciones": 0, "pdv_visitados": 0, "paises": 0,
        "disponibilidad_pct": 0.0, "ejecucion_pct": 0.0, "planograma_pct": 0.0,
        "sos_cliente_pct": 0.0, "quiebres": 0, "promo_pct": 0.0,
        "obs_por_min": 0.0, "window_min": window_min,
    }
    if not rows or not rows[0].get("observaciones"):
        return empty

    r = rows[0]
    obs = int(r.get("observaciones") or 0)
    return {
        "observaciones": obs,
        "pdv_visitados": int(r.get("pdv_visitados") or 0),
        "paises": int(r.get("paises") or 0),
        "disponibilidad_pct": float(r.get("disponibilidad_pct") or 0),
        "ejecucion_pct": float(r.get("ejecucion_pct") or 0),
        "planograma_pct": float(r.get("planograma_pct") or 0),
        "sos_cliente_pct": float(r.get("sos_cliente_pct") or 0),
        "quiebres": int(r.get("quiebres") or 0),
        "promo_pct": float(r.get("promo_pct") or 0),
        "obs_por_min": round(obs / float(window_min), 1),
        "window_min": window_min,
    }
