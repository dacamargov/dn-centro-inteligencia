"""Precio y promoción — posición del cliente frente a la competencia.

El índice de precio ya viene calculado por el generador contra la media de la
**subcategoría** y normalizado por contenido (precio por 100 g / 100 ml). Es la
única forma de que la comparación signifique algo: sin normalizar, una leche en
polvo de 800 g contra un sobre de 60 g devuelve un índice enorme y vacío.

100 = paridad. Por encima, el cliente está más caro que sus sustitutos.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..config import FQ, get_current_user_email
from ..uc import execute, query

router = APIRouter()


def _q(s: str) -> str:
    return "'" + (s or "").replace("'", "''") + "'"


def _ultimo_snapshot() -> str:
    """CTE reutilizable con la foto de precios más reciente."""
    return f"""
        ultimo AS (
          SELECT MAX(snapshot_ts) AS ts FROM {FQ}.precios_competencia
        ),
        snap AS (
          SELECT * FROM {FQ}.precios_competencia, ultimo
          WHERE snapshot_ts = ultimo.ts
        )
    """


def _excluir_promos_activas(alias: str = "c") -> str:
    """SKUs con promoción activa no vuelven a la cola del simulador."""
    return f"""
        AND NOT EXISTS (
          SELECT 1 FROM {FQ}.promociones_gondola pg
          WHERE pg.sku = {alias}.sku
            AND pg.estado = 'activa'
        )
    """


_PROMO_COLS = """
    promo_id, sku, producto, marca, categoria, subcategoria,
    country_code, cadena, descuento_pct, duracion,
    precio_base_usd, precio_gondola_usd, estado, lanzada_por, lanzada_en
"""


class LanzarPromocionBody(BaseModel):
    sku: str = Field(..., min_length=1, max_length=80)
    cadena: str = Field(..., min_length=1, max_length=120)
    country_code: str = Field(..., min_length=2, max_length=8)
    descuento_pct: int = Field(..., ge=5, le=50)
    duracion: str = Field(..., min_length=3, max_length=40)
    precio_base_usd: float = Field(..., gt=0)
    producto: Optional[str] = None
    marca: Optional[str] = None
    categoria: Optional[str] = None
    subcategoria: Optional[str] = None


def _fila_promo(r: dict) -> dict:
    return {
        "promo_id": r["promo_id"],
        "sku": r["sku"],
        "producto": r.get("producto"),
        "marca": r.get("marca"),
        "categoria": r.get("categoria"),
        "subcategoria": r.get("subcategoria"),
        "country_code": r["country_code"],
        "cadena": r["cadena"],
        "descuento_pct": int(r["descuento_pct"]),
        "duracion": r["duracion"],
        "precio_base_usd": float(r["precio_base_usd"] or 0),
        "precio_gondola_usd": float(r["precio_gondola_usd"] or 0),
        "estado": r["estado"],
        "lanzada_por": r.get("lanzada_por"),
        "lanzada_en": r.get("lanzada_en"),
    }


@router.get("/api/precios/brechas")
def brechas(
    categoria: Optional[str] = Query(None),
    umbral: float = Query(108.0, ge=100.0, le=200.0,
                          description="índice desde el cual se considera brecha"),
    limit: int = Query(50, ge=1, le=200),
):
    """SKUs del cliente donde el precio está por encima de sus sustitutos.

    Devuelve, junto a cada SKU, el competidor más barato de la misma
    subcategoría en el mismo país y cadena: es la comparación que el ejecutivo
    de la marca hace de cabeza cuando ve el número.
    """
    cat_filter = f"AND s.categoria = {_q(categoria)}" if categoria else ""
    sql = f"""
        WITH {_ultimo_snapshot()},
        cliente AS (
          SELECT s.* FROM snap s
          WHERE s.es_cliente AND s.indice_precio >= {float(umbral)}
            {cat_filter}
            {_excluir_promos_activas("s")}
        ),
        rival AS (
          -- El sustituto más barato en la misma plaza y subcategoría.
          SELECT country_code, cadena, subcategoria,
                 MIN_BY(marca, precio_usd)      AS marca_rival,
                 MIN_BY(fabricante, precio_usd) AS fabricante_rival,
                 MIN(precio_usd)                AS precio_rival_usd
          FROM snap
          WHERE NOT es_cliente
          GROUP BY country_code, cadena, subcategoria
        )
        SELECT c.sku, p.nombre AS producto, p.emoji, c.marca, c.categoria,
               c.subcategoria, c.country_code, c.cadena,
               CAST(c.precio_usd AS DOUBLE)     AS precio_usd,
               CAST(c.indice_precio AS DOUBLE)  AS indice_precio,
               c.en_promo,
               r.marca_rival, r.fabricante_rival,
               CAST(r.precio_rival_usd AS DOUBLE) AS precio_rival_usd
        FROM cliente c
        LEFT JOIN {FQ}.productos p ON p.sku = c.sku
        LEFT JOIN rival r
          ON r.country_code = c.country_code
         AND r.cadena       = c.cadena
         AND r.subcategoria = c.subcategoria
        ORDER BY c.indice_precio DESC
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
            "subcategoria": r["subcategoria"],
            "country_code": r["country_code"],
            "cadena": r["cadena"],
            "precio_usd": float(r["precio_usd"] or 0),
            "indice_precio": float(r["indice_precio"] or 0),
            "en_promo": bool(r["en_promo"]),
            "marca_rival": r.get("marca_rival"),
            "fabricante_rival": r.get("fabricante_rival"),
            "precio_rival_usd": (
                float(r["precio_rival_usd"]) if r.get("precio_rival_usd") is not None else None
            ),
        }
        for r in rows
    ]


