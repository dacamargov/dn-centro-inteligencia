"""Endpoints de visitas — ticker en vivo, series por minuto y cortes de ejecución.

Reemplaza al feed de ventas del dominio retail: aquí el evento que fluye no es
una orden sino una observación de anaquel hecha por un auditor en un PDV.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..config import FQ
from ..uc import query

router = APIRouter()


def _q(s: str) -> str:
    return "'" + (s or "").replace("'", "''") + "'"


# Retraso de sincronización del ticker, en segundos.
#
# El generador corre una vez por minuto y deja escrito el minuto que acaba de
# pasar, con una lectura cada medio segundo. Si el ticker mostrara simplemente las
# más recientes, quedaría congelado durante 60 segundos y luego daría un salto de
# cien filas: eso es lo que se veía.
#
# Revelando solo las lecturas anteriores a `ahora - RETRASO_SYNC_S`, el corte
# avanza con el reloj de pared y las lecturas van apareciendo de a una, sobre dato
# que ya está completo en la tabla. No se inventa nada en el frontend ni se
# escriben timestamps futuros —que romperían todos los agregados—: es la misma
# tabla, leída con un minuto de rezago.
#
# 60 s alcanzarían si el job fuera puntual al segundo; 70 dan margen para que un
# arranque demorado no seque el flujo.
RETRASO_SYNC_S = 70


@router.get("/api/visitas/recent")
def recent(limit: int = Query(200, ge=1, le=400)):
    """Ticker de lecturas de anaquel, revelado a ritmo de reloj.

    Devuelve las más recientes que ya "sincronizaron" (ver RETRASO_SYNC_S), de
    manera que cada segundo entran una o dos nuevas por arriba. El límite acota
    la ventana visible; la retención de la tabla la maneja el generador.
    """
    sql = f"""
        SELECT v.visita_id, v.store_id, v.sku, v.marca, v.fabricante, v.categoria,
               v.cadena, v.canal, v.ciudad, v.country_code, v.facings,
               v.precio_usd, v.en_stock, v.en_promo, v.planograma_ok,
               v.ejecucion_perfecta, v.share_of_shelf, v.confianza_ir,
               v.es_cliente, v.visit_ts,
               t.nombre AS tienda, p.nombre AS producto, p.emoji
        FROM {FQ}.visitas v
        LEFT JOIN {FQ}.tiendas   t ON t.store_id = v.store_id
        LEFT JOIN {FQ}.productos p ON p.sku = v.sku
        WHERE v.visit_ts <= current_timestamp() - INTERVAL {RETRASO_SYNC_S} SECONDS
        ORDER BY v.visit_ts DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "visita_id": r["visita_id"],
            "store_id": r["store_id"],
            "tienda": r.get("tienda"),
            "sku": r["sku"],
            "producto": r.get("producto"),
            "emoji": r.get("emoji"),
            "marca": r["marca"],
            "fabricante": r["fabricante"],
            "categoria": r["categoria"],
            "cadena": r["cadena"],
            "canal": r["canal"],
            "ciudad": r["ciudad"],
            "country_code": r["country_code"],
            "facings": int(r["facings"] or 0),
            "precio_usd": float(r["precio_usd"]) if r.get("precio_usd") is not None else None,
            "en_stock": bool(r["en_stock"]),
            "en_promo": bool(r["en_promo"]),
            "planograma_ok": bool(r["planograma_ok"]),
            "ejecucion_perfecta": bool(r["ejecucion_perfecta"]),
            "share_of_shelf": float(r["share_of_shelf"] or 0),
            "confianza_ir": float(r["confianza_ir"] or 0),
            "es_cliente": bool(r["es_cliente"]),
            "visit_ts": r["visit_ts"].isoformat() if r.get("visit_ts") else None,
        }
        for r in rows
    ]


