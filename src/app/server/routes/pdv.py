"""Puntos de venta — mapa de la red auditada y ficha de un PDV.

Cada PDV se califica por lo observado en la ventana viva: si el auditor no pasó
por ahí en ese lapso, la tienda aparece sin lecturas en vez de con un cero
engañoso. Distinguir "no medido" de "mal ejecutado" es medio negocio de D&N.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..config import FQ, get_current_user_email
from ..uc import execute, query

router = APIRouter()


def _q(s: str) -> str:
    return "'" + (s or "").replace("'", "''") + "'"


def _motivo(obs: int, dispo, plano, quiebres: int) -> str:
    """Por qué este PDV está en la lista de los que hay que atender.

    Un ranking que solo ordena por porcentaje obliga a abrir cada tienda para
    entender qué le pasa. La ejecución perfecta es disponibilidad Y planograma,
    así que la causa dominante casi siempre es una de las dos, y decirla en la
    fila es la diferencia entre un tablero y una lista de tareas.
    """
    if obs == 0:
        return "sin_medicion"
    falta_stock = dispo is not None and dispo < 80
    falta_plano = plano is not None and plano < 80
    if falta_stock and falta_plano:
        return "quiebre_y_planograma"
    if falta_stock or quiebres > 0:
        return "quiebre"
    if falta_plano:
        return "planograma"
    return "en_meta"


@router.get("/api/pdv")
def list_pdv(
    categoria: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    window_min: int = Query(60, ge=5, le=240),
):
    """Universo de PDV con su ejecución reciente, listo para pintar en el mapa."""
    cat_filter = f"AND v.categoria = {_q(categoria)}" if categoria else ""
    pais_filter = f"AND t.country_code = {_q(country_code)}" if country_code else ""

    # La ventana se parte por la mitad para poder decir si el PDV va mejorando o
    # empeorando. Un 62% que viene subiendo y un 62% que viene cayendo piden
    # cosas distintas, y sin la tendencia el ranking los trata igual.
    mitad = max(5, int(window_min) // 2)

    sql = f"""
        WITH medicion AS (
          SELECT v.store_id,
                 COUNT(*)                                         AS observaciones,
                 MAX(v.visit_ts)                                  AS ultima_visita,
                 AVG(CASE WHEN v.es_cliente THEN CAST(v.en_stock AS INT) END) * 100
                                                                  AS disponibilidad_pct,
                 AVG(CASE WHEN v.es_cliente THEN CAST(v.ejecucion_perfecta AS INT) END) * 100
                                                                  AS ejecucion_pct,
                 AVG(CASE WHEN v.es_cliente THEN CAST(v.planograma_ok AS INT) END) * 100
                                                                  AS planograma_pct,
                 SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END)
                   / NULLIF(SUM(v.facings), 0) * 100              AS sos_pct,
                 SUM(CASE WHEN v.es_cliente AND NOT v.en_stock THEN 1 ELSE 0 END)
                                                                  AS quiebres,
                 AVG(CASE
                       WHEN v.es_cliente
                        AND v.visit_ts >= current_timestamp() - INTERVAL {mitad} MINUTES
                       THEN CAST(v.ejecucion_perfecta AS INT) END) * 100
                                                                  AS ejecucion_reciente,
                 AVG(CASE
                       WHEN v.es_cliente
                        AND v.visit_ts <  current_timestamp() - INTERVAL {mitad} MINUTES
                       THEN CAST(v.ejecucion_perfecta AS INT) END) * 100
                                                                  AS ejecucion_previa
          FROM {FQ}.visitas v
          WHERE v.visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
            {cat_filter}
          GROUP BY v.store_id
        ),
        -- El SKU que más veces se leyó vacío en cada tienda: es el destinatario
        -- natural de la visita que se despacha desde el ranking.
        peor_sku AS (
          SELECT store_id, sku, producto, categoria, faltantes
          FROM (
            SELECT v.store_id, v.sku, p.nombre AS producto, v.categoria,
                   COUNT(*) AS faltantes,
                   ROW_NUMBER() OVER (
                     PARTITION BY v.store_id ORDER BY COUNT(*) DESC, v.sku
                   ) AS rn
            FROM {FQ}.visitas v
            LEFT JOIN {FQ}.productos p ON p.sku = v.sku
            WHERE v.visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
              AND v.es_cliente AND NOT v.en_stock
              {cat_filter}
            GROUP BY v.store_id, v.sku, p.nombre, v.categoria
          ) WHERE rn = 1
        )
        SELECT t.store_id, t.nombre, t.canal, t.cadena, t.formato, t.ciudad,
               t.country_code, t.latitude, t.longitude, t.mercaderista,
               t.visitas_mes_meta,
               COALESCE(m.observaciones, 0) AS observaciones,
               m.ultima_visita,
               m.disponibilidad_pct, m.ejecucion_pct, m.planograma_pct, m.sos_pct,
               COALESCE(m.quiebres, 0)      AS quiebres,
               m.ejecucion_reciente, m.ejecucion_previa,
               s.sku AS sku_critico, s.producto AS producto_critico,
               s.categoria AS categoria_critica, s.faltantes
        FROM {FQ}.tiendas t
        LEFT JOIN medicion m ON m.store_id = t.store_id
        LEFT JOIN peor_sku s ON s.store_id = t.store_id
        WHERE 1=1 {pais_filter}
        ORDER BY m.ejecucion_pct ASC NULLS LAST, m.quiebres DESC
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    out = []
    for r in rows:
        obs = int(r.get("observaciones") or 0)
        ejec = float(r["ejecucion_pct"]) if r.get("ejecucion_pct") is not None else None
        dispo = (
            float(r["disponibilidad_pct"]) if r.get("disponibilidad_pct") is not None else None
        )
        plano = (
            float(r["planograma_pct"]) if r.get("planograma_pct") is not None else None
        )
        quiebres = int(r.get("quiebres") or 0)

        rec = r.get("ejecucion_reciente")
        prev = r.get("ejecucion_previa")
        tendencia_pp = (
            round(float(rec) - float(prev), 1)
            if rec is not None and prev is not None else None
        )

        out.append({
            "store_id": r["store_id"],
            "nombre": r["nombre"],
            "canal": r["canal"],
            "cadena": r["cadena"],
            "formato": r["formato"],
            "ciudad": r["ciudad"],
            "country_code": r["country_code"],
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "mercaderista": r.get("mercaderista"),
            "visitas_mes_meta": int(r["visitas_mes_meta"] or 0),
            "observaciones": obs,
            "ultima_visita": (
                r["ultima_visita"].isoformat() if r.get("ultima_visita") else None
            ),
            "disponibilidad_pct": round(dispo, 1) if dispo is not None else None,
            "ejecucion_pct": round(ejec, 1) if ejec is not None else None,
            "planograma_pct": round(plano, 1) if plano is not None else None,
            "sos_pct": (
                round(float(r["sos_pct"]), 1) if r.get("sos_pct") is not None else None
            ),
            "quiebres": quiebres,
            "tendencia_pp": tendencia_pp,
            "motivo": _motivo(obs, dispo, plano, quiebres),
            "sku_critico": r.get("sku_critico"),
            "producto_critico": r.get("producto_critico"),
            "categoria_critica": r.get("categoria_critica"),
            "estado": (
                "sin_medicion" if obs == 0 else
                "critico" if ejec is not None and ejec < 55 else
                "riesgo" if ejec is not None and ejec < 75 else
                "ok"
            ),
        })
    return out


