-- =============================================================================
-- Unity Catalog — gobernanza del esquema dacamargovws_catalog.ditcher
-- =============================================================================
-- Aplica: claves primarias/foráneas (RELY), comentarios de negocio, tags de
-- clasificación (incluida la marca de DATO SINTÉTICO) y GRANTs de acceso.
-- Pensado para ejecutarse en el SQL Editor / warehouse del workspace.
-- Los nombres de catálogo/esquema son los del deploy vivo de la demo.

-- ---------------------------------------------------------------------------
-- 0 · Marca a nivel esquema: todo el dato es SINTÉTICO (no es dato de cliente)
-- ---------------------------------------------------------------------------
COMMENT ON SCHEMA dacamargovws_catalog.ditcher IS
  'Centro de Inteligencia D&N — datos 100% SINTÉTICOS generados para la demo. No contiene datos reales de clientes ni PII.';
ALTER SCHEMA dacamargovws_catalog.ditcher SET TAGS ('dato' = 'sintetico');

-- ---------------------------------------------------------------------------
-- 1 · Claves primarias (RELY) sobre maestros y hechos
-- ---------------------------------------------------------------------------
ALTER TABLE dacamargovws_catalog.ditcher.tiendas  ALTER COLUMN store_id      SET NOT NULL;
ALTER TABLE dacamargovws_catalog.ditcher.productos ALTER COLUMN sku          SET NOT NULL;
ALTER TABLE dacamargovws_catalog.ditcher.paises    ALTER COLUMN country_code SET NOT NULL;

ALTER TABLE dacamargovws_catalog.ditcher.tiendas
  ADD CONSTRAINT pk_tiendas PRIMARY KEY (store_id) RELY;
ALTER TABLE dacamargovws_catalog.ditcher.productos
  ADD CONSTRAINT pk_productos PRIMARY KEY (sku) RELY;
ALTER TABLE dacamargovws_catalog.ditcher.paises
  ADD CONSTRAINT pk_paises PRIMARY KEY (country_code) RELY;
ALTER TABLE dacamargovws_catalog.ditcher.visitas
  ADD CONSTRAINT pk_visitas PRIMARY KEY (visita_id) RELY;

-- ---------------------------------------------------------------------------
-- 2 · Claves foráneas (RELY, NOT ENFORCED) — habilitan joins y lineage en Genie
-- ---------------------------------------------------------------------------
ALTER TABLE dacamargovws_catalog.ditcher.visitas
  ADD CONSTRAINT fk_visitas_tienda FOREIGN KEY (store_id)
  REFERENCES dacamargovws_catalog.ditcher.tiendas (store_id) RELY;
ALTER TABLE dacamargovws_catalog.ditcher.visitas
  ADD CONSTRAINT fk_visitas_producto FOREIGN KEY (sku)
  REFERENCES dacamargovws_catalog.ditcher.productos (sku) RELY;
ALTER TABLE dacamargovws_catalog.ditcher.tiendas
  ADD CONSTRAINT fk_tiendas_pais FOREIGN KEY (country_code)
  REFERENCES dacamargovws_catalog.ditcher.paises (country_code) RELY;

-- ---------------------------------------------------------------------------
-- 3 · Comentarios de negocio sobre tablas
-- ---------------------------------------------------------------------------
COMMENT ON TABLE dacamargovws_catalog.ditcher.tiendas IS
  'Maestro de puntos de venta auditados (tienda, canal, cadena, ciudad, país). Dato sintético.';
COMMENT ON TABLE dacamargovws_catalog.ditcher.productos IS
  'Maestro de SKUs con marca/fabricante/categoría y bandera es_cliente (Nestlé vs. competencia). Dato sintético.';
COMMENT ON TABLE dacamargovws_catalog.ditcher.visitas IS
  'Hecho de auditoría de anaquel: una fila por lectura tienda×SKU (stock, facings, precio, promo, planograma, share of shelf, confianza del reconocimiento de imagen).';
COMMENT ON TABLE dacamargovws_catalog.ditcher.ejecucion_pdv_gold IS
  'Capa GOLD de Lakeflow: KPIs de ejecución por tienda×categoría (disponibilidad, ejecución perfecta, promo, share of shelf cliente).';
COMMENT ON TABLE dacamargovws_catalog.ditcher.predicciones_riesgo IS
  'Inferencia batch del modelo UC modelo_riesgo_quiebre@campeon: riesgo de quiebre por tienda×categoría con tier ALTO/MEDIO/BAJO.';
COMMENT ON TABLE dacamargovws_catalog.ditcher.recomendaciones IS
  'Salidas de los agentes de Gen AI: recomendaciones accionables priorizadas por severidad.';

-- ---------------------------------------------------------------------------
-- 4 · Comentarios de columnas clave (ayudan a Genie a razonar)
-- ---------------------------------------------------------------------------
ALTER TABLE dacamargovws_catalog.ditcher.visitas ALTER COLUMN en_stock
  COMMENT 'TRUE si el SKU estaba disponible en anaquel en la visita (base del cálculo de quiebre).';
ALTER TABLE dacamargovws_catalog.ditcher.visitas ALTER COLUMN share_of_shelf
  COMMENT 'Participación de caras del SKU sobre el total de la categoría en esa visita (0-1).';
ALTER TABLE dacamargovws_catalog.ditcher.visitas ALTER COLUMN confianza_ir
  COMMENT 'Confianza del reconocimiento de imagen de la lectura (0-1).';
ALTER TABLE dacamargovws_catalog.ditcher.visitas ALTER COLUMN es_cliente
  COMMENT 'TRUE si el SKU pertenece al cliente (Nestlé), FALSE si es competencia.';
ALTER TABLE dacamargovws_catalog.ditcher.predicciones_riesgo ALTER COLUMN riesgo_predicho
  COMMENT 'Tasa de quiebre esperada (0-1) estimada por el modelo de ML.';
ALTER TABLE dacamargovws_catalog.ditcher.predicciones_riesgo ALTER COLUMN tier_riesgo
  COMMENT 'Clasificación accionable: ALTO (>=0.18), MEDIO (>=0.10), BAJO (<0.10).';

-- ---------------------------------------------------------------------------
-- 5 · Tags de clasificación por capa/dominio
-- ---------------------------------------------------------------------------
ALTER TABLE dacamargovws_catalog.ditcher.auditorias_bronze    SET TAGS ('capa' = 'bronze', 'dato' = 'sintetico');
ALTER TABLE dacamargovws_catalog.ditcher.auditorias_silver    SET TAGS ('capa' = 'silver', 'dato' = 'sintetico');
ALTER TABLE dacamargovws_catalog.ditcher.ejecucion_pdv_gold   SET TAGS ('capa' = 'gold',   'dato' = 'sintetico');
ALTER TABLE dacamargovws_catalog.ditcher.predicciones_riesgo  SET TAGS ('capa' = 'ml_serving', 'dato' = 'sintetico');
ALTER TABLE dacamargovws_catalog.ditcher.visitas ALTER COLUMN precio_local SET TAGS ('sensibilidad' = 'comercial');

-- ---------------------------------------------------------------------------
-- 6 · GRANTs de acceso (gobierno de permisos)
-- ---------------------------------------------------------------------------
GRANT USE CATALOG ON CATALOG dacamargovws_catalog TO `account users`;
GRANT USE SCHEMA, SELECT ON SCHEMA dacamargovws_catalog.ditcher TO `account users`;
-- El acceso al modelo UC se gobierna con EXECUTE ON el securable de modelo:
GRANT EXECUTE ON FUNCTION dacamargovws_catalog.ditcher.modelo_riesgo_quiebre TO `account users`;