@router.get("/api/precios/por-categoria")
def por_categoria():
    """Índice medio del cliente por categoría y presión promocional de la competencia."""
    sql = f"""
        WITH {_ultimo_snapshot()}
        SELECT
          categoria,
          ROUND(AVG(CASE WHEN es_cliente THEN indice_precio END), 1)      AS indice_cliente,
          ROUND(AVG(CASE WHEN NOT es_cliente THEN indice_precio END), 1)  AS indice_competencia,
          ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_promo AS INT) END) * 100, 1)
                                                                          AS promo_cliente_pct,
          ROUND(AVG(CASE WHEN NOT es_cliente THEN CAST(en_promo AS INT) END) * 100, 1)
                                                                          AS promo_competencia_pct,
          COUNT(DISTINCT CASE WHEN es_cliente THEN sku END)               AS skus_cliente,
          COUNT(*)                                                        AS observaciones
        FROM snap
        GROUP BY categoria
        ORDER BY indice_cliente DESC
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "categoria": r["categoria"],
            "indice_cliente": float(r["indice_cliente"] or 0),
            "indice_competencia": float(r["indice_competencia"] or 0),
            "brecha": round(float(r["indice_cliente"] or 0) - float(r["indice_competencia"] or 0), 1),
            "promo_cliente_pct": float(r["promo_cliente_pct"] or 0),
            "promo_competencia_pct": float(r["promo_competencia_pct"] or 0),
            "skus_cliente": int(r["skus_cliente"] or 0),
            "observaciones": int(r["observaciones"] or 0),
        }
        for r in rows
    ]


@router.get("/api/precios/por-cadena")
def por_cadena(categoria: Optional[str] = Query(None)):
    """Índice del cliente por cadena y país — dónde duele la posición de precio."""
    cat_filter = f"AND categoria = {_q(categoria)}" if categoria else ""
    sql = f"""
        WITH {_ultimo_snapshot()}
        SELECT
          country_code, cadena,
          ROUND(AVG(CASE WHEN es_cliente THEN indice_precio END), 1)     AS indice_cliente,
          ROUND(AVG(CASE WHEN NOT es_cliente THEN indice_precio END), 1) AS indice_competencia,
          COUNT(DISTINCT CASE WHEN es_cliente THEN sku END)              AS skus_cliente
        FROM snap
        WHERE 1=1 {cat_filter}
        GROUP BY country_code, cadena
        HAVING indice_cliente IS NOT NULL
        ORDER BY indice_cliente DESC
        LIMIT 40
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "country_code": r["country_code"],
            "cadena": r["cadena"],
            "indice_cliente": float(r["indice_cliente"] or 0),
            "indice_competencia": float(r["indice_competencia"] or 0),
            "brecha": round(
                float(r["indice_cliente"] or 0) - float(r["indice_competencia"] or 0), 1
            ),
            "skus_cliente": int(r["skus_cliente"] or 0),
        }
        for r in rows
    ]


