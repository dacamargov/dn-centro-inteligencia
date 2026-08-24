"""Copiloto de campo sobre Lakebase — sugerencias al mercaderista en <100 ms.

El escenario: el mercaderista llega a un PDV, abre la app en el celular y
necesita saber, antes de caminar al anaquel, qué corregir primero. Esa llamada
tiene presupuesto de aplicación, no de reporte: si tarda un segundo, deja de
usarla y vuelve a trabajar de memoria.

Reparto de responsabilidades, que es el punto de la demo:
  * Unity Catalog / Delta → historia completa, analítica, entrenamiento.
  * Lakebase / Postgres   → lectura por clave del perfil del PDV, a latencia
    de aplicación, con la misma gobernanza del lakehouse.

El catálogo de SKUs se mantiene en memoria y se refresca en background. Es dato
casi estático que en producción llegaría por synced table; lo importante es que
recargarlo NUNCA ocurra dentro del cronómetro, porque un round-trip al warehouse
(~300-900 ms) envenenaría el p95 y el p99 de toda la sesión.

Endpoints:
  GET  /api/lakebase/status
  GET  /api/lakebase/pdv                — universo de PDV con su perfil
  GET  /api/lakebase/pdv/{store_id}     — perfil + últimas sugerencias
  POST /api/lakebase/sugerir            — camino caliente
  GET  /api/lakebase/recientes
  GET  /api/lakebase/sugerencia/{id}
  GET  /api/lakebase/stats              — p50 / p95 / p99
  GET  /api/lakebase/impacto            — lectura de negocio del log
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import CLIENTE, FQ
from ..lakebase import connect, is_configured
from ..uc import query as uc_query

log = logging.getLogger(__name__)
router = APIRouter()

PG_SCHEMA = "campo"

# Catálogo en memoria, particionado por categoría para rerankear rápido.
_catalogo_por_categoria: dict[str, list[dict]] = {}
_catalogo_por_sku: dict[str, dict] = {}
_catalogo_ultima_carga: float = 0.0
_CATALOGO_TTL_S = 900.0
_catalogo_lock = threading.Lock()
_catalogo_refrescando = False


def _check_configured():
    if not is_configured():
        raise HTTPException(status_code=503, detail="Lakebase no configurado")


# ---------------------------------------------------------------------------
# Cache del catálogo
# ---------------------------------------------------------------------------

def _cargar_catalogo_bloqueante() -> None:
    """Lee el catálogo entero en UNA consulta y cambia el cache de golpe."""
    global _catalogo_ultima_carga, _catalogo_por_categoria, _catalogo_por_sku
    sql = f"""
        SELECT sku, nombre, marca, fabricante, categoria, subcategoria,
               presentacion, emoji, es_cliente,
               CAST(precio_sugerido_usd AS DOUBLE) AS precio_usd,
               CAST(contenido_norm AS DOUBLE)      AS contenido_norm,
               unidad_norm
        FROM {FQ}.productos
    """
    try:
        rows = uc_query(sql)
    except Exception as exc:  # noqa: BLE001
        log.warning("carga de catálogo falló: %s", exc)
        return

    por_cat: dict[str, list[dict]] = {}
    por_sku: dict[str, dict] = {}
    for r in rows:
        item = {
            "sku": r["sku"],
            "nombre": r.get("nombre"),
            "marca": r.get("marca"),
            "fabricante": r.get("fabricante"),
            "categoria": r.get("categoria"),
            "subcategoria": r.get("subcategoria"),
            "presentacion": r.get("presentacion"),
            "emoji": r.get("emoji"),
            "es_cliente": bool(r.get("es_cliente")),
            "precio_usd": float(r.get("precio_usd") or 0),
            "contenido_norm": float(r.get("contenido_norm") or 0),
            "unidad_norm": r.get("unidad_norm"),
        }
        por_sku[item["sku"]] = item
        por_cat.setdefault(item["categoria"] or "?", []).append(item)

    for items in por_cat.values():
        items.sort(key=lambda x: -x["precio_usd"])

    # Swap atómico por rebind: ningún lector ve estado parcial.
    _catalogo_por_categoria = por_cat
    _catalogo_por_sku = por_sku
    _catalogo_ultima_carga = time.monotonic()


def _refrescar_catalogo_async() -> None:
    global _catalogo_refrescando
    with _catalogo_lock:
        if _catalogo_refrescando:
            return
        _catalogo_refrescando = True

    def _worker():
        global _catalogo_refrescando
        try:
            _cargar_catalogo_bloqueante()
        finally:
            with _catalogo_lock:
                _catalogo_refrescando = False

    threading.Thread(target=_worker, name="catalogo-refresh", daemon=True).start()


def _catalogo() -> dict[str, list[dict]]:
    """Catálogo por categoría, sin bloquear cuando ya hay cache (aunque sea viejo).

    Solo la primerísima carga es síncrona, y el pre-warm del arranque
    normalmente ya la cubrió.
    """
    if _catalogo_por_categoria:
        if (time.monotonic() - _catalogo_ultima_carga) >= _CATALOGO_TTL_S:
            _refrescar_catalogo_async()
        return _catalogo_por_categoria
    with _catalogo_lock:
        if _catalogo_por_categoria:
            return _catalogo_por_categoria
    _cargar_catalogo_bloqueante()
    return _catalogo_por_categoria


def prewarm() -> None:
    """Calienta el cache al arrancar el app, en background y sin frenar el boot."""
    _refrescar_catalogo_async()


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

@router.get("/api/lakebase/status")
def status():
    _check_configured()
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                      (SELECT COUNT(*) FROM {PG_SCHEMA}.pdv_perfiles),
                      (SELECT COUNT(*) FROM {PG_SCHEMA}.sugerencias_log),
                      (SELECT MAX(served_at) FROM {PG_SCHEMA}.sugerencias_log),
                      version()
                """)
                row = cur.fetchone() or (0, 0, None, None)
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s ORDER BY table_name",
                    (PG_SCHEMA,),
                )
                tablas = [r[0] for r in cur.fetchall()]
                cur.execute("SELECT current_user")
                conectado_como = cur.fetchone()[0]
        return {
            "configured": True,
            "host": os.environ.get("LAKEBASE_HOST"),
            "database": os.environ.get("LAKEBASE_DB"),
            "schema": PG_SCHEMA,
            "tables": tablas,
            "connected_as": conectado_como,
            "postgres_version": (row[3].split(",")[0] if row[3] else None),
            "counts": {
                "pdv_perfiles": int(row[0] or 0),
                "sugerencias_servidas": int(row[1] or 0),
            },
            "ultima_sugerencia_at": row[2].isoformat() if row[2] else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Lakebase status falló: {exc}") from exc


# ---------------------------------------------------------------------------
# /pdv — universo y ficha
# ---------------------------------------------------------------------------

_PERFIL_COLS = """store_id, nombre, canal, cadena, formato, ciudad, country_code,
                  pais, mercaderista, visitas_mes_meta, categorias_prioritarias,
                  skus_foco, disponibilidad_hist, ejecucion_hist, sos_hist,
                  riesgo_quiebre, ticket_categoria_usd, ultima_visita"""


def _row_to_perfil(r) -> dict:
    return {
        "store_id": r[0], "nombre": r[1], "canal": r[2], "cadena": r[3],
        "formato": r[4], "ciudad": r[5], "country_code": r[6], "pais": r[7],
        "mercaderista": r[8], "visitas_mes_meta": int(r[9] or 0),
        "categorias_prioritarias": list(r[10] or []),
        "skus_foco": list(r[11] or []),
        "disponibilidad_hist": float(r[12] or 0),
        "ejecucion_hist": float(r[13] or 0),
        "sos_hist": float(r[14] or 0),
        "riesgo_quiebre": float(r[15] or 0),
        "ticket_categoria_usd": float(r[16] or 0),
        "ultima_visita": r[17].isoformat() if r[17] else None,
    }


@router.get("/api/lakebase/pdv")
def list_pdv(
    q: Optional[str] = Query(None, description="busca en store_id, nombre o ciudad"),
    canal: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    _check_configured()
    where, params = [], []
    if q:
        where.append("(store_id ILIKE %s OR nombre ILIKE %s OR ciudad ILIKE %s)")
        params.extend([f"%{q}%"] * 3)
    if canal:
        where.append("canal = %s")
        params.append(canal)
    if country_code:
        where.append("country_code = %s")
        params.append(country_code)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_PERFIL_COLS} FROM {PG_SCHEMA}.pdv_perfiles "
                    f"{where_sql} ORDER BY riesgo_quiebre DESC LIMIT %s",
                    params,
                )
                rows = cur.fetchall()
        return [_row_to_perfil(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"listar PDV falló: {exc}") from exc


@router.get("/api/lakebase/pdv/{store_id}")
def get_pdv(store_id: str):
    _check_configured()
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_PERFIL_COLS} FROM {PG_SCHEMA}.pdv_perfiles WHERE store_id = %s",
                    (store_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"PDV {store_id} no encontrado")
                cur.execute(
                    f"SELECT id, categoria_foco, skus, rationale, impacto_usd, "
                    f"latency_ms, served_at FROM {PG_SCHEMA}.sugerencias_log "
                    f"WHERE store_id = %s ORDER BY served_at DESC LIMIT 5",
                    (store_id,),
                )
                recientes = cur.fetchall()
        perfil = _row_to_perfil(row)
        perfil["sugerencias_recientes"] = [
            {
                "id": int(r[0]), "categoria_foco": r[1], "skus": list(r[2] or []),
                "rationale": r[3], "impacto_usd": float(r[4] or 0),
                "latency_ms": int(r[5]),
                "served_at": r[6].isoformat() if r[6] else None,
            }
            for r in recientes
        ]
        return perfil
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"detalle PDV falló: {exc}") from exc


