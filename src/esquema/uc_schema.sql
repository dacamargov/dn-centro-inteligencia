-- =============================================================================
-- dichter & neira · Centro de Inteligencia — modelo de datos en Unity Catalog
-- =============================================================================
-- Catálogo y esquema se inyectan al aplicarlo (__CATALOG__ / __SCHEMA__).
--
-- Dominio: medición continua de mercado y ejecución en el punto de venta (PDV)
-- para marcas de consumo masivo en LATAM. Una fila de `visitas` = un SKU
-- observado por reconocimiento de imagen durante la visita de un auditor a un PDV.
--
-- Las tablas se dividen en PERSISTENTES (catálogo maestro, sobrevive al reset)
-- y TRANSITORIAS (se vacían con `scripts/limpiar.sh`).
-- =============================================================================

USE CATALOG __CATALOG__;

-- =========================================================================
-- PERSISTENTES — maestros de referencia
-- =========================================================================

-- Países donde D&N tiene operación, con su moneda y factor vs USD.
CREATE TABLE IF NOT EXISTS __SCHEMA__.paises (
    country_code   STRING NOT NULL,
    pais           STRING NOT NULL,
    moneda         STRING NOT NULL,
    fx_usd         DECIMAL(12,4) NOT NULL,   -- unidades de moneda local por 1 USD
    region_dn      STRING NOT NULL,          -- North Latam / South Latam
    CONSTRAINT pk_paises PRIMARY KEY (country_code) RELY
)
USING DELTA
COMMENT 'Países de operación D&N — referencia persistente';

-- Fabricantes medidos. `es_cliente` marca al fabricante que contrata el estudio;
-- el resto es competencia y sirve para calcular participación.
CREATE TABLE IF NOT EXISTS __SCHEMA__.fabricantes (
    fabricante        STRING NOT NULL,
    es_cliente        BOOLEAN NOT NULL,
    color_hex         STRING,
    share_objetivo_pct DECIMAL(5,2),
    CONSTRAINT pk_fabricantes PRIMARY KEY (fabricante) RELY
)
USING DELTA
COMMENT 'Fabricantes de consumo masivo bajo medición — referencia persistente';

-- Catálogo de SKUs auditados en anaquel.
CREATE TABLE IF NOT EXISTS __SCHEMA__.productos (
    sku                STRING NOT NULL,
    nombre             STRING NOT NULL,
    marca              STRING NOT NULL,
    fabricante         STRING NOT NULL,
    categoria          STRING NOT NULL,
    subcategoria       STRING,
    presentacion       STRING,                  -- p.ej. "500 ml", "250 g", "8 cubos"
    -- Contenido normalizado a gramos o mililitros. Es lo que permite comparar precios
    -- entre empaques de distinto tamaño: sin esto, un índice de precio compararía una
    -- bolsa de 800 g contra un sobre de 60 g y devolvería un número sin sentido.
    contenido_norm     DECIMAL(10,2) NOT NULL,
    unidad_norm        STRING NOT NULL,         -- g | ml
    precio_sugerido_usd DECIMAL(10,2) NOT NULL, -- PVP sugerido, base para desvíos
    es_cliente         BOOLEAN NOT NULL,
    emoji              STRING,
    CONSTRAINT pk_productos PRIMARY KEY (sku) RELY
)
USING DELTA
COMMENT 'Catálogo de SKUs FMCG bajo medición — referencia persistente';

-- Universo de puntos de venta auditados (canal moderno y tradicional).
CREATE TABLE IF NOT EXISTS __SCHEMA__.tiendas (
    store_id          STRING NOT NULL,
    nombre            STRING NOT NULL,
    canal             STRING NOT NULL,          -- Moderno / Tradicional
    cadena            STRING NOT NULL,
    formato           STRING NOT NULL,          -- Hipermercado / Supermercado / Colmado...
    ciudad            STRING NOT NULL,
    country_code      STRING NOT NULL,
    latitude          DOUBLE NOT NULL,
    longitude         DOUBLE NOT NULL,
    mercaderista      STRING,                   -- responsable de campo asignado
    visitas_mes_meta  INT NOT NULL,             -- frecuencia de visita comprometida
    CONSTRAINT pk_tiendas PRIMARY KEY (store_id) RELY
)
USING DELTA
COMMENT 'Universo de PDV auditados — referencia persistente';

-- Metas de ejecución por categoría. Son porcentajes objetivo, así que el panel
-- "Meta vs Realizado" compara nivel contra nivel y no acumulado contra acumulado:
-- se mantiene estable sin importar cuánto tiempo lleve corriendo la demo.
CREATE TABLE IF NOT EXISTS __SCHEMA__.metas_categoria (
    categoria              STRING NOT NULL,
    meta_disponibilidad_pct DECIMAL(5,2) NOT NULL,  -- OSA objetivo
    meta_ejecucion_pct      DECIMAL(5,2) NOT NULL,  -- ejecución perfecta objetivo
    meta_sos_pct            DECIMAL(5,2) NOT NULL,  -- share of shelf objetivo del cliente
    CONSTRAINT pk_metas_categoria PRIMARY KEY (categoria) RELY
)
USING DELTA
COMMENT 'Metas de ejecución por categoría — referencia persistente';

