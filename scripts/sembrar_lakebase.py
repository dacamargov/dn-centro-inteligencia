#!/usr/bin/env python3
"""Genera el SQL que puebla campo.pdv_perfiles en Lakebase desde Unity Catalog.

El perfil de cada punto de venta es un agregado lento del histórico de visitas:
qué categorías fallan más ahí, qué SKUs son foco, cuánto vale la categoría en ese
formato y qué tan probable es encontrar un quiebre. En producción esto sería una
synced table alimentada desde la capa gold; aquí lo materializamos con un UPSERT
para que la demo corra sin depender de la sincronización.

Escribe el SQL a stdout; el wrapper 06_lakebase.sh lo canaliza a psql.
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from q import run_sql  # noqa: E402

# Un solo query arma el perfil completo. Se apoya en visitas (ventana amplia para
# que el histórico sea estable) y en tiendas para los atributos fijos del PDV.
PERFILES_SQL = """
WITH hist AS (
  SELECT
    v.store_id,
    AVG(CASE WHEN v.es_cliente THEN CAST(v.en_stock AS INT) END) * 100            AS disponibilidad_hist,
    AVG(CASE WHEN v.es_cliente THEN CAST(v.ejecucion_perfecta AS INT) END) * 100  AS ejecucion_hist,
    SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END)
      / NULLIF(SUM(v.facings), 0) * 100                                           AS sos_hist,
    AVG(CASE WHEN v.es_cliente THEN CAST(NOT v.en_stock AS INT) END)              AS riesgo_quiebre,
    AVG(CASE WHEN v.es_cliente THEN v.precio_usd END)                             AS ticket_categoria_usd,
    MAX(v.visit_ts)                                                               AS ultima_visita
  FROM {S}.visitas v
  GROUP BY v.store_id
),
-- Las dos categorías donde ese PDV ejecuta peor: son las que el copiloto
-- prioriza cuando el mercaderista no fija una a mano.
cat_rank AS (
  SELECT store_id, categoria,
         ROW_NUMBER() OVER (
           PARTITION BY store_id
           ORDER BY AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) ASC
         ) AS rn
  FROM {S}.visitas
  WHERE es_cliente
  GROUP BY store_id, categoria
),
cats AS (
  SELECT store_id, collect_list(categoria) AS categorias_prioritarias
  FROM cat_rank WHERE rn <= 2
  GROUP BY store_id
),
-- Los SKUs del cliente que más se agotan en ese PDV concreto.
sku_rank AS (
  SELECT store_id, sku,
         ROW_NUMBER() OVER (
           PARTITION BY store_id
           ORDER BY SUM(CASE WHEN NOT en_stock THEN 1 ELSE 0 END) DESC
         ) AS rn
  FROM {S}.visitas
  WHERE es_cliente
  GROUP BY store_id, sku
),
skus AS (
  SELECT store_id, collect_list(sku) AS skus_foco
  FROM sku_rank WHERE rn <= 5
  GROUP BY store_id
)
SELECT
  t.store_id,
  t.nombre,
  t.canal,
  t.cadena,
  t.formato,
  t.ciudad,
  t.country_code,
  p.pais,
  t.mercaderista,
  t.visitas_mes_meta,
  COALESCE(c.categorias_prioritarias, array())            AS categorias_prioritarias,
  COALESCE(s.skus_foco, array())                          AS skus_foco,
  ROUND(COALESCE(h.disponibilidad_hist, 0), 2)            AS disponibilidad_hist,
  ROUND(COALESCE(h.ejecucion_hist, 0), 2)                 AS ejecucion_hist,
  ROUND(COALESCE(h.sos_hist, 0), 2)                       AS sos_hist,
  ROUND(COALESCE(h.riesgo_quiebre, 0), 3)                 AS riesgo_quiebre,
  ROUND(COALESCE(h.ticket_categoria_usd, 0), 2)           AS ticket_categoria_usd,
  h.ultima_visita