@router.get("/api/precios/promociones")
def list_promociones(limit: int = Query(30, ge=1, le=100)):
    """Promociones en góndola lanzadas desde el simulador — la más reciente primero."""
    sql = f"""
        SELECT {_PROMO_COLS}
        FROM {FQ}.promociones_gondola
        WHERE estado = 'activa'
        ORDER BY lanzada_en DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc
    return [_fila_promo(r) for r in rows]


@router.post("/api/precios/promociones")
def lanzar_promocion(body: LanzarPromocionBody, request: Request):
    """Activa una promoción en góndola: registra la fila, el log y saca el SKU de la cola."""
    sku = body.sku.strip()
    cadena = body.cadena.strip()
    country = body.country_code.strip().upper()

    ya = query(f"""
        SELECT promo_id FROM {FQ}.promociones_gondola
        WHERE sku = {_q(sku)} AND cadena = {_q(cadena)} AND country_code = {_q(country)}
          AND estado = 'activa'
        LIMIT 1
    """)
    if ya:
        raise HTTPException(
            status_code=409,
            detail="Este SKU ya tiene una promoción activa en esa cadena.",
        )

    precio_gondola = round(body.precio_base_usd * (1 - body.descuento_pct / 100), 2)
    promo_id = f"prm_{uuid.uuid4().hex[:12]}"
    actor = get_current_user_email(request)
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    log_id = f"act_{uuid.uuid4().hex[:14]}"

    notas = {
        "tipo": "promocion_gondola",
        "promo_id": promo_id,
        "sku": sku,
        "cadena": cadena,
        "country_code": country,
        "descuento_pct": body.descuento_pct,
        "duracion": body.duracion,
        "precio_base_usd": body.precio_base_usd,
        "precio_gondola_usd": precio_gondola,
        "producto": body.producto,
    }

    try:
        execute(f"""
            INSERT INTO {FQ}.promociones_gondola VALUES (
              {_q(promo_id)}, {_q(sku)}, {_q(body.producto or '')},
              {_q(body.marca or '')}, {_q(body.categoria or '')}, {_q(body.subcategoria or '')},
              {_q(country)}, {_q(cadena)},
              {int(body.descuento_pct)}, {_q(body.duracion)},
              CAST({body.precio_base_usd} AS DECIMAL(10,2)),
              CAST({precio_gondola} AS DECIMAL(10,2)),
              'activa', {_q(actor)}, '{now_iso}'
            )
        """)
        execute(f"""
            INSERT INTO {FQ}.action_log
              (id, recommendation_id, action, actor, notes, occurred_at)
            VALUES (
              {_q(log_id)}, {_q(f"promo:{promo_id}")},
              'ACTIVAR_PROMO', {_q(actor)},
              {_q(json.dumps(notas, ensure_ascii=False))},
              '{now_iso}'
            )
        """)
        execute(f"""
            UPDATE {FQ}.precios_competencia
            SET en_promo = true
            WHERE sku = {_q(sku)}
              AND cadena = {_q(cadena)}
              AND country_code = {_q(country)}
              AND es_cliente = true
              AND snapshot_ts = (
                SELECT MAX(snapshot_ts) FROM {FQ}.precios_competencia
              )
        """)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"no se pudo lanzar la promoción: {exc}") from exc

    return {
        "promo_id": promo_id,
        "log_id": log_id,
        "sku": sku,
        "producto": body.producto,
        "marca": body.marca,
        "categoria": body.categoria,
        "subcategoria": body.subcategoria,
        "country_code": country,
        "cadena": cadena,
        "descuento_pct": body.descuento_pct,
        "duracion": body.duracion,
        "precio_base_usd": body.precio_base_usd,
        "precio_gondola_usd": precio_gondola,
        "estado": "activa",
        "lanzada_por": actor,
        "lanzada_en": now_iso,
    }
