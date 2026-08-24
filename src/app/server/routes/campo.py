"""Acciones de campo — qué debe corregir el mercaderista en su próxima visita.

Ocupa el lugar que en un tablero de retail tendrían las sugerencias logísticas.
La lógica es determinística en SQL: se detectan tres patrones sobre la ventana
viva de `visitas` y se ordenan por impacto estimado.

  * `reponer`             — el SKU aparece agotado de forma repetida en el PDV.
  * `corregir_planograma` — está en stock pero mal exhibido.
  * `ampliar_espacio`     — hay stock y planograma, pero el espacio del cliente
                            quedó por debajo de la meta de share of shelf.

El impacto en USD es una estimación de venta perdida: precio sugerido del SKU
por las caras que le faltan, extrapolado a un día de operación del PDV. Sirve
para priorizar, no para cerrar el mes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..config import FQ, get_current_user_email
from ..uc import execute, query

router = APIRouter()

# Rotación diaria asumida por cara de producto. Es el factor que convierte una
# cara faltante en dinero; conservador a propósito.
UNIDADES_DIA_POR_FACING = 3.0
MIN_LECTURAS = 3


def _q(s: Optional[str]) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


@router.get("/api/campo/acciones")
def acciones(
    limit: int = Query(12, ge=1, le=100),
    categoria: Optional[str] = Query(None),
    window_min: int = Query(60, ge=10, le=240),
):
    cat_filter = f"AND v.categoria = {_q(categoria)}" if categoria else ""
    sql = f"""
        WITH obs AS (
          SELECT v.store_id, v.sku, v.categoria, v.marca,
                 COUNT(*)                                    AS lecturas,
                 AVG(CAST(v.en_stock AS INT))                 AS tasa_stock,
                 AVG(CAST(v.planograma_ok AS INT))            AS tasa_plano,
                 AVG(v.facings)                               AS facings_prom,
                 MAX(v.visit_ts)                              AS ultima_lectura
          FROM {FQ}.visitas v
          WHERE v.visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
            AND v.es_cliente
            {cat_filter}
          GROUP BY v.store_id, v.sku, v.categoria, v.marca
          HAVING COUNT(*) >= {MIN_LECTURAS}
        ),
        sos AS (
          -- Espacio del cliente por PDV y categoría, para el caso ampliar_espacio.
          SELECT store_id, categoria,
                 SUM(CASE WHEN es_cliente THEN facings ELSE 0 END)
                   / NULLIF(SUM(facings), 0) * 100 AS sos_pct
          FROM {FQ}.visitas
          WHERE visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
            {cat_filter.replace("v.", "")}
          GROUP BY store_id, categoria
        ),
        diagnostico AS (
          SELECT o.*,
                 s.sos_pct,
                 m.meta_sos_pct,
                 p.nombre AS producto, p.emoji, p.precio_sugerido_usd,
                 t.nombre AS tienda, t.cadena, t.canal, t.ciudad,
                 t.country_code, t.mercaderista,
                 CASE
                   WHEN o.tasa_stock  < 0.70 THEN 'reponer'
                   WHEN o.tasa_plano  < 0.70 THEN 'corregir_planograma'
                   WHEN s.sos_pct IS NOT NULL AND m.meta_sos_pct IS NOT NULL
                        AND s.sos_pct < m.meta_sos_pct - 5 THEN 'ampliar_espacio'
                 END AS tipo_accion
          FROM obs o
          JOIN {FQ}.tiendas   t ON t.store_id = o.store_id
          JOIN {FQ}.productos p ON p.sku      = o.sku
          LEFT JOIN sos s ON s.store_id = o.store_id AND s.categoria = o.categoria
          LEFT JOIN {FQ}.metas_categoria m ON m.categoria = o.categoria
        )
        SELECT
          store_id, tienda, cadena, canal, ciudad, country_code, mercaderista,
          sku, producto, emoji, marca, categoria,
          tipo_accion,
          ROUND(tasa_stock * 100, 1)  AS disponibilidad_pct,
          ROUND(tasa_plano * 100, 1)  AS planograma_pct,
          ROUND(facings_prom, 1)      AS facings_prom,
          ROUND(sos_pct, 1)           AS sos_pct,
          CAST(meta_sos_pct AS DOUBLE) AS meta_sos_pct,
          lecturas,
          ultima_lectura,
          -- Caras perdidas × rotación × precio = venta que no ocurre hoy.
          CAST(
            GREATEST(1.0, facings_prom) * (1.0 - tasa_stock)
            * {UNIDADES_DIA_POR_FACING} * precio_sugerido_usd
            AS DECIMAL(14,2)
          ) AS impacto_usd
        FROM diagnostico
        WHERE tipo_accion IS NOT NULL
        ORDER BY
          CASE tipo_accion
            WHEN 'reponer' THEN 0
            WHEN 'corregir_planograma' THEN 1
            ELSE 2
          END,
          impacto_usd DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    def urgencia(r) -> str:
        disp = float(r.get("disponibilidad_pct") or 100)
        if r["tipo_accion"] == "reponer" and disp < 45:
            return "alta"
        if r["tipo_accion"] == "reponer":
            return "media"
        return "media" if r["tipo_accion"] == "corregir_planograma" else "baja"

    return [
        {
            "store_id": r["store_id"],
            "tienda": r["tienda"],
            "cadena": r["cadena"],
            "canal": r["canal"],
            "ciudad": r["ciudad"],
            "country_code": r["country_code"],
            "mercaderista": r.get("mercaderista"),
            "sku": r["sku"],
            "producto": r["producto"],
            "emoji": r.get("emoji"),
            "marca": r["marca"],
            "categoria": r["categoria"],
            "tipo_accion": r["tipo_accion"],
            "disponibilidad_pct": float(r["disponibilidad_pct"] or 0),
            "planograma_pct": float(r["planograma_pct"] or 0),
            "facings_prom": float(r["facings_prom"] or 0),
            "sos_pct": float(r["sos_pct"]) if r.get("sos_pct") is not None else None,
            "meta_sos_pct": (
                float(r["meta_sos_pct"]) if r.get("meta_sos_pct") is not None else None
            ),
            "lecturas": int(r["lecturas"] or 0),
            "ultima_lectura": (
                r["ultima_lectura"].isoformat() if r.get("ultima_lectura") else None
            ),
            "impacto_usd": float(r["impacto_usd"] or 0),
            "urgencia": urgencia(r),
        }
        for r in rows
    ]