# ---------------------------------------------------------------------------
# Traslados entre PDV — la cola del agente de red de abastecimiento
# ---------------------------------------------------------------------------
#
# El agente escribe en `traslados` con estado 'propuesto'. Acá solo se lee y se
# registra la decisión del humano: nada se ejecuta solo, que es justo lo que hay
# que poder decir en voz alta cuando el cliente pregunta quién manda.

_TRASLADO_COLS = """
    traslado_id, sku, producto, marca, categoria, country_code,
    origen_id, origen_nombre, origen_ciudad, origen_lat, origen_lon,
    destino_id, destino_nombre, destino_ciudad, destino_lat, destino_lon,
    distancia_km, unidades, venta_recuperada_usd, costo_logistico_usd,
    ganancia_neta_usd, estado, decidido_por, decidido_en, propuesto_en
"""


def _fila_traslado(r: dict) -> dict:
    return {
        "traslado_id": r["traslado_id"],
        "sku": r["sku"],
        "producto": r.get("producto"),
        "marca": r.get("marca"),
        "categoria": r.get("categoria"),
        "country_code": r.get("country_code"),
        "origen_id": r["origen_id"],
        "origen_nombre": r.get("origen_nombre"),
        "origen_ciudad": r.get("origen_ciudad"),
        "origen_lat": float(r["origen_lat"]) if r.get("origen_lat") is not None else None,
        "origen_lon": float(r["origen_lon"]) if r.get("origen_lon") is not None else None,
        "destino_id": r["destino_id"],
        "destino_nombre": r.get("destino_nombre"),
        "destino_ciudad": r.get("destino_ciudad"),
        "destino_lat": float(r["destino_lat"]) if r.get("destino_lat") is not None else None,
        "destino_lon": float(r["destino_lon"]) if r.get("destino_lon") is not None else None,
        "distancia_km": round(float(r["distancia_km"] or 0), 1),
        "unidades": int(r["unidades"] or 0),
        "venta_recuperada_usd": float(r["venta_recuperada_usd"] or 0),
        "costo_logistico_usd": float(r["costo_logistico_usd"] or 0),
        "ganancia_neta_usd": float(r["ganancia_neta_usd"] or 0),
        "estado": r["estado"],
        "decidido_por": r.get("decidido_por"),
        "decidido_en": r["decidido_en"].isoformat() if r.get("decidido_en") else None,
        "propuesto_en": r["propuesto_en"].isoformat() if r.get("propuesto_en") else None,
    }


