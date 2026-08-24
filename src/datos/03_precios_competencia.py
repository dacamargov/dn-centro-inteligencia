# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Price & Promo — fotografía de precios por cadena
# MAGIC
# MAGIC Corre como Job agendado cada 5 minutos. Cada tick toma una fotografía del precio
# MAGIC observado de cada SKU en cada cadena y país donde se audita.
# MAGIC
# MAGIC El indicador clave es el **índice de precio**: el precio del SKU frente al promedio
# MAGIC de su categoría en esa misma cadena y país, con base 100. Un índice de 112 significa
# MAGIC que el producto está 12% por encima del promedio de su categoría en ese anaquel;
# MAGIC es la lectura que usa un equipo de revenue growth para decidir si el precio está
# MAGIC fuera de rango frente a la competencia directa.
# MAGIC
# MAGIC A diferencia de `visitas`, esta tabla se **reemplaza completa** en cada tick: es
# MAGIC una foto del estado actual del mercado, no una serie histórica.

# COMMAND ----------

import random
from datetime import datetime, timezone
from decimal import Decimal

from pyspark.sql.types import (
    BooleanType, DecimalType, StringType, StructField, StructType, TimestampType,
)

try:
    dbutils.widgets.text("catalog", "main")
    dbutils.widgets.text("schema", "ditcher_neira")
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
except NameError:
    CATALOG, SCHEMA = "main", "ditcher_neira"

FQ = f"{CATALOG}.{SCHEMA}"