# ---------------------------------------------------------------------------
# /sugerir — el camino caliente
# ---------------------------------------------------------------------------

class SugerirRequest(BaseModel):
    store_id: str
    categoria: Optional[str] = None
    n: int = Field(4, ge=1, le=10)


# Rotación diaria asumida por cara — mismo supuesto que /api/campo/acciones,
# para que los dos paneles cuenten la misma historia de plata.
UNIDADES_DIA_POR_FACING = 3.0


@router.post("/api/lakebase/sugerir")
def sugerir(body: SugerirRequest):
    """Devuelve las acciones priorizadas para el PDV, cronometrando el camino real.

    El cronómetro arranca DESPUÉS de abrir la conexión y de tener el catálogo en
    memoria: eso es lo que en producción sería un pool caliente y una synced
    table. Lo que se mide es lo que se paga por request: la lectura por clave del
    perfil en Postgres más el ranking.
    """
    _check_configured()
    _catalogo()  # fuera del cronómetro, a propósito

    try:
        with connect() as conn:
            t0 = time.perf_counter()
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_PERFIL_COLS} FROM {PG_SCHEMA}.pdv_perfiles WHERE store_id = %s",
                    (body.store_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=404, detail=f"PDV {body.store_id} no encontrado"
                    )
                perfil = _row_to_perfil(row)

                categoria = body.categoria or _categoria_foco(perfil)
                candidatos = _candidatos(perfil, categoria, n=body.n * 6)
                acciones = _rankear(candidatos, perfil, categoria, body.n)
                escenario = _escenario(perfil, categoria)
                rationale = _rationale(perfil, categoria, acciones)
                impacto = round(sum(a["impacto_usd"] for a in acciones), 2)

                elapsed_ms = int((time.perf_counter() - t0) * 1000)

                cur.execute(
                    f"""
                    INSERT INTO {PG_SCHEMA}.sugerencias_log
                      (store_id, categoria_foco, acciones, skus, rationale,
                       impacto_usd, latency_ms, mercaderista, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'servida')
                    RETURNING id, served_at
                    """,
                    (
                        body.store_id, categoria,
                        json.dumps(acciones, ensure_ascii=False),
                        [a["sku"] for a in acciones],
                        rationale, impacto, elapsed_ms,
                        perfil.get("mercaderista"),
                    ),
                )
                sug_id, served_at = cur.fetchone()
            conn.commit()

        return {
            "ok": True,
            "sugerencia_id": int(sug_id),
            "served_at": served_at.isoformat() if served_at else None,
            "latency_ms": elapsed_ms,
            "pdv": perfil,
            "categoria_foco": categoria,
            "categoria_source": "usuario" if body.categoria else "perfil",
            "escenario": escenario,
            "acciones": acciones,
            "impacto_usd": impacto,
            "rationale": rationale,
            "estado": "servida",
            "mercaderista": perfil.get("mercaderista"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"sugerir falló: {exc}") from exc


def _categoria_foco(perfil: dict) -> Optional[str]:
    """Categoría sobre la que trabajar en esta visita.

    Determinística por store_id: el mismo PDV abre siempre con la misma
    categoría, que es como se comporta una ruta de campo real.
    """
    prioritarias = perfil.get("categorias_prioritarias") or []
    if prioritarias:
        rng = random.Random(hash(perfil["store_id"]) & 0xFFFFFFFF)
        return rng.choice(prioritarias)
    cat = _catalogo()
    return next(iter(cat), None)


def _candidatos(perfil: dict, categoria: Optional[str], n: int) -> List[dict]:
    """SKUs del cliente candidatos a corrección, empezando por la categoría foco."""
    por_cat = _catalogo()
    orden: list[str] = []
    if categoria:
        orden.append(categoria)
    for c in perfil.get("categorias_prioritarias") or []:
        if c not in orden:
            orden.append(c)
    if not orden:
        orden = list(por_cat.keys())

    items, vistos = [], set()
    for c in orden:
        for item in por_cat.get(c, []):
            if item["sku"] in vistos or not item["es_cliente"]:
                continue
            items.append(item)
            vistos.add(item["sku"])
            if len(items) >= n:
                return items
    return items


# Cada tipo de acción vale distinto: un quiebre cuesta la venta completa, un
# planograma mal armado cuesta una fracción, y ampliar espacio es apuesta a futuro.
_PESO_ACCION = {"reponer": 1.0, "corregir_planograma": 0.45, "ampliar_espacio": 0.25}


def _rankear(candidatos: List[dict], perfil: dict, categoria: Optional[str],
             top_n: int) -> List[dict]:
    """Ordena las acciones por impacto esperado en dólares.

    El score combina el riesgo histórico de quiebre del PDV, si el SKU está en
    la lista de foco del perfil, y el precio del producto. En producción este
    ranking sería un modelo servido desde el mismo Lakebase; la forma del
    contrato (features por clave → score) es idéntica.
    """
    foco = set(perfil.get("skus_foco") or [])
    riesgo = float(perfil.get("riesgo_quiebre") or 0.2)
    ejecucion = float(perfil.get("ejecucion_hist") or 70) / 100.0
    rng = random.Random(hash(perfil["store_id"]) & 0xFFFFFFFF)

    resultados = []
    for c in candidatos:
        # El tipo de acción sale del punto más débil del PDV: si históricamente
        # falla la reposición, la primera acción es reponer; si falla la
        # exhibición, es corregir el planograma.
        r = rng.random()
        if r < riesgo:
            tipo = "reponer"
        elif ejecucion < 0.8:
            tipo = "corregir_planograma"
        else:
            tipo = "ampliar_espacio"

        peso = _PESO_ACCION[tipo]
        impacto = c["precio_usd"] * UNIDADES_DIA_POR_FACING * peso * (0.6 + riesgo)
        score = impacto
        if c["sku"] in foco:
            score *= 2.0
        if categoria and c["categoria"] == categoria:
            score *= 1.5

        resultados.append((score, {
            **c,
            "tipo_accion": tipo,
            "impacto_usd": round(impacto, 2),
            "score": round(score, 3),
            "en_foco": c["sku"] in foco,
        }))

    resultados.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in resultados[:top_n]]