-- =========================================================================
-- TRANSITORIAS — generadas en vivo, se vacían con reset.sh
-- =========================================================================

-- Hecho principal: una fila = un SKU observado en anaquel durante una visita.
-- Es el motor de la demo. El generador la alimenta continuamente y poda lo que
-- sale de la ventana de retención.
CREATE TABLE IF NOT EXISTS __SCHEMA__.visitas (
    visita_id           STRING NOT NULL,
    store_id            STRING NOT NULL,
    sku                 STRING NOT NULL,
    visit_ts            TIMESTAMP NOT NULL,
    auditor_id          STRING NOT NULL,
    facings             INT NOT NULL,           -- caras de producto en anaquel
    precio_local        DECIMAL(12,2),
    moneda              STRING NOT NULL,
    precio_usd          DECIMAL(10,2),          -- normalizado, comparable entre países
    en_stock            BOOLEAN NOT NULL,
    en_promo            BOOLEAN NOT NULL,
    planograma_ok       BOOLEAN NOT NULL,
    share_of_shelf      DECIMAL(6,4) NOT NULL,  -- 0..1
    confianza_ir        DECIMAL(5,3) NOT NULL,  -- confianza del reconocimiento de imagen
    ejecucion_perfecta  BOOLEAN NOT NULL,       -- en_stock AND planograma_ok
    -- denormalizado para que el app consulte sin joins en el camino caliente
    canal               STRING NOT NULL,
    cadena              STRING NOT NULL,
    ciudad              STRING NOT NULL,
    country_code        STRING NOT NULL,
    marca               STRING NOT NULL,
    fabricante          STRING NOT NULL,
    categoria           STRING NOT NULL,
    es_cliente          BOOLEAN NOT NULL,
    visit_minute        TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Observaciones de anaquel por visita (StoreConnect AI) — transitoria';

-- Agregado por minuto para las series de tiempo del dashboard.
CREATE TABLE IF NOT EXISTS __SCHEMA__.ejecucion_realtime (
    minute_ts            TIMESTAMP NOT NULL,
    country_code         STRING,
    categoria            STRING,
    observaciones        BIGINT NOT NULL,
    disponibilidad_pct   DECIMAL(5,2) NOT NULL,
    ejecucion_pct        DECIMAL(5,2) NOT NULL,
    sos_cliente_pct      DECIMAL(5,2) NOT NULL,
    promo_pct            DECIMAL(5,2) NOT NULL
)
USING DELTA
COMMENT 'Agregados por minuto de ejecución en PDV — transitoria';

-- Seguimiento de precio y promoción: precio observado del cliente vs competencia
-- en la misma subcategoría, país y cadena.
--
-- El índice se calcula contra la SUBCATEGORÍA y no contra la categoría, porque solo
-- tiene sentido comparar productos sustituibles entre sí. Comparar una leche en polvo
-- de 800 g contra un yogurt de 150 g daría un índice enorme que no significa nada.
CREATE TABLE IF NOT EXISTS __SCHEMA__.precios_competencia (
    snapshot_ts      TIMESTAMP NOT NULL,
    country_code     STRING NOT NULL,
    cadena           STRING NOT NULL,
    categoria        STRING NOT NULL,
    subcategoria     STRING NOT NULL,
    sku              STRING NOT NULL,
    fabricante       STRING NOT NULL,
    marca            STRING NOT NULL,
    es_cliente       BOOLEAN NOT NULL,
    precio_usd       DECIMAL(10,2) NOT NULL,
    en_promo         BOOLEAN NOT NULL,
    indice_precio    DECIMAL(6,2)              -- 100 = paridad con la media de la subcategoría
)
USING DELTA
COMMENT 'Seguimiento de precio y promoción por SKU/cadena — transitoria';

-- Brand & Ad Insight: escucha social de las marcas medidas.
CREATE TABLE IF NOT EXISTS __SCHEMA__.social_posts (
    post_id          STRING NOT NULL,
    platform         STRING NOT NULL,           -- x, instagram, tiktok, facebook
    author_handle    STRING NOT NULL,
    author_followers INT,
    content          STRING NOT NULL,
    marca            STRING,
    fabricante       STRING,
    country_code     STRING,
    sentiment        STRING NOT NULL,           -- positivo / negativo / neutral
    sentiment_score  DECIMAL(4,3) NOT NULL,     -- -1..1
    engagement       INT NOT NULL,
    is_viral         BOOLEAN NOT NULL,
    posted_at        TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Escucha social por marca (Brand & Ad Insight) — transitoria';

-- =========================================================================
-- AGENTES — escritas por los agentes y por el app
-- =========================================================================

CREATE TABLE IF NOT EXISTS __SCHEMA__.recomendaciones (
    id                STRING NOT NULL,
    agent_name        STRING NOT NULL,
    severity          STRING NOT NULL,          -- critical / high / medium / low
    title             STRING NOT NULL,
    analysis          STRING,
    recommendation    STRING,
    suggested_action  STRING,                   -- JSON serializado
    supporting_data   STRING,                   -- JSON serializado
    created_at        TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Recomendaciones generadas por los agentes — transitoria';

CREATE TABLE IF NOT EXISTS __SCHEMA__.runs (
    run_id          STRING NOT NULL,
    agent_name      STRING NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          STRING NOT NULL,
    recs_generated  INT,
    error           STRING
)
USING DELTA
COMMENT 'Trazas de ejecución de los agentes — transitoria';

CREATE TABLE IF NOT EXISTS __SCHEMA__.action_log (
    id                 STRING NOT NULL,
    recommendation_id  STRING,
    action             STRING NOT NULL,          -- APPROVED / REJECTED
    actor              STRING,
    notes              STRING,
    occurred_at        TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Decisiones tomadas sobre las recomendaciones — transitoria';

-- Acciones de campo sugeridas: qué debe corregir el mercaderista en su próxima
-- visita a un PDV concreto.
CREATE TABLE IF NOT EXISTS __SCHEMA__.acciones_campo (
    id             STRING NOT NULL,
    store_id       STRING,
    tienda         STRING,
    sku            STRING,
    producto       STRING,
    categoria      STRING,
    country_code   STRING,
    tipo_accion    STRING,                      -- reponer / corregir_planograma / ajustar_precio / ampliar_espacio
    motivo         STRING,
    urgencia       STRING,                      -- alta / media / baja
    impacto_usd    DECIMAL(14,2),
    created_at     TIMESTAMP NOT NULL,
    status         STRING
)
USING DELTA
COMMENT 'Acciones sugeridas para la fuerza de campo — transitoria';

-- Campañas de amplificación: cuando el equipo decide empujar un post que ya está
-- funcionando orgánicamente, queda registrado acá con su inversión y su alcance.
--
-- El post original se marca is_viral y se le suma el alcance pagado, así que la
-- campaña y su efecto sobre la conversación se ven en la misma pantalla. Es el
-- cierre del ciclo del agente de sentimiento: detecta, recomienda, y alguien actúa.
CREATE TABLE IF NOT EXISTS __SCHEMA__.campanas (
    campana_id        STRING NOT NULL,
    post_id           STRING NOT NULL,
    nombre            STRING NOT NULL,
    marca             STRING,
    fabricante        STRING,
    categoria         STRING,
    country_code      STRING,
    objetivo          STRING NOT NULL,          -- amplificar / defender / lanzar
    plataformas       STRING NOT NULL,          -- lista separada por comas
    presupuesto_usd   DECIMAL(12,2) NOT NULL,
    alcance_estimado  BIGINT NOT NULL,
    engagement_base   INT NOT NULL,             -- engagement orgánico al momento de lanzar
    estado            STRING NOT NULL,          -- activa / pausada / cerrada
    creada_por        STRING,
    creada_en         TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Campañas de amplificación lanzadas desde el centro de mando — transitoria';

-- Traslados entre puntos de venta: el agente de red de abastecimiento cruza las
-- tiendas en quiebre contra las que tienen sobrestock del mismo SKU y propone
-- mover producto por la malla de distribución en lugar de esperar al siguiente
-- despacho de fábrica.
--
-- La fila nace en 'propuesto' y solo un humano la mueve a 'aprobado'. Guardamos
-- la geometría de los dos extremos porque el mapa dibuja la ruta, y la economía
-- completa (venta recuperada, costo logístico, ganancia neta) porque el que
-- aprueba tiene que poder discutir el número, no solo verlo.
CREATE TABLE IF NOT EXISTS __SCHEMA__.traslados (
    traslado_id          STRING NOT NULL,
    sku                  STRING NOT NULL,
    producto             STRING,
    marca                STRING,
    categoria            STRING,
    country_code         STRING,
    origen_id            STRING NOT NULL,
    origen_nombre        STRING,
    origen_ciudad        STRING,
    origen_lat           DOUBLE,
    origen_lon           DOUBLE,
    destino_id           STRING NOT NULL,
    destino_nombre       STRING,
    destino_ciudad       STRING,
    destino_lat          DOUBLE,
    destino_lon          DOUBLE,
    distancia_km         DOUBLE NOT NULL,
    unidades             INT NOT NULL,
    venta_recuperada_usd DECIMAL(12,2) NOT NULL,
    costo_logistico_usd  DECIMAL(12,2) NOT NULL,
    ganancia_neta_usd    DECIMAL(12,2) NOT NULL,
    estado               STRING NOT NULL,       -- propuesto / aprobado / descartado
    decidido_por         STRING,
    decidido_en          TIMESTAMP,
    propuesto_en         TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Traslados de mercadería propuestos por el agente de red — transitoria';
