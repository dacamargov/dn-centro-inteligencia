"""Precio y promoción — posición del cliente frente a la competencia.

El índice de precio ya viene calculado por el generador contra la media de la
**subcategoría** y normalizado por contenido (precio por 100 g / 100 ml). Es la
única forma de que la comparación signifique algo: sin normalizar, una leche en
polvo de 800 g contra un sobre de 60 g devuelve un índice enorme y vacío.

100 = paridad. Por encima, el cliente está más caro que sus sustitutos.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..config import FQ
from ..uc import query

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