@router.get("/api/pdv/traslados")
def list_traslados(
    estado: Optional[str] = Query(
        None, description="propuesto | aprobado | descartado | vencido"
    ),
    country_code: Optional[str] = Query(None),
    limit: int = Query(40, ge=1, le=200),
):
    """Traslados que propuso el agente, de mayor a menor ganancia neta.

    Por defecto devuelve solo lo que está vivo: la cola abierta y lo que se
    aprobó, que es lo que la pantalla muestra. Lo vencido y lo descartado
    engordarían la lista sin que nadie pueda hacer nada con ello.
    """
    filtros = []
    if estado:
        filtros.append(f"estado = {_q(estado)}")
    else:
        filtros.append("estado IN ('propuesto', 'aprobado')")
    if country_code:
        filtros.append(f"country_code = {_q(country_code)}")
    where = f"WHERE {' AND '.join(filtros)}"
    sql = f"""
        SELECT {_TRASLADO_COLS}
        FROM {FQ}.traslados
        {where}
        ORDER BY CASE estado WHEN 'propuesto' THEN 0 WHEN 'aprobado' THEN 1 ELSE 2 END,
                 CASE WHEN estado = 'aprobado' THEN decidido_en END DESC,
                 ganancia_neta_usd DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        # La tabla puede no existir todavía en un workspace recién instalado.
        if "TABLE_OR_VIEW_NOT_FOUND" in str(exc):
            return []
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc
    return [_fila_traslado(r) for r in rows]


class DecisionTraslado(BaseModel):
    accion: str = Field(default="aprobar", description="aprobar | descartar")


@router.post("/api/pdv/traslados/{traslado_id}/decidir")
def decidir_traslado(traslado_id: str, body: DecisionTraslado, request: Request):
    accion = (body.accion or "").lower().strip()
    if accion not in ("aprobar", "descartar"):
        raise HTTPException(status_code=400, detail="acción inválida")
    estado = "aprobado" if accion == "aprobar" else "descartado"
    actor = get_current_user_email(request)

    tid = _q(traslado_id)
    try:
        actual = query(
            f"SELECT {_TRASLADO_COLS} FROM {FQ}.traslados WHERE traslado_id = {tid}"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc
    if not actual:
        raise HTTPException(status_code=404, detail="traslado no encontrado")
    if actual[0]["estado"] != "propuesto":
        raise HTTPException(status_code=409, detail="el traslado ya fue decidido")

    try:
        execute(f"""
            UPDATE {FQ}.traslados
            SET estado = {_q(estado)},
                decidido_por = {_q(actor)},
                decidido_en = current_timestamp()
            WHERE traslado_id = {tid}
        """)
        rows = query(
            f"SELECT {_TRASLADO_COLS} FROM {FQ}.traslados WHERE traslado_id = {tid}"
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC write failed: {exc}") from exc
    return _fila_traslado(rows[0])


@router.get("/api/pdv/traslados/resumen")
def resumen_traslados():
    """Cuánto vale la cola y cuánto ya se aprobó — el marcador del agente."""
    sql = f"""
        SELECT estado,
               COUNT(*)                                     AS traslados,
               COALESCE(SUM(ganancia_neta_usd), 0)          AS ganancia_usd,
               COALESCE(SUM(venta_recuperada_usd), 0)       AS venta_usd,
               COALESCE(SUM(unidades), 0)                   AS unidades,
               COALESCE(ROUND(AVG(distancia_km), 1), 0)     AS km_promedio
        FROM {FQ}.traslados
        GROUP BY estado
    """
    try:
        rows = query(sql)
    except Exception as exc:
        if "TABLE_OR_VIEW_NOT_FOUND" in str(exc):
            rows = []
        else:
            raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc
    base = {
        e: {"traslados": 0, "ganancia_usd": 0.0, "venta_usd": 0.0, "unidades": 0,
            "km_promedio": 0.0}
        for e in ("propuesto", "aprobado", "descartado", "vencido")
    }
    for r in rows:
        base[r["estado"]] = {
            "traslados": int(r["traslados"] or 0),
            "ganancia_usd": float(r["ganancia_usd"] or 0),
            "venta_usd": float(r["venta_usd"] or 0),
            "unidades": int(r["unidades"] or 0),
            "km_promedio": float(r["km_promedio"] or 0),
        }
    return base


@router.get("/api/pdv/{store_id}/detalle")
def pdv_detalle(store_id: str, window_min: int = Query(90, ge=5, le=240)):
    """Ficha de un PDV: identidad, ejecución por categoría y SKUs en quiebre."""
    sid = _q(store_id)

    sql_meta = f"""
        SELECT t.store_id, t.nombre, t.canal, t.cadena, t.formato, t.ciudad,
               t.country_code, t.mercaderista, t.visitas_mes_meta,
               pa.pais, pa.moneda
        FROM {FQ}.tiendas t
        LEFT JOIN {FQ}.paises pa ON pa.country_code = t.country_code
        WHERE t.store_id = {sid}
    """
    sql_cat = f"""
        SELECT categoria,
               COUNT(*) AS observaciones,
               ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100, 1)
                                                          AS disponibilidad_pct,
               ROUND(AVG(CASE WHEN es_cliente THEN CAST(ejecucion_perfecta AS INT) END) * 100, 1)
                                                          AS ejecucion_pct,
               ROUND(SUM(CASE WHEN es_cliente THEN facings ELSE 0 END)
                     / NULLIF(SUM(facings), 0) * 100, 1)  AS sos_pct
        FROM {FQ}.visitas
        WHERE store_id = {sid}
          AND visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
        GROUP BY categoria
        ORDER BY ejecucion_pct ASC
    """
    sql_quiebres = f"""
        SELECT v.sku, p.nombre AS producto, p.emoji, v.marca, v.categoria,
               MAX(v.visit_ts) AS ultima_lectura,
               MAX(CAST(v.planograma_ok AS INT)) AS planograma_ok
        FROM {FQ}.visitas v
        LEFT JOIN {FQ}.productos p ON p.sku = v.sku
        WHERE v.store_id = {sid}
          AND v.es_cliente AND NOT v.en_stock
          AND v.visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
        GROUP BY v.sku, p.nombre, p.emoji, v.marca, v.categoria
        ORDER BY ultima_lectura DESC
        LIMIT 12
    """
    try:
        meta_rows = query(sql_meta)
        cat_rows = query(sql_cat)
        quiebre_rows = query(sql_quiebres)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    if not meta_rows:
        raise HTTPException(status_code=404, detail="PDV no encontrado")

    return {
        "pdv": meta_rows[0],
        "por_categoria": [
            {
                "categoria": r["categoria"],
                "observaciones": int(r["observaciones"] or 0),
                "disponibilidad_pct": float(r["disponibilidad_pct"] or 0),
                "ejecucion_pct": float(r["ejecucion_pct"] or 0),
                "sos_pct": float(r["sos_pct"] or 0),
            }
            for r in cat_rows
        ],
        "quiebres": [
            {
                "sku": r["sku"],
                "producto": r.get("producto"),
                "emoji": r.get("emoji"),
                "marca": r["marca"],
                "categoria": r["categoria"],
                "planograma_ok": bool(r.get("planograma_ok")),
                "ultima_lectura": (
                    r["ultima_lectura"].isoformat() if r.get("ultima_lectura") else None
                ),
            }
            for r in quiebre_rows
        ],
    }