def _escenario(perfil: dict, categoria: Optional[str]) -> dict:
    """Encuadre de la visita, según qué tan mal viene el PDV."""
    ejec = float(perfil.get("ejecucion_hist") or 0)
    nombre = perfil.get("nombre") or perfil["store_id"]
    if ejec < 55:
        return {
            "code": "critico",
            "headline": "PDV crítico — ejecución muy por debajo de meta",
            "narrative": (
                f"{nombre} viene con {ejec:.0f}% de ejecución perfecta. La visita "
                f"debe cerrar los quiebres de {categoria} antes que cualquier otra cosa."
            ),
        }
    if ejec < 75:
        return {
            "code": "riesgo",
            "headline": f"Ejecución en riesgo · {ejec:.0f}%",
            "narrative": (
                f"{nombre} está por debajo de meta en {categoria}. Hay margen de "
                f"recuperación en la visita de hoy si se prioriza bien el anaquel."
            ),
        }
    if float(perfil.get("sos_hist") or 0) < 30:
        return {
            "code": "espacio",
            "headline": "Ejecución sana, espacio corto",
            "narrative": (
                f"{nombre} ejecuta bien pero {CLIENTE} tiene poco espacio en "
                f"{categoria}. La conversación de hoy es de negociación, no de reposición."
            ),
        }
    return {
        "code": "mantenimiento",
        "headline": "PDV en meta — visita de mantenimiento",
        "narrative": (
            f"{nombre} viene cumpliendo. Las sugerencias son de refinamiento: "
            f"asegurar el frente de anaquel y no perder terreno."
        ),
    }


