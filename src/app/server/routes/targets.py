"""Metas por categoría — Meta vs Realizado de ejecución en el punto de venta.

A diferencia de un panel de ventas, aquí meta y realizado son **niveles**
(porcentajes), no acumulados: la disponibilidad objetivo de una categoría es
92%, y lo realizado es el 90.4% observado en la ventana viva. Comparar nivel
contra nivel hace que el indicador sea estable corra la demo 5 minutos o 3
horas, sin necesidad de prorratear nada.

Lo único que se cuida es el ruido: con pocas observaciones un porcentaje salta
mucho, así que el cumplimiento se encoge hacia 100% mientras la muestra es
chica y converge al valor real conforme entran lecturas.
"""
from fastapi import APIRouter, HTTPException, Query

from ..config import FQ
from ..uc import query

router = APIRouter()

# Observaciones-equivalentes del prior "en meta". Con la muestra chica de los
# primeros ticks el cumplimiento se acerca a 100%; pasadas unas centenas de
# lecturas su peso es despreciable.
SHRINK_OBS = 120.0


def _shrink(pace: float, n: float) -> float:
    return (n * pace + SHRINK_OBS * 100.0) / (n + SHRINK_OBS) if n > 0 else 100.0


@router.get("/api/targets")
def category_targets(window_min: int = Query(30, ge=5, le=180)):
    sql = f"""
        WITH realizado AS (
          SELECT
            categoria,
            COUNT(*)                                                      AS observaciones,
            SUM(CASE WHEN es_cliente THEN 1 ELSE 0 END)                   AS obs_cliente,
            AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100 AS disponibilidad_pct,
            AVG(CASE WHEN es_cliente THEN CAST(ejecucion_perfecta AS INT) END) * 100
                                                                          AS ejecucion_pct,
            SUM(CASE WHEN es_cliente THEN facings ELSE 0 END)
              / NULLIF(SUM(facings), 0) * 100                             AS sos_pct,
            SUM(CASE WHEN es_cliente AND NOT en_stock THEN 1 ELSE 0 END)  AS quiebres
          FROM {FQ}.visitas
          WHERE visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
          GROUP BY categoria
        )
        SELECT
          m.categoria,
          m.meta_disponibilidad_pct,
          m.meta_ejecucion_pct,
          m.meta_sos_pct,
          COALESCE(r.observaciones, 0)  AS observaciones,
          COALESCE(r.obs_cliente, 0)    AS obs_cliente,
          r.disponibilidad_pct,
          r.ejecucion_pct,
          r.sos_pct,
          COALESCE(r.quiebres, 0)       AS quiebres
        FROM {FQ}.metas_categoria m
        LEFT JOIN realizado r ON r.categoria = m.categoria
        ORDER BY m.categoria
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    out = []
    for r in rows:
        obs_cliente = float(r.get("obs_cliente") or 0)
        meta_disp = float(r.get("meta_disponibilidad_pct") or 0)
        meta_ejec = float(r.get("meta_ejecucion_pct") or 0)
        meta_sos = float(r.get("meta_sos_pct") or 0)

        disp = float(r["disponibilidad_pct"]) if r.get("disponibilidad_pct") is not None else 0.0
        ejec = float(r["ejecucion_pct"]) if r.get("ejecucion_pct") is not None else 0.0
        sos = float(r["sos_pct"]) if r.get("sos_pct") is not None else 0.0

        # El cumplimiento titular es el de ejecución perfecta: resume en un solo
        # número si el producto está en el anaquel Y bien exhibido.
        pace = _shrink((ejec / meta_ejec * 100) if meta_ejec else 0.0, obs_cliente)
        pace_disp = _shrink((disp / meta_disp * 100) if meta_disp else 0.0, obs_cliente)
        pace_sos = _shrink((sos / meta_sos * 100) if meta_sos else 0.0, obs_cliente)

        out.append({
            "categoria": r["categoria"],
            "observaciones": int(r.get("observaciones") or 0),
            "obs_cliente": int(obs_cliente),
            "quiebres": int(r.get("quiebres") or 0),
            "meta_disponibilidad_pct": meta_disp,
            "meta_ejecucion_pct": meta_ejec,
            "meta_sos_pct": meta_sos,
            "disponibilidad_pct": round(disp, 1),
            "ejecucion_pct": round(ejec, 1),
            "sos_pct": round(sos, 1),
            "cumplimiento_pct": round(pace, 1),
            "cumplimiento_disponibilidad_pct": round(pace_disp, 1),
            "cumplimiento_sos_pct": round(pace_sos, 1),
            "status": (
                "above" if pace >= 105 else
                "on" if pace >= 95 else
                "behind"
            ),
        })
    return out