class AccionCampo(BaseModel):
    store_id: str
    sku: str
    tipo_accion: str = Field(..., min_length=1, max_length=40)
    tienda: Optional[str] = None
    producto: Optional[str] = None
    categoria: Optional[str] = None
    country_code: Optional[str] = None
    motivo: Optional[str] = None
    urgencia: str = "media"
    impacto_usd: float = 0.0


TIPOS_VALIDOS = {"reponer", "corregir_planograma", "ampliar_espacio", "ajustar_precio"}


@router.post("/api/campo/despachar")
def despachar(body: AccionCampo, request: Request):
    """Envía la acción a la cola del mercaderista y la deja registrada."""
    if body.tipo_accion not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_accion inválido: {body.tipo_accion}")

    actor = get_current_user_email(request)
    accion_id = f"acc_{uuid.uuid4().hex[:14]}"
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    motivo = body.motivo or f"despachada por {actor}"

    sql = f"""
        INSERT INTO {FQ}.acciones_campo
          (id, store_id, tienda, sku, producto, categoria, country_code,
           tipo_accion, motivo, urgencia, impacto_usd, created_at, status)
        VALUES (
          '{accion_id}', {_q(body.store_id)}, {_q(body.tienda)}, {_q(body.sku)},
          {_q(body.producto)}, {_q(body.categoria)}, {_q(body.country_code)},
          {_q(body.tipo_accion)}, {_q(motivo)}, {_q(body.urgencia)},
          {float(body.impacto_usd):.2f}, '{now_iso}', 'despachada'
        )
    """
    try:
        execute(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC write failed: {exc}") from exc

    return {
        "ok": True,
        "id": accion_id,
        "actor": actor,
        "store_id": body.store_id,
        "sku": body.sku,
        "tipo_accion": body.tipo_accion,
    }


@router.get("/api/campo/despachadas")
def despachadas(limit: int = Query(30, ge=1, le=200)):
    """Cola de acciones ya enviadas a campo — cierra el ciclo del tablero."""
    sql = f"""
        SELECT id, store_id, tienda, sku, producto, categoria, country_code,
               tipo_accion, motivo, urgencia, impacto_usd, created_at, status
        FROM {FQ}.acciones_campo
        ORDER BY created_at DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            **{k: r.get(k) for k in (
                "id", "store_id", "tienda", "sku", "producto", "categoria",
                "country_code", "tipo_accion", "motivo", "urgencia", "status",
            )},
            "impacto_usd": float(r["impacto_usd"] or 0),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]
