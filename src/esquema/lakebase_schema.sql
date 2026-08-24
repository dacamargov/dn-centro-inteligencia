-- =============================================================================
-- dichter & neira · Centro de Inteligencia — esquema operacional en Lakebase
-- =============================================================================
-- Lakebase (Postgres gestionado por Databricks) sirve el camino caliente del
-- copiloto de campo: el mercaderista llega a un PDV, abre la app y en menos de
-- 100 ms recibe la lista priorizada de qué corregir en ese anaquel.
--
-- La división es deliberada:
--   * Unity Catalog / Delta  → analítica, historia completa, entrenamiento.
--   * Lakebase / Postgres    → lectura por clave a latencia de aplicación.
--
-- En producción `pdv_perfiles` sería una synced table alimentada desde la capa
-- gold del lakehouse: los mismos features que entrenan el modelo se sirven aquí,
-- lo que elimina el desfase entre entrenamiento y serving.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS campo;

-- Perfil operativo del punto de venta. Cambia lento (horas), se lee muchísimo.
CREATE TABLE IF NOT EXISTS campo.pdv_perfiles (
    store_id                TEXT PRIMARY KEY,
    nombre                  TEXT NOT NULL,
    canal                   TEXT NOT NULL,
    cadena                  TEXT NOT NULL,
    formato                 TEXT NOT NULL,
    ciudad                  TEXT NOT NULL,
    country_code            TEXT NOT NULL,
    pais                    TEXT,
    mercaderista            TEXT,
    visitas_mes_meta        INT  NOT NULL DEFAULT 4,
    -- Features de comportamiento agregados desde el histórico de visitas.
    categorias_prioritarias TEXT[]        NOT NULL DEFAULT '{}',
    skus_foco               TEXT[]        NOT NULL DEFAULT '{}',
    disponibilidad_hist     NUMERIC(5,2)  NOT NULL DEFAULT 0,
    ejecucion_hist          NUMERIC(5,2)  NOT NULL DEFAULT 0,
    sos_hist                NUMERIC(5,2)  NOT NULL DEFAULT 0,
    -- 0..1 — probabilidad histórica de encontrar un quiebre en este PDV.
    riesgo_quiebre          NUMERIC(4,3)  NOT NULL DEFAULT 0,
    ticket_categoria_usd    NUMERIC(10,2) NOT NULL DEFAULT 0,
    ultima_visita           TIMESTAMPTZ,
    actualizado_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pdv_mercaderista ON campo.pdv_perfiles (mercaderista);
CREATE INDEX IF NOT EXISTS idx_pdv_pais         ON campo.pdv_perfiles (country_code);
CREATE INDEX IF NOT EXISTS idx_pdv_riesgo       ON campo.pdv_perfiles (riesgo_quiebre DESC);

-- Log de cada sugerencia servida y de lo que el mercaderista hizo con ella.
-- Sostiene el panel de SLA y, sobre todo, cierra el ciclo: una recomendación que
-- nadie ejecuta no vale nada, así que la tasa de ejecución se mide, no se supone.
-- En producción esta misma tabla es el dataset de retroalimentación del ranking.
CREATE TABLE IF NOT EXISTS campo.sugerencias_log (
    id              BIGSERIAL PRIMARY KEY,
    store_id        TEXT NOT NULL,
    categoria_foco  TEXT,
    acciones        JSONB NOT NULL,
    skus            TEXT[] NOT NULL DEFAULT '{}',
    rationale       TEXT,
    impacto_usd     NUMERIC(12,2) NOT NULL DEFAULT 0,
    latency_ms      INT NOT NULL,
    served_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ciclo de ejecución. Va con ALTER y no dentro del CREATE para que una instancia
-- ya sembrada se actualice sin perder el log.
--   servida   → el plan llegó al celular y todavía nadie lo tocó
--   ejecutada → el mercaderista corrigió todo lo que se le pidió
--   parcial   → corrigió parte (lo normal: no siempre hay producto en bodega)
--   omitida   → cerró la visita sin ejecutar nada del plan
ALTER TABLE campo.sugerencias_log
    ADD COLUMN IF NOT EXISTS estado                TEXT NOT NULL DEFAULT 'servida',
    ADD COLUMN IF NOT EXISTS mercaderista          TEXT,
    ADD COLUMN IF NOT EXISTS skus_ejecutados       TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS impacto_ejecutado_usd NUMERIC(12,2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ejecutado_at          TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS nota_cierre           TEXT;

CREATE INDEX IF NOT EXISTS idx_sug_served ON campo.sugerencias_log (served_at DESC);
CREATE INDEX IF NOT EXISTS idx_sug_store  ON campo.sugerencias_log (store_id, served_at DESC);
-- El feed pide "lo que está pendiente de ejecutar" varias veces por segundo.
CREATE INDEX IF NOT EXISTS idx_sug_estado ON campo.sugerencias_log (estado, served_at DESC);

-- Historial del chat de Genie. Vive aquí y no en Delta porque son escrituras
-- pequeñas y constantes: exactamente el patrón que Delta hace mal y Postgres bien.
CREATE TABLE IF NOT EXISTS public.genie_interactions (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT,
    message_id      TEXT,
    user_email      TEXT,
    question        TEXT NOT NULL,
    answer          TEXT,
    sql_query       TEXT,
    status          TEXT,
    row_count       INT,
    has_result      BOOLEAN DEFAULT FALSE,
    error           TEXT,
    duration_ms     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_genie_created ON public.genie_interactions (created_at DESC);