@router.get("/api/visitas/timeline")
def timeline(window_min: int = Query(30, ge=5, le=180)):
    """Disponibilidad y ejecución por minuto, desglosadas por categoría.

    Se lee directo de `visitas` y no del agregado `ejecucion_realtime`: ese se
    reconstruye cada minuto con DELETE+INSERT y puede quedar vacío un instante,
    lo que hace parpadear el gráfico con un "sin datos" falso.
    """
    # Cada minuto trae unas 60 lecturas repartidas entre cinco categorías, así que
    # una categoría se calcula sobre ~12 observaciones y cada una la mueve 8 puntos.
    # Crudas, las cinco curvas se cruzan sin parar y no se lee ninguna. La media
    # móvil de 5 minutos multiplica por cinco la base de cada punto: el nivel de la
    # categoría es el mismo, pero deja de ser ruido.
    suavizado = 5
    sql = f"""
        WITH por_minuto AS (
          SELECT DATE_TRUNC('MINUTE', visit_ts) AS minute_ts,
                 categoria,
                 COUNT(*)                              AS obs,
                 SUM(CAST(en_stock AS INT))            AS en_stock,
                 SUM(CAST(ejecucion_perfecta AS INT))  AS perfectas
          FROM {FQ}.visitas
          WHERE visit_ts >= current_timestamp() - INTERVAL {int(window_min) + suavizado} MINUTES
            AND es_cliente
          GROUP BY DATE_TRUNC('MINUTE', visit_ts), categoria
        ),
        movil AS (
          SELECT minute_ts,
                 categoria,
                 obs AS observaciones,
                 ROUND(SUM(en_stock)  OVER w * 100.0 / NULLIF(SUM(obs) OVER w, 0), 1)
                     AS disponibilidad_pct,
                 ROUND(SUM(perfectas) OVER w * 100.0 / NULLIF(SUM(obs) OVER w, 0), 1)
                     AS ejecucion_pct
          FROM por_minuto
          WINDOW w AS (
            PARTITION BY categoria ORDER BY CAST(minute_ts AS LONG)
            RANGE BETWEEN {(suavizado - 1) * 60} PRECEDING AND CURRENT ROW
          )
        )
        -- El recorte va después de la ventana: si filtrara antes, los primeros
        -- minutos del gráfico se suavizarían contra nada y arrancarían crudos.
        SELECT *
        FROM movil
        WHERE minute_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
          -- El minuto en curso va a medias: solo han aterrizado las visitas de
          -- los primeros segundos, así que casi siempre le faltan categorías y
          -- el último punto del gráfico se caía a una sola curva.
          AND minute_ts < DATE_TRUNC('MINUTE', current_timestamp())
        ORDER BY minute_ts
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    buckets: dict = {}
    cats: set = set()
    for r in rows:
        ts = r["minute_ts"].isoformat() if r.get("minute_ts") else None
        cat = r.get("categoria") or "?"
        cats.add(cat)
        b = buckets.setdefault(
            ts, {"minute_ts": ts, "observaciones": 0, "por_categoria": {}}
        )
        b["por_categoria"][cat] = {
            "disponibilidad_pct": float(r.get("disponibilidad_pct") or 0),
            "ejecucion_pct": float(r.get("ejecucion_pct") or 0),
            "observaciones": int(r.get("observaciones") or 0),
        }
        b["observaciones"] += int(r.get("observaciones") or 0)

    # Promedio ponderado del minuto: sin ponderar, una categoría con 3 lecturas
    # pesaría lo mismo que una con 300 y la línea saltaría sin razón.
    for b in buckets.values():
        total = b["observaciones"] or 1
        b["disponibilidad_pct"] = round(
            sum(c["disponibilidad_pct"] * c["observaciones"] for c in b["por_categoria"].values())
            / total, 1
        )
        b["ejecucion_pct"] = round(
            sum(c["ejecucion_pct"] * c["observaciones"] for c in b["por_categoria"].values())
            / total, 1
        )

    return {
        "categorias": sorted(cats),
        "puntos": sorted(buckets.values(), key=lambda x: x["minute_ts"] or ""),
    }


@router.get("/api/visitas/skus-criticos")
def skus_criticos(
    window_min: int = Query(30, ge=1, le=120),
    limit: int = Query(10, ge=1, le=50),
    categoria: Optional[str] = Query(None),
):
    """SKUs del cliente con peor disponibilidad — el panel de quiebres críticos."""
    cat_filter = f"AND v.categoria = {_q(categoria)}" if categoria else ""
    sql = f"""
        SELECT v.sku, p.nombre AS producto, p.emoji, v.marca, v.categoria,
               p.subcategoria,
               COUNT(*)                                              AS observaciones,
               SUM(CASE WHEN NOT v.en_stock THEN 1 ELSE 0 END)       AS quiebres,
               COUNT(DISTINCT CASE WHEN NOT v.en_stock THEN v.store_id END) AS pdv_afectados,
               ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1)          AS disponibilidad_pct,
               ROUND(AVG(CAST(v.planograma_ok AS INT)) * 100, 1)     AS planograma_pct,
               ROUND(AVG(v.facings), 1)                              AS facings_prom,
               ROUND(AVG(v.precio_usd), 2)                           AS precio_usd_prom
        FROM {FQ}.visitas v
        LEFT JOIN {FQ}.productos p ON p.sku = v.sku
        WHERE v.visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
          AND v.es_cliente
          {cat_filter}
        GROUP BY v.sku, p.nombre, p.emoji, v.marca, v.categoria, p.subcategoria
        HAVING COUNT(*) >= 5
        ORDER BY disponibilidad_pct ASC, quiebres DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "sku": r["sku"],
            "producto": r.get("producto"),
            "emoji": r.get("emoji"),
            "marca": r["marca"],
            "categoria": r["categoria"],
            "subcategoria": r.get("subcategoria"),
            "observaciones": int(r["observaciones"]),
            "quiebres": int(r["quiebres"]),
            "pdv_afectados": int(r["pdv_afectados"]),
            "disponibilidad_pct": float(r["disponibilidad_pct"] or 0),
            "planograma_pct": float(r["planograma_pct"] or 0),
            "facings_prom": float(r["facings_prom"] or 0),
            "precio_usd_prom": float(r["precio_usd_prom"] or 0),
        }
        for r in rows
    ]


