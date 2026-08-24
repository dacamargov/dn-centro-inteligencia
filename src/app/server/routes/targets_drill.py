"""Drill-down de categoría — diagnóstico, explicación con LLM y ficha de SKU.

Es el camino que recorre el ejecutivo cuando una categoría aparece por debajo
de meta: primero el diagnóstico determinístico (SQL puro, siempre el mismo
número), después la lectura del LLM sobre esos mismos datos, y por último el
detalle SKU por SKU. El LLM nunca calcula: solo interpreta el JSON que le
entrega el diagnóstico.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import CLIENTE, FQ, get_current_user_email
from ..llm import EXPLAIN_LLM_ENDPOINT, get_openai_client
from ..uc import execute, query

router = APIRouter()

# Debe coincidir con el window_min por defecto de /api/targets para que el pace
# del drill-down dé exactamente el mismo número que la tarjeta de la categoría.
WINDOW_MIN = 30
SHRINK_OBS = 120.0
INDICE_ALERTA = 108.0
TOP_SKU_LIMIT = 5
CACHE_TTL_SECONDS = 30
PREFETCH_TOP_N = 5

_response_cache: dict[str, tuple[float, dict]] = {}


def _cache_get(key: str) -> Optional[dict]:
    entry = _response_cache.get(key)
    if entry and (time.monotonic() - entry[0]) < CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_set(key: str, value: dict) -> None:
    _response_cache[key] = (time.monotonic(), value)


def _sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _shrink(pace: float, n: float) -> float:
    return (n * pace + SHRINK_OBS * 100.0) / (n + SHRINK_OBS) if n > 0 else 100.0


def _collect_diagnosis(categoria: str) -> dict:
    """Cuatro consultas determinísticas que arman el diagnóstico de la categoría."""
    cache_key = f"diagnose:{categoria}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    cat_lit = _sql_str(categoria)

    totales_sql = f"""
        WITH r AS (
          SELECT
            COUNT(*)                                                      AS observaciones,
            SUM(CASE WHEN es_cliente THEN 1 ELSE 0 END)                   AS obs_cliente,
            AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100 AS disponibilidad_pct,
            AVG(CASE WHEN es_cliente THEN CAST(ejecucion_perfecta AS INT) END) * 100
                                                                          AS ejecucion_pct,
            AVG(CASE WHEN es_cliente THEN CAST(planograma_ok AS INT) END) * 100
                                                                          AS planograma_pct,
            SUM(CASE WHEN es_cliente THEN facings ELSE 0 END)
              / NULLIF(SUM(facings), 0) * 100                             AS sos_pct,
            SUM(CASE WHEN es_cliente AND NOT en_stock THEN 1 ELSE 0 END)  AS quiebres,
            COUNT(DISTINCT store_id)                                      AS pdv_medidos
          FROM {FQ}.visitas
          WHERE categoria = {cat_lit}
            AND visit_ts >= current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES
        )
        SELECT r.*, m.meta_disponibilidad_pct, m.meta_ejecucion_pct, m.meta_sos_pct
        FROM r LEFT JOIN {FQ}.metas_categoria m ON m.categoria = {cat_lit}
    """

    senales_sql = f"""
        SELECT
          (SELECT COUNT(DISTINCT sku)
           FROM {FQ}.precios_competencia
           WHERE categoria = {cat_lit} AND es_cliente
             AND indice_precio >= {INDICE_ALERTA}
             AND snapshot_ts >= current_timestamp() - INTERVAL 30 MINUTES
          ) AS skus_caros,
          (SELECT ROUND(AVG(indice_precio), 1)
           FROM {FQ}.precios_competencia
           WHERE categoria = {cat_lit} AND es_cliente
             AND snapshot_ts >= current_timestamp() - INTERVAL 30 MINUTES
          ) AS indice_promedio,
          (SELECT COUNT(*)
           FROM {FQ}.social_posts sp
           WHERE sp.sentiment = 'negativo'
             AND sp.posted_at >= current_timestamp() - INTERVAL 60 MINUTES
             AND sp.marca IN (SELECT DISTINCT marca FROM {FQ}.productos
                              WHERE categoria = {cat_lit} AND es_cliente)
          ) AS posts_negativos,
          (SELECT COUNT(DISTINCT store_id)
           FROM {FQ}.visitas
           WHERE categoria = {cat_lit} AND es_cliente AND NOT en_stock
             AND visit_ts >= current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES
          ) AS pdv_con_quiebre
    """

    top_skus_sql = f"""
        SELECT
          v.sku, p.nombre AS producto, p.emoji, v.marca, p.subcategoria,
          COUNT(*)                                           AS lecturas,
          ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1)       AS disponibilidad_pct,
          ROUND(AVG(CAST(v.planograma_ok AS INT)) * 100, 1)  AS planograma_pct,
          ROUND(AVG(v.facings), 1)                           AS facings_prom,
          COUNT(DISTINCT CASE WHEN NOT v.en_stock THEN v.store_id END) AS pdv_afectados,
          CAST(p.precio_sugerido_usd AS DOUBLE)              AS precio_sugerido_usd
        FROM {FQ}.visitas v
        JOIN {FQ}.productos p ON p.sku = v.sku
        WHERE v.categoria = {cat_lit} AND v.es_cliente
          AND v.visit_ts >= current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES
        GROUP BY v.sku, p.nombre, p.emoji, v.marca, p.subcategoria, p.precio_sugerido_usd
        HAVING COUNT(*) >= 3
        ORDER BY disponibilidad_pct ASC, pdv_afectados DESC
        LIMIT {TOP_SKU_LIMIT}
    """

    recs_sql = f"""
        WITH ultima AS (
          SELECT recommendation_id, action,
                 ROW_NUMBER() OVER (PARTITION BY recommendation_id ORDER BY occurred_at DESC) AS rn
          FROM {FQ}.action_log
        )
        SELECT r.id, r.agent_name, r.severity, r.title, r.created_at,
               u.action AS decision_action
        FROM {FQ}.recomendaciones r
        LEFT JOIN ultima u ON u.recommendation_id = r.id AND u.rn = 1
        WHERE r.created_at >= current_timestamp() - INTERVAL 2 HOURS
          AND (r.title ILIKE '%' || {cat_lit} || '%'
               OR r.analysis ILIKE '%' || {cat_lit} || '%'
               OR r.recommendation ILIKE '%' || {cat_lit} || '%')
        ORDER BY r.created_at DESC
        LIMIT 5
    """

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            tot_rows, sen_rows, sku_rows, rec_rows = list(
                pool.map(query, [totales_sql, senales_sql, top_skus_sql, recs_sql])
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    if not tot_rows or not tot_rows[0].get("observaciones"):
        raise HTTPException(status_code=404, detail=f"sin lecturas para la categoría {categoria}")

    t = tot_rows[0]
    obs_cliente = float(t.get("obs_cliente") or 0)
    ejec = float(t["ejecucion_pct"]) if t.get("ejecucion_pct") is not None else 0.0
    disp = float(t["disponibilidad_pct"]) if t.get("disponibilidad_pct") is not None else 0.0
    sos = float(t["sos_pct"]) if t.get("sos_pct") is not None else 0.0
    meta_ejec = float(t.get("meta_ejecucion_pct") or 0)
    meta_disp = float(t.get("meta_disponibilidad_pct") or 0)
    meta_sos = float(t.get("meta_sos_pct") or 0)

    pace = _shrink((ejec / meta_ejec * 100) if meta_ejec else 0.0, obs_cliente)

    s = sen_rows[0] if sen_rows else {}
    senales = {
        "skus_caros": int(s.get("skus_caros") or 0),
        "indice_promedio": float(s.get("indice_promedio") or 0),
        "posts_negativos": int(s.get("posts_negativos") or 0),
        "pdv_con_quiebre": int(s.get("pdv_con_quiebre") or 0),
        "recs_pendientes": sum(1 for r in rec_rows if not r.get("decision_action")),
    }

    top_skus = [
        {
            "sku": r["sku"],
            "producto": r.get("producto"),
            "emoji": r.get("emoji"),
            "marca": r.get("marca"),
            "subcategoria": r.get("subcategoria"),
            "lecturas": int(r.get("lecturas") or 0),
            "disponibilidad_pct": float(r.get("disponibilidad_pct") or 0),
            "planograma_pct": float(r.get("planograma_pct") or 0),
            "facings_prom": float(r.get("facings_prom") or 0),
            "pdv_afectados": int(r.get("pdv_afectados") or 0),
            "precio_sugerido_usd": float(r.get("precio_sugerido_usd") or 0),
            "brecha_pp": round(float(r.get("disponibilidad_pct") or 0) - meta_disp, 1),
        }
        for r in sku_rows
    ]

    recs_activas = [
        {
            "id": r["id"],
            "agent_name": r.get("agent_name"),
            "severity": r.get("severity"),
            "title": r.get("title"),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "decidida": bool(r.get("decision_action")),
        }
        for r in rec_rows
    ]

    payload = {
        "categoria": categoria,
        "ventana_min": WINDOW_MIN,
        "totales": {
            "observaciones": int(t.get("observaciones") or 0),
            "obs_cliente": int(obs_cliente),
            "pdv_medidos": int(t.get("pdv_medidos") or 0),
            "quiebres": int(t.get("quiebres") or 0),
            "disponibilidad_pct": round(disp, 1),
            "ejecucion_pct": round(ejec, 1),
            "planograma_pct": round(float(t.get("planograma_pct") or 0), 1),
            "sos_pct": round(sos, 1),
            "meta_disponibilidad_pct": meta_disp,
            "meta_ejecucion_pct": meta_ejec,
            "meta_sos_pct": meta_sos,
            "brecha_ejecucion_pp": round(ejec - meta_ejec, 1),
            "brecha_disponibilidad_pp": round(disp - meta_disp, 1),
            "brecha_sos_pp": round(sos - meta_sos, 1),
            "cumplimiento_pct": round(pace, 1),
            "status": "above" if pace >= 105 else "on" if pace >= 95 else "behind",
        },
        "senales": senales,
        "top_skus": top_skus,
        "recomendaciones_activas": recs_activas,
    }
    _cache_set(cache_key, payload)
    _prefetch_top_skus_async(categoria, top_skus)
    return payload


def _prefetch_top_skus_async(categoria: str, top_skus: list[dict]) -> None:
    """Calienta en background la ficha de los peores SKUs.

    Para cuando el usuario expande uno en el panel, la respuesta ya está en
    cache. Best-effort: cualquier fallo se traga, nunca afecta al diagnóstico.
    """
    skus = [s.get("sku") for s in top_skus[:PREFETCH_TOP_N] if s.get("sku")]
    if not skus:
        return

    def warm_one(sku: str):
        try:
            if _cache_get(f"sku:{categoria}:{sku}") is None:
                sku_detalle(categoria, sku)
        except Exception:
            pass

    def worker():
        with ThreadPoolExecutor(max_workers=3) as pool:
            pool.map(warm_one, skus)

    threading.Thread(target=worker, daemon=True).start()


@router.get("/api/targets/{categoria}/diagnose")
def diagnose(categoria: str):
    """Diagnóstico determinístico de por qué la categoría está bajo meta."""
    return _collect_diagnosis(categoria)


# ---- Explicación del LLM -----------------------------------------------------

EXPLAIN_SYSTEM_PROMPT = f"""Eres analista senior de dichter & neira, la firma de \
investigación de mercados que audita la ejecución en el punto de venta para marcas de \
consumo masivo en Centroamérica, el Caribe y la región andina. Tu cliente en este \
estudio es {CLIENTE}.

