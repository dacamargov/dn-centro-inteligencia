# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Brand & Ad Insight — escucha social de marcas
# MAGIC
# MAGIC Corre como Job agendado cada minuto. Genera menciones a las marcas bajo medición
# MAGIC con sabor latinoamericano, clasificadas por sentimiento y con picos virales
# MAGIC ocasionales.
# MAGIC
# MAGIC En una implementación real esta tabla se alimenta de la API de las plataformas
# MAGIC sociales y el sentimiento sale de un modelo de clasificación. Acá el sentimiento
# MAGIC viene marcado desde la plantilla, para que la demo sea reproducible y no dependa
# MAGIC de inferencia.

# COMMAND ----------

import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pyspark.sql.types import (
    BooleanType, DecimalType, IntegerType, StringType, StructField, StructType, TimestampType,
)

try:
    dbutils.widgets.text("catalog", "main")
    dbutils.widgets.text("schema", "ditcher_neira")
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
except NameError:
    CATALOG, SCHEMA = "main", "ditcher_neira"

FQ = f"{CATALOG}.{SCHEMA}"
RETENTION_MINUTES = 90

# COMMAND ----------

PLATFORMS = [("x", 0.40), ("instagram", 0.32), ("tiktok", 0.18), ("facebook", 0.10)]

POSITIVAS = [
    "por fin encontré {prod} en el súper de la esquina, llevaba semanas buscándolo 🙌",
    "{marca} sacó promo de {prod} y quedó a mejor precio que la competencia 💸",
    "el {prod} de {marca} nunca falla, ya es parte de la despensa fija de la casa",
    "compré {prod} en {cadena} y estaba en oferta, buenísimo el 2x1 🛒",
    "la nueva presentación de {prod} rinde muchísimo más, {marca} se lució",
    "en {pais} por fin está llegando {prod} a las tiendas de barrio, gran movida de {marca}",
    "{prod} volvió al anaquel de {cadena} después de meses, ya era hora ✅",
]

NEGATIVAS = [
    "llevo tres semanas sin encontrar {prod} en ningún {cadena} de {pais} 😡",
    "subió otra vez el precio de {prod}, {marca} ya se pasó",
    "{prod} agotado en toda la zona, ¿alguien sabe dónde conseguirlo?",
    "la góndola de {marca} en {cadena} está vacía desde el lunes, pésima reposición",
    "compré {prod} y el empaque venía roto, {marca} debería revisar eso",
    "el precio de {prod} en {cadena} está 30% más caro que en el súper de al lado",
    "otra vez {prod} fuera de stock en {pais}, ya perdí la costumbre de comprarlo",
]

NEUTRALES = [
    "¿{prod} sale mejor en {cadena} o en la tienda de barrio?",
    "comparando precios de {prod} entre marcas antes de la compra del mes",
    "alguien ha probado la nueva versión de {prod} de {marca}?",
    "en {pais} {prod} cuesta el doble que hace dos años, ¿a alguien más le pasa?",
    "haciendo la lista del súper: {prod} y poco más",
]

# Un post viral no es siempre bueno. Cada plantilla trae su propio sentimiento y su
# peso: los virales positivos son la materia prima de una campaña de amplificación,
# y el negativo — más raro — es el que dispara al agente de sentimiento.
VIRALES = [
    ("🚨 {prod} está con 40% de descuento en {cadena} y nadie está hablando de esto 🚨", "positivo", 3),
    ("GENTE el precio de {prod} en {cadena} de {pais} es REAL, corran antes de que se acabe 🏃", "positivo", 3),
    ("no exagero: {prod} de {marca} es lo mejor que le pasó a mi despensa este año, hilo 🧵", "positivo", 3),
    ("{marca} escuchó a la gente y bajó {prod} en toda {pais}, así se hace 👏", "positivo", 2),
    ("hilo 🧵 de por qué {prod} desapareció de los anaqueles en medio {pais} y qué está pasando con {marca}", "negativo", 2),
]

NOMBRES = ["juan", "maria", "santi", "valen", "sofi", "andres", "camila", "dani",
           "laura", "nico", "gaby", "rodri", "flor", "seba", "pao"]

# COMMAND ----------

productos = spark.table(f"{FQ}.productos").select(
    "sku", "nombre", "marca", "fabricante", "categoria", "es_cliente"
).toPandas()

tiendas = spark.table(f"{FQ}.tiendas").select("cadena", "country_code").toPandas()
paises = spark.table(f"{FQ}.paises").select("country_code", "pais").toPandas()
PAIS_NOMBRE = {r.country_code: r.pais for r in paises.itertuples()}
CADENAS = sorted({r.cadena for r in tiendas.itertuples() if r.cadena != "Independiente"})

now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

