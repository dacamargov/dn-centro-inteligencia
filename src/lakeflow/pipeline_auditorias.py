# Databricks notebook source
# MAGIC %md
# MAGIC # Lakeflow · Pipeline declarativo de auditorías de anaquel
# MAGIC
# MAGIC Ingesta end-to-end del **dato crudo** que aterriza StoreConnect AI en el
# MAGIC Volume `landing/auditorias/`, gobernada de principio a fin por Unity Catalog:
# MAGIC
# MAGIC ```
# MAGIC   Volume (JSON crudo)
# MAGIC        │  Auto Loader (cloudFiles, incremental)
# MAGIC        ▼
# MAGIC   auditorias_bronze    ← todo lo que llegó, con linaje de archivo
# MAGIC        │  tipado + expectativas de calidad + dedupe
# MAGIC        ▼
# MAGIC   auditorias_silver    ← limpio, enriquecido con maestros gobernados
# MAGIC        │  agregación de negocio
# MAGIC        ▼
# MAGIC   ejecucion_pdv_gold   ← KPIs de ejecución por tienda/categoría (consumo)
# MAGIC ```
# MAGIC
# MAGIC Las **expectativas** (`@dlt.expect_*`) son el control de calidad declarativo:
# MAGIC quedan registradas en el event log del pipeline con el porcentaje de filas que
# MAGIC pasaron, así la calidad del dato se mide y no se asume.
# MAGIC
# MAGIC El pipeline escribe en el **mismo esquema de Unity Catalog** que consume el
# MAGIC resto del journey (dashboard, Genie, agentes), así que la ingesta no es un
# MAGIC silo: `ejecucion_pdv_gold` es la capa gobernada que alimenta la analítica.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F

# El pipeline recibe catálogo/esquema como configuración (spark conf). El target
# del pipeline (catalog/schema) lo fija el recurso del bundle; estas dos sólo se
# usan para leer los maestros y construir la ruta del Volume de aterrizaje.
CATALOG = spark.conf.get("dn.catalog", "main")
SCHEMA = spark.conf.get("dn.schema", "ditcher_neira")
FQ = f"{CATALOG}.{SCHEMA}"
LANDING = f"/Volumes/{CATALOG}/{SCHEMA}/landing/auditorias"

# COMMAND ----------

# ── BRONZE ───────────────────────────────────────────────────────────────────
# Auto Loader ingiere incrementalmente cada archivo nuevo del Volume. Guarda el
# dato tal cual llegó más el linaje (archivo de origen e instante de ingesta):
# es la copia fiel e inmutable del crudo, la red de seguridad del pipeline.
@dlt.table(
    name="auditorias_bronze",
    comment="Lecturas crudas de anaquel (StoreConnect AI) ingeridas con Auto Loader, con linaje de archivo.",
    table_properties={"quality": "bronze", "pipelines.reset.allowed": "true"},
)
def auditorias_bronze():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .load(LANDING)
        .withColumn("_archivo_origen", F.col("_metadata.file_path"))
        .withColumn("_ingesta_ts", F.current_timestamp())
    )

# COMMAND ----------

# ── SILVER ───────────────────────────────────────────────────────────────────
# Tipa, valida y enriquece. Las expectativas son el contrato de calidad:
#   * las críticas (expect_or_drop) descartan la fila que no sirve;
#   * las informativas (expect) sólo miden, sin bloquear.
# El enriquecimiento une contra los maestros gobernados en UC (productos, tiendas,
# países) para derivar lo que el crudo no trae: dimensiones, precio normalizado a
# USD y share-of-shelf exacto calculado sobre las caras de esa misma visita.
_productos = spark.read.table(f"{FQ}.productos")
_tiendas = spark.read.table(f"{FQ}.tiendas")
_paises = spark.read.table(f"{FQ}.paises")