Recibes el snapshot de una categoría: disponibilidad en anaquel (OSA), ejecución perfecta, \
share of shelf, quiebres por PDV, señales de precio e índice social, y los SKUs con peor \
desempeño.

Produce un análisis breve para el comité de la marca, en español latinoamericano, con:

1. **Por qué estamos bajo meta** — 2 o 3 frases con la causa raíz más probable de la brecha, \
citando las señales concretas del JSON. Distingue si el problema es de reposición (el producto \
no está), de exhibición (está pero mal exhibido) o de espacio negociado (share of shelf).

2. **Qué hacer ahora** — 3 a 5 acciones priorizadas, en imperativo, dirigidas a la fuerza de \
campo o al equipo comercial. Nombra SKUs y PDV reales de la lista cuando aplique.

Restricciones:
- Usa SOLO cifras y SKUs que aparecen en el JSON. Nunca inventes.
- Español latinoamericano, tono ejecutivo.
- Markdown con exactamente dos encabezados: `## Por qué estamos bajo meta` y `## Qué hacer ahora`.
- Sin introducción ni cierre. Máximo 300 palabras.
"""


def _sse_event(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/api/targets/{categoria}/explain")
def explain(categoria: str):
    """Análisis del LLM en streaming (SSE).

    Emite `diagnosis` (el snapshot determinístico, inmediato), luego `delta` por
    cada token y finalmente `done`. Ante un fallo emite `error` y cierra.
    """
    diagnosis = _collect_diagnosis(categoria)

    def generator():
        yield _sse_event("diagnosis", diagnosis)
        client = get_openai_client()
        t0 = time.monotonic()
        try:
            stream = client.chat.completions.create(
                model=EXPLAIN_LLM_ENDPOINT,
                messages=[
                    {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
                    {"role": "user", "content":
                        f"Categoría: {categoria}\nVentana: últimos {WINDOW_MIN} minutos\n\n"
                        f"Datos (JSON):\n```json\n"
                        f"{json.dumps(diagnosis, ensure_ascii=False, default=str, indent=2)}\n```"},
                ],
                temperature=0.3,
                max_tokens=600,
                stream=True,
            )
            for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                token = getattr(chunk.choices[0].delta, "content", None)
                if token:
                    yield _sse_event("delta", {"text": token})
        except Exception as exc:  # noqa: BLE001
            yield _sse_event("error", {"detail": f"LLM stream failed: {exc}"})
            return
        yield _sse_event(
            "done",
            {"elapsed_ms": int((time.monotonic() - t0) * 1000), "model": EXPLAIN_LLM_ENDPOINT},
        )

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---- Ficha de SKU ------------------------------------------------------------

@router.get("/api/targets/{categoria}/sku/{sku}/detalle")
def sku_detalle(categoria: str, sku: str):
    """Ficha de un SKU dentro del drill-down.

    Consolida cinco sub-consultas en un solo round-trip con UNION ALL y payloads
    JSON; el backend las separa por sección. Cacheada, así reabrir es instantáneo.
    """
    cache_key = f"sku:{categoria}:{sku}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    cat_lit = _sql_str(categoria)
    sku_lit = _sql_str(sku)

    consolidado_sql = f"""
        SELECT 'producto' AS seccion, to_json(named_struct(
                 'nombre', nombre, 'marca', marca, 'fabricante', fabricante,
                 'subcategoria', subcategoria, 'presentacion', presentacion,
                 'emoji', emoji,
                 'contenido_norm', CAST(contenido_norm AS DOUBLE),
                 'unidad_norm', unidad_norm,
                 'precio_sugerido_usd', CAST(precio_sugerido_usd AS DOUBLE)
               )) AS payload
        FROM {FQ}.productos
        WHERE sku = {sku_lit} AND categoria = {cat_lit}

        UNION ALL

        SELECT 'anaquel', to_json(named_struct(
                 'lecturas', COUNT(*),
                 'pdv', COUNT(DISTINCT store_id),
                 'disponibilidad_pct', ROUND(AVG(CAST(en_stock AS INT)) * 100, 1),
                 'planograma_pct',     ROUND(AVG(CAST(planograma_ok AS INT)) * 100, 1),
                 'promo_pct',          ROUND(AVG(CAST(en_promo AS INT)) * 100, 1),
                 'facings_prom',       ROUND(AVG(facings), 1),
                 'precio_usd_prom',    ROUND(AVG(precio_usd), 2)
               ))
        FROM {FQ}.visitas
        WHERE sku = {sku_lit}
          AND visit_ts >= current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES

        UNION ALL

        SELECT 'serie', to_json(named_struct(
                 'minute_ts', date_trunc('minute', visit_ts),
                 'disponibilidad_pct', ROUND(AVG(CAST(en_stock AS INT)) * 100, 1),
                 'lecturas', COUNT(*)
               ))
        FROM {FQ}.visitas
        WHERE sku = {sku_lit}
          AND visit_ts >= current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES
        GROUP BY date_trunc('minute', visit_ts)

        UNION ALL

        SELECT 'peores_pdv', to_json(named_struct(
                 'store_id', v.store_id, 'tienda', t.nombre, 'cadena', t.cadena,
                 'ciudad', t.ciudad, 'country_code', t.country_code,
                 'mercaderista', t.mercaderista,
                 'disponibilidad_pct', ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1),
                 'lecturas', COUNT(*)
               ))
        FROM {FQ}.visitas v
        JOIN {FQ}.tiendas t ON t.store_id = v.store_id
        WHERE v.sku = {sku_lit}
          AND v.visit_ts >= current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES
        GROUP BY v.store_id, t.nombre, t.cadena, t.ciudad, t.country_code, t.mercaderista
        HAVING AVG(CAST(v.en_stock AS INT)) < 0.9

        UNION ALL

        SELECT 'precio', to_json(named_struct(
                 'country_code', country_code, 'cadena', cadena,
                 'precio_usd', CAST(precio_usd AS DOUBLE),
                 'indice_precio', CAST(indice_precio AS DOUBLE),
                 'en_promo', en_promo
               ))
        FROM (
          SELECT country_code, cadena, precio_usd, indice_precio, en_promo,
                 ROW_NUMBER() OVER (PARTITION BY country_code, cadena
                                    ORDER BY snapshot_ts DESC) AS rn
          FROM {FQ}.precios_competencia
          WHERE sku = {sku_lit}
            AND snapshot_ts >= current_timestamp() - INTERVAL 60 MINUTES
        )
        WHERE rn = 1
    """

    try:
        rows = query(consolidado_sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    secciones: dict[str, list[dict]] = {
        "producto": [], "anaquel": [], "serie": [], "peores_pdv": [], "precio": [],
    }
    for r in rows:
        seccion, payload = r.get("seccion"), r.get("payload")
        if seccion in secciones and payload:
            try:
                secciones[seccion].append(json.loads(payload))
            except json.JSONDecodeError:
                pass

    if not secciones["producto"]:
        raise HTTPException(status_code=404, detail=f"SKU {sku} no encontrado en {categoria}")

    secciones["serie"].sort(key=lambda x: x.get("minute_ts") or "")
    secciones["peores_pdv"].sort(key=lambda x: x.get("disponibilidad_pct") or 0)
    secciones["precio"].sort(key=lambda x: -(x.get("indice_precio") or 0))

    result = {
        "sku": sku,
        "categoria": categoria,
        "producto": secciones["producto"][0],
        "anaquel": secciones["anaquel"][0] if secciones["anaquel"] else {},
        "serie": secciones["serie"],
        "peores_pdv": secciones["peores_pdv"][:8],
        "precio": secciones["precio"][:8],
    }
    _cache_set(cache_key, result)
    return result


# ---- Acciones a nivel categoría ----------------------------------------------

ACCIONES_PERMITIDAS = {
    "priorizar_visitas",     # reordenar la ruta de campo hacia los PDV en rojo
    "corregir_planograma",   # brief de exhibición a la agencia de trade
    "negociar_espacio",      # abrir negociación de espacio con la cadena
    "revisar_precio",        # pasar el caso al equipo comercial
    "escalar_equipo",        # subir el tema al comité de la marca
}


class AccionCategoria(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=40)
    params: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


def _sql_or_null(s: Optional[str]) -> str:
    return "NULL" if s is None else "'" + s.replace("'", "''") + "'"


@router.post("/api/targets/{categoria}/actions")
def submit_action(categoria: str, body: AccionCategoria, request: Request):
    """Registra una decisión tomada desde el drill-down de la categoría.

    Se guarda en `action_log` con recommendation_id = "cat:{categoria}", lo que
    la distingue de las decisiones sobre recomendaciones individuales.
    """
    if body.action_type not in ACCIONES_PERMITIDAS:
        raise HTTPException(status_code=400, detail=f"acción no soportada: {body.action_type}")

    actor = get_current_user_email(request)
    log_id = f"act_{uuid.uuid4().hex[:14]}"
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")

    notas: dict[str, Any] = {"categoria": categoria}
    if body.params:
        notas["params"] = body.params
    if body.notes:
        notas["notes"] = body.notes

    sql = f"""
        INSERT INTO {FQ}.action_log
          (id, recommendation_id, action, actor, notes, occurred_at)
        VALUES (
          '{log_id}', {_sql_or_null(f"cat:{categoria}")},
          '{body.action_type.upper()}', {_sql_or_null(actor)},
          {_sql_or_null(json.dumps(notas, ensure_ascii=False, default=str))},
          '{now_iso}'
        )
    """
    try:
        execute(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"action insert failed: {exc}") from exc

    return {
        "ok": True, "log_id": log_id, "categoria": categoria,
        "action": body.action_type.upper(), "actor": actor, "occurred_at": now_iso,
    }
