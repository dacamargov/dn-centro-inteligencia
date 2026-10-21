-- =============================================================================
-- Capa GOLD de serving — perfil operativo del PDV (una fila por tienda)
-- =============================================================================
-- Esta tabla es el ÚNICO origen de los features que sirve el copiloto de campo.
-- Se construye desde la capa gobernada:
--   * ejecucion_pdv_gold   (capa GOLD de Lakeflow)  → disponibilidad / ejecución / SoS
--   * predicciones_riesgo  (salida del modelo de ML) → riesgo de quiebre
--   * tiendas / paises     (maestros de UC)          → atributos descriptivos
--   * visitas              (hecho gobernado)         → SKUs foco por PDV
-- Al derivar el serving desde los mismos datos de gold/modelo que entrenan y
-- reportan, el feature de serving y el de entrenamiento NO pueden desalinearse.
-- Es el origen de la synced table hacia Lakebase (ver docs/LAKEBASE.md).
-- Parametrizada por {cat}.{sch} desde el job de Lakebase.

CREATE OR REPLACE TABLE {cat}.{sch}.pdv_perfil_gold AS
WITH g AS (  -- agregado a nivel tienda desde la capa GOLD (ponderado por observaciones)
  SELECT store_id,
    SUM(observaciones) AS obs,
    ROUND(SUM(disponibilidad_pct * observaciones) / NULLIF(SUM(observaciones),0), 2) AS disponibilidad_hist,
    ROUND(SUM(ejecucion_pct    * observaciones) / NULLIF(SUM(observaciones),0), 2) AS ejecucion_hist,
    ROUND(SUM(sos_cliente_pct  * observaciones) / NULLIF(SUM(observaciones),0), 2) AS sos_hist,
    MAX(ultima_visita) AS ultima_visita
  FROM {cat}.{sch}.ejecucion_pdv_gold
  GROUP BY store_id
),
catrank AS (  -- las 2 categorías donde el PDV ejecuta peor (desde GOLD)
  SELECT store_id, categoria,
    ROW_NUMBER() OVER (PARTITION BY store_id ORDER BY disponibilidad_pct ASC, categoria) AS rn
  FROM {cat}.{sch}.ejecucion_pdv_gold
),
cats AS (
  SELECT store_id, collect_list(categoria) AS categorias_prioritarias
  FROM catrank WHERE rn <= 2 GROUP BY store_id
),
skurank AS (  -- los 5 SKUs del cliente que más se agotan en ese PDV
  SELECT store_id, sku,
    ROW_NUMBER() OVER (PARTITION BY store_id ORDER BY SUM(CASE WHEN NOT en_stock THEN 1 ELSE 0 END) DESC, sku) AS rn
  FROM {cat}.{sch}.visitas WHERE es_cliente GROUP BY store_id, sku
),
skus AS (
  SELECT store_id, collect_list(sku) AS skus_foco
  FROM skurank WHERE rn <= 5 GROUP BY store_id
),
risk AS (  -- riesgo de quiebre = salida del MODELO de ML (predicciones_riesgo)
  SELECT store_id, ROUND(AVG(riesgo_predicho), 3) AS riesgo_quiebre
  FROM {cat}.{sch}.predicciones_riesgo GROUP BY store_id
),
ticket AS (
  SELECT store_id, ROUND(AVG(precio_usd), 2) AS ticket_categoria_usd
  FROM {cat}.{sch}.visitas WHERE es_cliente GROUP BY store_id
)
SELECT
  t.store_id, t.nombre, t.canal, t.cadena, t.formato, t.ciudad, t.country_code,
  p.pais, t.mercaderista, CAST(t.visitas_mes_meta AS INT) AS visitas_mes_meta,
  COALESCE(c.categorias_prioritarias, array())  AS categorias_prioritarias,
  COALESCE(s.skus_foco, array())                AS skus_foco,
  CAST(COALESCE(g.disponibilidad_hist, 0) AS DOUBLE) AS disponibilidad_hist,
  CAST(COALESCE(g.ejecucion_hist, 0)      AS DOUBLE) AS ejecucion_hist,
  CAST(COALESCE(g.sos_hist, 0)            AS DOUBLE) AS sos_hist,
  CAST(COALESCE(r.riesgo_quiebre, 0)      AS DOUBLE) AS riesgo_quiebre,
  CAST(COALESCE(tk.ticket_categoria_usd, 0) AS DOUBLE) AS ticket_categoria_usd,
  g.ultima_visita,
  current_timestamp() AS actualizado_at
FROM {cat}.{sch}.tiendas t
LEFT JOIN {cat}.{sch}.paises p  ON p.country_code = t.country_code
LEFT JOIN g      ON g.store_id  = t.store_id
LEFT JOIN cats c ON c.store_id  = t.store_id
LEFT JOIN skus s ON s.store_id  = t.store_id
LEFT JOIN risk r ON r.store_id  = t.store_id
LEFT JOIN ticket tk ON tk.store_id = t.store_id;

-- PK (RELY) + Change Data Feed: requisitos para registrarla como synced table.
ALTER TABLE {cat}.{sch}.pdv_perfil_gold ALTER COLUMN store_id SET NOT NULL;
ALTER TABLE {cat}.{sch}.pdv_perfil_gold ADD CONSTRAINT pk_pdv_perfil_gold PRIMARY KEY (store_id) RELY;
ALTER TABLE {cat}.{sch}.pdv_perfil_gold SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
COMMENT ON TABLE {cat}.{sch}.pdv_perfil_gold IS
  'Capa GOLD de serving: perfil operativo por PDV (desde ejecucion_pdv_gold + predicciones_riesgo + maestros). Origen de la synced table a Lakebase.';