# La semilla depende del minuto: los precios se mueven entre tomas, pero de forma
# reproducible dentro de una misma toma.
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
random.seed(int(now_utc.timestamp()) // 300)

# COMMAND ----------

productos = spark.table(f"{FQ}.productos").select(
    "sku", "marca", "fabricante", "categoria", "subcategoria",
    "contenido_norm", "precio_sugerido_usd", "es_cliente"
).toPandas().sort_values("sku")

tiendas = spark.table(f"{FQ}.tiendas").select("cadena", "country_code", "canal").toPandas()

# Un par (país, cadena) por cada combinación realmente auditada.
plazas = sorted({(r.country_code, r.cadena) for r in tiendas.itertuples()})
print(f"{len(productos)} SKUs × {len(plazas)} plazas (país × cadena)")

# COMMAND ----------

# Postura de precio de cada cadena frente al promedio del mercado. Los clubes de
# precio y los formatos duros van sistemáticamente por debajo; los de conveniencia
# y proximidad, por encima. Es la estructura real del retail latinoamericano.
POSTURA_CADENA = {
    "PriceSmart": -0.10, "D1": -0.12, "Maxi Palí": -0.08, "Metro": -0.05,
    "Walmart": -0.04, "Tottus": -0.03, "Éxito": 0.00, "Olímpica": 0.02,
    "Supermaxi": 0.02, "Jumbo": 0.01, "Nacional": 0.03, "Plaza Vea": -0.01,
    "Wong": 0.06, "Automercado": 0.07, "Riba Smith": 0.05, "El Rey": 0.02,
    "Super 99": 0.00, "La Torre": 0.01, "Paiz": 0.02, "La Colonia": 0.02,
    "Súper Selectos": 0.01, "La Unión": 0.02, "Bravo": 0.03, "Mi Comisariato": 0.00,
    "Tía": -0.02, "Independiente": 0.09,
}

# Presión promocional por fabricante: qué tan seguido aparece en promoción.
# La competencia directa del cliente en Culinarios está empujando fuerte, que es
# la historia que el agente de Price & Promo va a levantar.
PRESION_PROMO = {
    "Nestlé": 0.20, "Unilever": 0.34, "P&G": 0.24, "Coca-Cola": 0.26,
    "PepsiCo": 0.25, "Colgate-Palmolive": 0.22, "Alpina": 0.20,
    "Dos Pinos": 0.19, "Gloria": 0.21, "Pozuelo": 0.28, "Grupo Bimbo": 0.23,
}

rows = []
for ccode, cadena in plazas:
    postura = POSTURA_CADENA.get(cadena, 0.0)
    for p in productos.itertuples():
        base = float(p.precio_sugerido_usd)
        fabricante = p.fabricante
        en_promo = random.random() < PRESION_PROMO.get(fabricante, 0.22)

        precio = base * (1.0 + postura + random.gauss(0.0, 0.035))
        if en_promo:
            # La profundidad se quedó en 8–20%, que es la banda real de promoción
            # en supermercado LATAM. Con descuentos de hasta 28% una subcategoría
            # de tres SKUs se desfondaba cuando dos competidores coincidían en
            # promo, y el índice del cliente saltaba a 140 sin que él tocara nada.
            precio *= (1.0 - random.uniform(0.08, 0.20))
        precio = max(0.05, round(precio, 2))

        rows.append({
            "country_code": ccode, "cadena": cadena, "categoria": p.categoria,
            "subcategoria": p.subcategoria, "sku": p.sku, "fabricante": fabricante,
            "marca": p.marca, "es_cliente": bool(p.es_cliente),
            "precio_usd": precio, "en_promo": en_promo,
            # precio por 100 g / 100 ml: la única base comparable entre empaques
            "precio_norm": precio / float(p.contenido_norm) * 100.0,
        })

# Índice de precio: 100 = paridad con el promedio de la SUBCATEGORÍA en esa misma
# plaza, comparando precio por contenido.
#
# Los dos ajustes importan. La subcategoría agrupa productos sustituibles entre sí
# (una leche en polvo no compite contra un yogurt). Y el precio por 100 g/ml elimina
# el efecto del tamaño de empaque, que si no domina el índice: una bolsa familiar
# siempre saldría "cara" frente a un sobre individual aunque rinda más por peso.
promedios = {}
for r in rows:
    k = (r["country_code"], r["cadena"], r["subcategoria"])
    promedios.setdefault(k, []).append(r["precio_norm"])
promedios = {k: (sum(v) / len(v)) for k, v in promedios.items()}

final = []
for r in rows:
    avg = promedios[(r["country_code"], r["cadena"], r["subcategoria"])] or 1.0
    final.append((
        now_utc, r["country_code"], r["cadena"], r["categoria"], r["subcategoria"],
        r["sku"], r["fabricante"], r["marca"], r["es_cliente"],
        Decimal(str(r["precio_usd"])), r["en_promo"],
        Decimal(str(round(r["precio_norm"] / avg * 100, 2))),
    ))

print(f"Filas generadas: {len(final)}")

# COMMAND ----------

precios_schema = StructType([
    StructField("snapshot_ts",   TimestampType(), False),
    StructField("country_code",  StringType(), False),
    StructField("cadena",        StringType(), False),
    StructField("categoria",     StringType(), False),
    StructField("subcategoria",  StringType(), False),
    StructField("sku",           StringType(), False),
    StructField("fabricante",    StringType(), False),
    StructField("marca",         StringType(), False),
    StructField("es_cliente",    BooleanType(), False),
    StructField("precio_usd",    DecimalType(10, 2), False),
    StructField("en_promo",      BooleanType(), False),
    StructField("indice_precio", DecimalType(6, 2), True),
])

# Reemplazo completo: es una foto del mercado ahora, no un histórico.
spark.createDataFrame(final, precios_schema) \
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{FQ}.precios_competencia")
print(f"precios_competencia reemplazada con {len(final)} filas")

# COMMAND ----------

# MAGIC %md ## Verificación — índice de precio del cliente por categoría

# COMMAND ----------

display(spark.sql(f"""
  SELECT
    categoria,
    ROUND(AVG(CASE WHEN es_cliente THEN indice_precio END), 1) AS indice_cliente,
    ROUND(AVG(CASE WHEN NOT es_cliente THEN indice_precio END), 1) AS indice_competencia,
    ROUND(AVG(CASE WHEN es_cliente AND en_promo THEN 100.0
                   WHEN es_cliente THEN 0.0 END), 1) AS promo_cliente_pct,
    ROUND(AVG(CASE WHEN NOT es_cliente AND en_promo THEN 100.0
                   WHEN NOT es_cliente THEN 0.0 END), 1) AS promo_competencia_pct
  FROM {FQ}.precios_competencia
  GROUP BY categoria ORDER BY categoria
"""))