def _rationale(perfil: dict, categoria: Optional[str], acciones: List[dict]) -> str:
    partes = [f"canal {perfil.get('canal')}", f"cadena {perfil.get('cadena')}"]
    if categoria:
        partes.append(f"foco {categoria}")
    partes.append(f"ejecución histórica {float(perfil.get('ejecucion_hist') or 0):.0f}%")
    partes.append(f"riesgo de quiebre {float(perfil.get('riesgo_quiebre') or 0):.0%}")
    if acciones:
        tipos = {a["tipo_accion"] for a in acciones}
        partes.append("acciones: " + ", ".join(sorted(tipos)))
    return " · ".join(partes)


# ---------------------------------------------------------------------------
# /ejecutar — el otro extremo del ciclo
# ---------------------------------------------------------------------------

class EjecutarRequest(BaseModel):
    """Lo que el mercaderista reporta al cerrar la visita.

    `skus_ejecutados` vacío significa que cerró sin hacer nada del plan, que es
    un dato tan valioso como la ejecución: es la señal de que el plan no servía.
    """
    skus_ejecutados: List[str] = Field(default_factory=list)
    nota: Optional[str] = None


@router.post("/api/lakebase/sugerencia/{sug_id}/ejecutar")
def ejecutar(sug_id: int, body: EjecutarRequest):
    """Cierra la visita: registra qué se corrigió de lo que se había sugerido.

    Esto es lo que convierte la demo en un ciclo y no en un generador de
    sugerencias: el impacto ejecutado se calcula sumando solo las acciones que
    de verdad se hicieron, así la tasa de ejecución del panel es una medición y
    no un supuesto.
    """
    _check_configured()
    hechos = {s for s in body.skus_ejecutados if s}
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT acciones, impacto_usd, estado FROM {PG_SCHEMA}.sugerencias_log "
                    f"WHERE id = %s",
                    (sug_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"sugerencia {sug_id} no existe")
                if row[2] != "servida":
                    raise HTTPException(
                        status_code=409,
                        detail=f"la sugerencia {sug_id} ya está {row[2]}",
                    )

                acciones = row[0] if isinstance(row[0], list) else json.loads(row[0] or "[]")
                validos = {a["sku"] for a in acciones}
                hechos &= validos     # no se acredita lo que nunca se sugirió
                impacto_hecho = round(
                    sum(float(a.get("impacto_usd") or 0) for a in acciones if a["sku"] in hechos),
                    2,
                )
                if not hechos:
                    estado = "omitida"
                elif hechos == validos:
                    estado = "ejecutada"
                else:
                    estado = "parcial"

                cur.execute(
                    f"""
                    UPDATE {PG_SCHEMA}.sugerencias_log
                    SET estado = %s, skus_ejecutados = %s, impacto_ejecutado_usd = %s,
                        ejecutado_at = NOW(), nota_cierre = %s
                    WHERE id = %s
                    RETURNING ejecutado_at
                    """,
                    (estado, sorted(hechos), impacto_hecho, body.nota, sug_id),
                )
                ejecutado_at = cur.fetchone()[0]
            conn.commit()
        return {
            "ok": True,
            "id": sug_id,
            "estado": estado,
            "skus_ejecutados": sorted(hechos),
            "acciones_totales": len(validos),
            "impacto_ejecutado_usd": impacto_hecho,
            "impacto_sugerido_usd": float(row[1] or 0),
            "ejecutado_at": ejecutado_at.isoformat() if ejecutado_at else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ejecutar falló: {exc}") from exc


# ---------------------------------------------------------------------------
# /recientes + /sugerencia/{id}
# ---------------------------------------------------------------------------

@router.get("/api/lakebase/recientes")
def recientes(
    limit: int = Query(20, ge=1, le=100),
    estado: Optional[str] = Query(None, description="servida | ejecutada | parcial | omitida"),
):
    _check_configured()
    where = "WHERE l.estado = %s" if estado else ""
    params = ([estado] if estado else []) + [limit]
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT l.id, l.store_id, p.nombre, p.canal, p.cadena, p.ciudad,
                           l.categoria_foco, l.skus, l.impacto_usd, l.latency_ms, l.served_at,
                           l.estado, l.skus_ejecutados, l.impacto_ejecutado_usd,
                           l.ejecutado_at, COALESCE(l.mercaderista, p.mercaderista)
                    FROM {PG_SCHEMA}.sugerencias_log l
                    JOIN {PG_SCHEMA}.pdv_perfiles p ON p.store_id = l.store_id
                    {where}
                    ORDER BY l.served_at DESC
                    LIMIT %s
                """, params)
                rows = cur.fetchall()
        return [
            {
                "id": int(r[0]), "store_id": r[1], "nombre": r[2], "canal": r[3],
                "cadena": r[4], "ciudad": r[5], "categoria_foco": r[6],
                "skus": list(r[7] or []), "impacto_usd": float(r[8] or 0),
                "latency_ms": int(r[9]),
                "served_at": r[10].isoformat() if r[10] else None,
                "estado": r[11] or "servida",
                "skus_ejecutados": list(r[12] or []),
                "impacto_ejecutado_usd": float(r[13] or 0),
                "ejecutado_at": r[14].isoformat() if r[14] else None,
                "mercaderista": r[15],
            }
            for r in rows
        ]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"recientes falló: {exc}") from exc


@router.get("/api/lakebase/sugerencia/{sug_id}")
def get_sugerencia(sug_id: int):
    _check_configured()
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT l.id, l.store_id, l.categoria_foco, l.acciones, l.rationale,
                           l.impacto_usd, l.latency_ms, l.served_at,
                           {", ".join("p." + c.strip() for c in _PERFIL_COLS.split(","))}
                    FROM {PG_SCHEMA}.sugerencias_log l
                    JOIN {PG_SCHEMA}.pdv_perfiles p ON p.store_id = l.store_id
                    WHERE l.id = %s
                """, (sug_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"sugerencia {sug_id} no existe")

        acciones = row[3] if isinstance(row[3], list) else json.loads(row[3] or "[]")
        perfil = _row_to_perfil(row[8:])
        return {
            "id": int(row[0]),
            "store_id": row[1],
            "categoria_foco": row[2],
            "acciones": acciones,
            "rationale": row[4],
            "impacto_usd": float(row[5] or 0),
            "latency_ms": int(row[6]),
            "served_at": row[7].isoformat() if row[7] else None,
            "escenario": _escenario(perfil, row[2]),
            "pdv": perfil,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"detalle de sugerencia falló: {exc}") from exc


# ---------------------------------------------------------------------------
# /stats — observabilidad del SLA
# ---------------------------------------------------------------------------

# Los percentiles se calculan sobre las llamadas recientes, no sobre la historia
# completa: sin ventana, un pico viejo (el cold start de una sesión anterior)
# queda clavado en el p99 para siempre.
_SLA_VENTANA_MIN = 30
_SLA_MAX_FILAS = 500


@router.get("/api/lakebase/stats")
def stats():
    _check_configured()
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    WITH recientes AS (
                        SELECT latency_ms FROM {PG_SCHEMA}.sugerencias_log
                        WHERE served_at >= NOW() - INTERVAL '{_SLA_VENTANA_MIN} minutes'
                        ORDER BY served_at DESC
                        LIMIT {_SLA_MAX_FILAS}
                    ),
                    respaldo AS (
                        SELECT latency_ms FROM {PG_SCHEMA}.sugerencias_log
                        ORDER BY served_at DESC LIMIT 100
                    ),
                    ventana AS (
                        SELECT * FROM recientes
                        UNION ALL
                        SELECT * FROM respaldo WHERE NOT EXISTS (SELECT 1 FROM recientes)
                    )
                    SELECT
                      COUNT(*),
                      COALESCE(ROUND(AVG(latency_ms)), 0)::int,
                      COALESCE(PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY latency_ms), 0)::int,
                      COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)::int,
                      COALESCE(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms), 0)::int,
                      COALESCE(MIN(latency_ms), 0),
                      COALESCE(MAX(latency_ms), 0)
                    FROM ventana
                """)
                r = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0)
                cur.execute(
                    f"SELECT COUNT(*) FROM {PG_SCHEMA}.sugerencias_log "
                    f"WHERE served_at >= NOW() - INTERVAL '5 minutes'"
                )
                ultimos_5min = cur.fetchone()[0]
        return {
            "n": int(r[0] or 0),
            "mean_ms": int(r[1] or 0),
            "p50_ms": int(r[2] or 0),
            "p95_ms": int(r[3] or 0),
            "p99_ms": int(r[4] or 0),
            "min_ms": int(r[5] or 0),
            "max_ms": int(r[6] or 0),
            "last_5min": int(ultimos_5min or 0),
            "window_min": _SLA_VENTANA_MIN,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"stats falló: {exc}") from exc


# ---------------------------------------------------------------------------
# /flujo — la rueda de visitas del lado del servidor
# ---------------------------------------------------------------------------

class FlujoRequest(BaseModel):
    activo: bool
    ritmo_por_min: float = Field(6.0, ge=0.5, le=60)


@router.get("/api/lakebase/flujo")
def flujo_estado():
    from ..campo_flujo import flujo
    return flujo.estado()


@router.post("/api/lakebase/flujo")
def flujo_control(body: FlujoRequest):
    """Enciende o apaga la jornada simulada de la red."""
    _check_configured()
    from ..campo_flujo import flujo

    if body.activo:
        flujo.arrancar(body.ritmo_por_min)
    else:
        flujo.detener()
    return flujo.estado()


# ---------------------------------------------------------------------------
# /impacto — lectura de negocio del log
# ---------------------------------------------------------------------------

# Contrafactual: cuánto se corregiría sin la lista priorizada, trabajando de
# memoria. Este sí es un supuesto y se expone como tal — el cliente debe poder
# discutirlo. La tasa CON copiloto ya no se supone: se mide contra el log.
TASA_BASE_SIN_COPILOTO = 0.24


@router.get("/api/lakebase/impacto")
def impacto():
    """Traduce el log a recuperación de venta, con la ejecución realmente medida."""
    _check_configured()
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                      COUNT(*),
                      COUNT(*) FILTER (WHERE served_at >= NOW() - INTERVAL '24 hours'),
                      COUNT(*) FILTER (WHERE served_at >= NOW() - INTERVAL '5 minutes'),
                      COALESCE(SUM(impacto_usd), 0),
                      COALESCE(SUM(impacto_usd) FILTER
                               (WHERE served_at >= NOW() - INTERVAL '24 hours'), 0),
                      COUNT(DISTINCT store_id),
                      -- Ciclo cerrado: solo las visitas ya reportadas cuentan para
                      -- la tasa, porque las servidas hace diez segundos todavía no
                      -- tuvieron oportunidad de ejecutarse.
                      COUNT(*) FILTER (WHERE estado <> 'servida'),
                      COUNT(*) FILTER (WHERE estado = 'ejecutada'),
                      COUNT(*) FILTER (WHERE estado = 'parcial'),
                      COUNT(*) FILTER (WHERE estado = 'omitida'),
                      COALESCE(SUM(impacto_ejecutado_usd), 0),
                      COALESCE(SUM(impacto_usd) FILTER (WHERE estado <> 'servida'), 0)
                    FROM {PG_SCHEMA}.sugerencias_log
                """)
                r = cur.fetchone() or (0,) * 12
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"impacto falló: {exc}") from exc

    (total, d24, d5m, imp_total, imp_24h, pdv,
     cerradas, ejecutadas, parciales, omitidas, imp_ejecutado, imp_cerrado) = r

    imp_total = float(imp_total or 0)
    imp_24h = float(imp_24h or 0)
    imp_ejecutado = float(imp_ejecutado or 0)
    imp_cerrado = float(imp_cerrado or 0)
    cerradas = int(cerradas or 0)

    # Tasa observada sobre plata, no sobre conteo de visitas: corregir el SKU de
    # mayor rotación no vale lo mismo que corregir el de menor.
    tasa_obs = (imp_ejecutado / imp_cerrado) if imp_cerrado > 0 else None
    base = imp_total * TASA_BASE_SIN_COPILOTO

    if tasa_obs is None:
        # Todavía no cerró ninguna visita: no hay nada que medir y no se inventa.
        recuperado = 0.0
        supuesto = (
            "Venta perdida identificada = caras faltantes × rotación diaria × precio. "
            "La recuperación se calcula sobre visitas ya cerradas; todavía no hay "
            "ninguna, así que aún no hay tasa de ejecución medida."
        )
    else:
        recuperado = imp_total * tasa_obs
        supuesto = (
            "Venta perdida identificada = caras faltantes × rotación diaria × precio. "
            f"La tasa de ejecución del {tasa_obs * 100:.0f}% NO es un supuesto: sale de "
            f"las {cerradas} visitas ya cerradas, comparando el valor de lo corregido "
            f"contra el valor de lo sugerido. El {TASA_BASE_SIN_COPILOTO * 100:.0f}% de "
            "la línea base sí es un supuesto: es lo que se corrige trabajando de memoria."
        )

    return {
        "sugerencias_total": int(total or 0),
        "sugerencias_24h": int(d24 or 0),
        "sugerencias_5min": int(d5m or 0),
        "pdv_atendidos": int(pdv or 0),
        "impacto_identificado_usd": round(imp_total, 2),
        "impacto_identificado_24h_usd": round(imp_24h, 2),
        "recuperacion_estimada_usd": round(recuperado, 2),
        "recuperacion_base_usd": round(base, 2),
        "uplift_usd": round(recuperado - base, 2),
        "tasa_ejecucion_campo_pct": round(tasa_obs * 100, 1) if tasa_obs is not None else None,
        "tasa_base_pct": round(TASA_BASE_SIN_COPILOTO * 100, 1),
        # Ciclo cerrado
        "visitas_cerradas": cerradas,
        "visitas_pendientes": int(total or 0) - cerradas,
        "ejecutadas": int(ejecutadas or 0),
        "parciales": int(parciales or 0),
        "omitidas": int(omitidas or 0),
        "impacto_ejecutado_usd": round(imp_ejecutado, 2),
        "impacto_cerrado_usd": round(imp_cerrado, 2),
        "supuesto": supuesto,
    }