@router.get("/api/visitas/por-categoria")
def por_categoria(window_min: int = Query(30, ge=1, le=120)):
    """Corte por categoría: disponibilidad, ejecución y share of shelf del cliente."""
    sql = f"""
        SELECT
          categoria,
          COUNT(*)                                                       AS observaciones,
          COUNT(DISTINCT store_id)                                       AS pdv,
          ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100, 1)
                                                                         AS disponibilidad_pct,
          ROUND(AVG(CASE WHEN es_cliente THEN CAST(ejecucion_perfecta AS INT) END) * 100, 1)
                                                                         AS ejecucion_pct,
          ROUND(SUM(CASE WHEN es_cliente THEN facings ELSE 0 END)
                / NULLIF(SUM(facings), 0) * 100, 1)                      AS sos_cliente_pct,
          SUM(CASE WHEN es_cliente AND NOT en_stock THEN 1 ELSE 0 END)   AS quiebres
        FROM {FQ}.visitas
        WHERE visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
        GROUP BY categoria
        ORDER BY ejecucion_pct ASC
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "categoria": r["categoria"],
            "observaciones": int(r["observaciones"] or 0),
            "pdv": int(r["pdv"] or 0),
            "disponibilidad_pct": float(r["disponibilidad_pct"] or 0),
            "ejecucion_pct": float(r["ejecucion_pct"] or 0),
            "sos_cliente_pct": float(r["sos_cliente_pct"] or 0),
            "quiebres": int(r["quiebres"] or 0),
        }
        for r in rows
    ]


@router.get("/api/visitas/por-pais")
def por_pais(window_min: int = Query(30, ge=1, le=120)):
    """Corte por país y canal — el mapa regional de la operación."""
    sql = f"""
        SELECT
          v.country_code,
          pa.pais,
          pa.region_dn,
          COUNT(*)                                                        AS observaciones,
          COUNT(DISTINCT v.store_id)                                      AS pdv,
          ROUND(AVG(CASE WHEN v.es_cliente THEN CAST(v.en_stock AS INT) END) * 100, 1)
                                                                          AS disponibilidad_pct,
          ROUND(AVG(CASE WHEN v.es_cliente THEN CAST(v.ejecucion_perfecta AS INT) END) * 100, 1)
                                                                          AS ejecucion_pct,
          ROUND(SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END)
                / NULLIF(SUM(v.facings), 0) * 100, 1)                     AS sos_cliente_pct,
          ROUND(AVG(CASE WHEN v.canal = 'Moderno' AND v.es_cliente
                         THEN CAST(v.ejecucion_perfecta AS INT) END) * 100, 1)
                                                                          AS ejecucion_moderno_pct,
          ROUND(AVG(CASE WHEN v.canal = 'Tradicional' AND v.es_cliente
                         THEN CAST(v.ejecucion_perfecta AS INT) END) * 100, 1)
                                                                          AS ejecucion_tradicional_pct
        FROM {FQ}.visitas v
        LEFT JOIN {FQ}.paises pa ON pa.country_code = v.country_code
        WHERE v.visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
        GROUP BY v.country_code, pa.pais, pa.region_dn
        ORDER BY ejecucion_pct ASC
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "country_code": r["country_code"],
            "pais": r.get("pais") or r["country_code"],
            "region_dn": r.get("region_dn"),
            "observaciones": int(r["observaciones"] or 0),
            "pdv": int(r["pdv"] or 0),
            "disponibilidad_pct": float(r["disponibilidad_pct"] or 0),
            "ejecucion_pct": float(r["ejecucion_pct"] or 0),
            "sos_cliente_pct": float(r["sos_cliente_pct"] or 0),
            "ejecucion_moderno_pct": float(r["ejecucion_moderno_pct"] or 0),
            "ejecucion_tradicional_pct": float(r["ejecucion_tradicional_pct"] or 0),
        }
        for r in rows
    ]