@dlt.table(
    name="auditorias_silver",
    comment="Auditorías limpias, tipadas y enriquecidas con maestros gobernados. SoS exacto por visita.",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("store_id_presente", "store_id IS NOT NULL")
@dlt.expect_or_drop("sku_presente", "sku IS NOT NULL")
@dlt.expect_or_drop("facings_no_negativo", "facings >= 0")
@dlt.expect_or_drop("confianza_valida", "confianza_ir BETWEEN 0 AND 1")
@dlt.expect_or_drop("visit_ts_presente", "visit_ts IS NOT NULL")
@dlt.expect("stock_con_precio", "NOT en_stock OR precio_local IS NOT NULL")
@dlt.expect("confianza_alta_ir", "confianza_ir >= 0.80")
def auditorias_silver():
    # Vista materializada (batch sobre bronze) y no streaming: el share-of-shelf
    # exacto usa una window por visita (SUM de caras), y Structured Streaming sólo
    # admite agregaciones por ventana de tiempo. Recalcular completo sobre la
    # ventana viva es barato y habilita la window. Bronze sí es incremental.
    bronze = (
        dlt.read("auditorias_bronze")
        .withColumn("visit_ts", F.to_timestamp("visit_ts"))
        .withColumn("facings", F.col("facings").cast("int"))
        .withColumn("precio_local", F.col("precio_local").cast("decimal(12,2)"))
        .withColumn("confianza_ir", F.col("confianza_ir").cast("decimal(5,3)"))
        # Dedupe defensivo: un mismo visita_id no debe contarse dos veces aunque
        # un archivo se reprocese.
        .dropDuplicates(["visita_id"])
    )

    # `productos` ya trae fabricante, categoría, marca y es_cliente (el flag de
    # cliente del estudio), así que el enriquecimiento de SKU sale de un solo join;
    # `tiendas` aporta las dimensiones de punto de venta y `paises` el factor FX.
    enriquecido = (
        bronze.join(
            F.broadcast(_productos.select(
                "sku", "marca", "fabricante", "categoria", "es_cliente")),
            "sku", "left")
        .join(
            F.broadcast(_tiendas.select(
                "store_id", "canal", "cadena", "ciudad", "country_code")),
            "store_id", "left")
        .join(F.broadcast(_paises.select("country_code", "fx_usd")), "country_code", "left")
        .withColumn("precio_usd",
                    F.when(F.col("precio_local").isNotNull() & (F.col("fx_usd") > 0),
                           F.round(F.col("precio_local") / F.col("fx_usd"), 2))
                     .cast("decimal(10,2)"))
        .withColumn("ejecucion_perfecta", F.col("en_stock") & F.col("planograma_ok"))
        .withColumn("visit_minute", F.date_trunc("minute", F.col("visit_ts")))
        .withColumn("es_cliente", F.coalesce(F.col("es_cliente"), F.lit(False)))
    )

    # Share-of-shelf exacto: caras del SKU sobre el total de caras observadas en
    # esa misma visita (el crudo no lo trae; acá se calcula con una window).
    from pyspark.sql.window import Window
    w = Window.partitionBy("visita_id")
    return enriquecido.withColumn(
        "share_of_shelf",
        F.when(F.sum("facings").over(w) > 0,
               F.round(F.col("facings") / F.sum("facings").over(w), 4))
         .otherwise(F.lit(0.0)).cast("decimal(6,4)"),
    )

# COMMAND ----------

# ── GOLD ─────────────────────────────────────────────────────────────────────
# La capa de consumo: KPIs de ejecución por tienda y categoría, listos para el
# dashboard, Genie y los agentes. Es una vista materializada (recalcula completa)
# porque son agregados sobre la ventana, no un append incremental.
@dlt.table(
    name="ejecucion_pdv_gold",
    comment="KPIs de ejecución por tienda y categoría derivados del pipeline de auditorías. Capa de consumo gobernada.",
    table_properties={"quality": "gold"},
)
@dlt.expect("tiene_observaciones", "observaciones > 0")
def ejecucion_pdv_gold():
    s = dlt.read("auditorias_silver")
    return (
        s.groupBy("store_id", "cadena", "ciudad", "country_code", "categoria")
        .agg(
            F.count("*").alias("observaciones"),
            F.round(F.avg(F.when(F.col("en_stock"), 100.0).otherwise(0.0)), 2).alias("disponibilidad_pct"),
            F.round(F.avg(F.when(F.col("ejecucion_perfecta"), 100.0).otherwise(0.0)), 2).alias("ejecucion_pct"),
            F.round(F.avg(F.when(F.col("en_promo"), 100.0).otherwise(0.0)), 2).alias("promo_pct"),
            F.round(F.when(F.sum("facings") > 0,
                           100.0 * F.sum(F.when(F.col("es_cliente"), F.col("facings")).otherwise(0))
                           / F.sum("facings")).otherwise(F.lit(0.0)), 2).alias("sos_cliente_pct"),
            F.round(F.avg("confianza_ir"), 3).alias("confianza_ir_prom"),
            F.max("visit_ts").alias("ultima_visita"),
        )
    )