FROM {S}.tiendas t
LEFT JOIN {S}.paises p ON p.country_code = t.country_code
LEFT JOIN hist  h ON h.store_id = t.store_id
LEFT JOIN cats  c ON c.store_id = t.store_id
LEFT JOIN skus  s ON s.store_id = t.store_id
ORDER BY t.store_id
"""


def lit(v) -> str:
    """Literal SQL seguro para Postgres a partir de un valor devuelto por el API."""
    if v is None or v == "":
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def num(v, default: str = "0") -> str:
    if v is None or v == "":
        return default
    return str(v)


def arr(v) -> str:
    """Convierte el array serializado del SQL Warehouse a un array de Postgres."""
    if not v:
        return "'{}'"
    # El API devuelve arrays como texto JSON: ["Lácteos","Culinarios"]
    import json

    try:
        items = json.loads(v) if isinstance(v, str) else list(v)
    except Exception:
        items = [x.strip() for x in str(v).strip("[]").split(",") if x.strip()]
    if not items:
        return "'{}'"
    inner = ",".join('"' + str(i).replace('"', '\\"') + '"' for i in items)
    return "'{" + inner + "}'"


def main() -> int:
    profile = os.environ.get("PROFILE") or os.environ.get("DATABRICKS_PROFILE", "DEFAULT")
    warehouse = os.environ.get("WAREHOUSE_ID", "")
    fq = os.environ.get("FQ_SCHEMA") or (
        f"{os.environ.get('CATALOG', 'main')}.{os.environ.get('SCHEMA', 'ditcher_neira')}"
    )
    if not warehouse:
        print("-- ❌ WAREHOUSE_ID vacío", file=sys.stderr)
        return 1

    _, rows = run_sql(profile, warehouse, PERFILES_SQL.replace("{S}", fq))
    if not rows:
        print("-- ❌ sin PDV en Unity Catalog; corre primero la siembra", file=sys.stderr)
        return 1

    out = ["BEGIN;"]
    for r in rows:
        (store_id, nombre, canal, cadena, formato, ciudad, cc, pais, merca, meta,
         cats, skus, disp, ejec, sos, riesgo, ticket, ultima) = r
        out.append(
            "INSERT INTO campo.pdv_perfiles (store_id, nombre, canal, cadena, formato, "
            "ciudad, country_code, pais, mercaderista, visitas_mes_meta, "
            "categorias_prioritarias, skus_foco, disponibilidad_hist, ejecucion_hist, "
            "sos_hist, riesgo_quiebre, ticket_categoria_usd, ultima_visita, actualizado_at) "
            f"VALUES ({lit(store_id)}, {lit(nombre)}, {lit(canal)}, {lit(cadena)}, "
            f"{lit(formato)}, {lit(ciudad)}, {lit(cc)}, {lit(pais)}, {lit(merca)}, "
            f"{num(meta, '4')}, {arr(cats)}, {arr(skus)}, {num(disp)}, {num(ejec)}, "
            f"{num(sos)}, {num(riesgo)}, {num(ticket)}, {lit(ultima)}::timestamptz, NOW()) "
            "ON CONFLICT (store_id) DO UPDATE SET "
            "nombre = EXCLUDED.nombre, canal = EXCLUDED.canal, cadena = EXCLUDED.cadena, "
            "formato = EXCLUDED.formato, ciudad = EXCLUDED.ciudad, "
            "country_code = EXCLUDED.country_code, pais = EXCLUDED.pais, "
            "mercaderista = EXCLUDED.mercaderista, visitas_mes_meta = EXCLUDED.visitas_mes_meta, "
            "categorias_prioritarias = EXCLUDED.categorias_prioritarias, "
            "skus_foco = EXCLUDED.skus_foco, disponibilidad_hist = EXCLUDED.disponibilidad_hist, "
            "ejecucion_hist = EXCLUDED.ejecucion_hist, sos_hist = EXCLUDED.sos_hist, "
            "riesgo_quiebre = EXCLUDED.riesgo_quiebre, "
            "ticket_categoria_usd = EXCLUDED.ticket_categoria_usd, "
            "ultima_visita = EXCLUDED.ultima_visita, actualizado_at = NOW();"
        )
    out.append("COMMIT;")
    print("\n".join(out))
    print(f"-- {len(rows)} PDV preparados", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