# La mezcla de sentimiento rota entre estados: así el termómetro de marca se mueve
# durante la demo en lugar de quedarse clavado en un valor.
#
# El termómetro puntúa 50 + (positivos - negativos)/total * 50, así que el saldo
# neto entre positivo y negativo es lo único que mueve la aguja. Las mezclas y sus
# pesos están calibrados para que la marca del cliente viva en "saludable" (70+) y
# baje a "en alerta" solo de vez en cuando: una marca líder no está en crisis
# permanente, y un termómetro clavado en rojo deja de significar algo.
MEZCLA = random.choices(
    [
        {"positivo": 0.62, "negativo": 0.13, "neutral": 0.25},  # buen momento de marca
        {"positivo": 0.55, "negativo": 0.20, "neutral": 0.25},  # día normal
        {"positivo": 0.44, "negativo": 0.31, "neutral": 0.25},  # tensión puntual
    ],
    weights=[0.40, 0.40, 0.20],
)[0]

# COMMAND ----------

# Igual que el generador de visitas: si la tabla está vacía o el dato quedó rancio
# tras una pausa, sembramos la ventana entera. El termómetro de marca mide sobre la
# última hora y con 20 posts recién nacidos abriría prácticamente en blanco.
ultimo_post = spark.sql(f"SELECT MAX(posted_at) AS m FROM {FQ}.social_posts").collect()[0]["m"]
rancio = ultimo_post is None or (now_utc - ultimo_post).total_seconds() > 20 * 60

if rancio:
    n_posts = random.randint(340, 420)
    spread_s = 70 * 60
    print(f"Dato social rancio o vacío: sembrando {n_posts} posts sobre los últimos 70 min")
else:
    n_posts = random.randint(14, 28)
    spread_s = 60

rows = []

for _ in range(n_posts):
    # El cliente concentra la conversación medida: es su estudio.
    prod = productos.sample(1, weights=productos["es_cliente"].map({True: 3.0, False: 1.0})).iloc[0]
    ccode = random.choice(list(PAIS_NOMBRE.keys()))
    ctx = {
        "prod": prod["nombre"],
        "marca": prod["marca"],
        "cadena": random.choice(CADENAS) if CADENAS else "el supermercado",
        "pais": PAIS_NOMBRE[ccode],
    }

    es_viral = random.random() < 0.10
    if es_viral:
        plantilla, sentiment, _ = random.choices(
            VIRALES, weights=[w for _, _, w in VIRALES]
        )[0]
        score = (
            random.uniform(0.55, 0.92) if sentiment == "positivo"
            else -random.uniform(0.55, 0.92)
        )
        engagement = random.randint(8000, 60000)
    else:
        sentiment = random.choices(
            ["positivo", "negativo", "neutral"],
            weights=[MEZCLA["positivo"], MEZCLA["negativo"], MEZCLA["neutral"]],
        )[0]
        if sentiment == "positivo":
            plantilla, score = random.choice(POSITIVAS), random.uniform(0.40, 0.85)
        elif sentiment == "negativo":
            plantilla, score = random.choice(NEGATIVAS), -random.uniform(0.40, 0.90)
        else:
            plantilla, score = random.choice(NEUTRALES), random.uniform(-0.15, 0.15)
        engagement = max(1, int(random.gauss(90, 70)))

    rows.append((
        f"post_{uuid.uuid4().hex[:14]}",
        random.choices([p for p, _ in PLATFORMS], weights=[w for _, w in PLATFORMS])[0],
        f"@{random.choice(NOMBRES)}{random.randint(1, 9999)}",
        random.choice([random.randint(50, 2000),
                       random.randint(2000, 50000),
                       random.randint(50000, 2_000_000)]),
        plantilla.format(**ctx),
        prod["marca"],
        prod["fabricante"],
        ccode,
        sentiment,
        Decimal(str(round(score, 3))),
        engagement,
        es_viral,
        now_utc - timedelta(seconds=random.randint(0, spread_s)),
    ))

schema = StructType([
    StructField("post_id",          StringType(), False),
    StructField("platform",         StringType(), False),
    StructField("author_handle",    StringType(), False),
    StructField("author_followers", IntegerType(), True),
    StructField("content",          StringType(), False),
    StructField("marca",            StringType(), True),
    StructField("fabricante",       StringType(), True),
    StructField("country_code",     StringType(), True),
    StructField("sentiment",        StringType(), False),
    StructField("sentiment_score",  DecimalType(4, 3), False),
    StructField("engagement",       IntegerType(), False),
    StructField("is_viral",         BooleanType(), False),
    StructField("posted_at",        TimestampType(), False),
])

spark.createDataFrame(rows, schema) \
    .write.format("delta").mode("append").saveAsTable(f"{FQ}.social_posts")
print(f"Añadidos {len(rows)} posts (mezcla de sentimiento: {MEZCLA})")

# COMMAND ----------

spark.sql(f"""
    DELETE FROM {FQ}.social_posts
    WHERE posted_at < current_timestamp() - INTERVAL {RETENTION_MINUTES} MINUTES
""")

# COMMAND ----------

display(spark.sql(f"""
  SELECT fabricante, sentiment, COUNT(*) AS posts,
         SUM(engagement) AS engagement_total,
         SUM(CASE WHEN is_viral THEN 1 ELSE 0 END) AS virales
  FROM {FQ}.social_posts
  WHERE posted_at >= current_timestamp() - INTERVAL 10 MINUTES
  GROUP BY fabricante, sentiment
  ORDER BY fabricante, sentiment
"""))
