# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Motor de visitas a PDV (tick agendado)
# MAGIC
# MAGIC Corre como Job agendado cada minuto. Cada tick:
# MAGIC 1. Calcula cuántas **visitas de auditoría** ocurrieron desde el último evento.
# MAGIC 2. Cada visita audita el **planograma completo de una categoría** en un PDV:
# MAGIC    genera una observación por SKU de esa categoría (así es como trabaja
# MAGIC    StoreConnect AI — una foto del anaquel devuelve todas las caras a la vez).
# MAGIC 3. Escribe en `visitas`, refresca `ejecucion_realtime` y poda lo que salió
# MAGIC    de la ventana de retención.
# MAGIC
# MAGIC ## Por qué está construido así
# MAGIC
# MAGIC **El volumen se ata al tiempo transcurrido, no al tick.** El job está agendado
# MAGIC cada minuto, pero una corrida lenta hace que se salte la siguiente. Si el volumen
# MAGIC dependiera del tick, el ritmo real variaría según cuánto tarde el notebook.
# MAGIC
# MAGIC **La auditoría es por visita completa, no por SKU suelto.** Eso hace que el
# MAGIC `share_of_shelf` sea exacto: se calcula sobre las caras observadas en esa misma
# MAGIC visita, no contra un total estimado.
# MAGIC
# MAGIC **Los KPIs son porcentajes, así que son estables por construcción.** A diferencia
# MAGIC de una meta de venta acumulada —que sube sola con las horas— disponibilidad y
# MAGIC ejecución perfecta son niveles: se quedan donde el generador los pone sin importar
# MAGIC cuánto dure la presentación.

# COMMAND ----------

import math
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
    dbutils.widgets.text("backfill_min", "")
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
    BACKFILL_MIN = (dbutils.widgets.get("backfill_min") or "").strip()
except NameError:
    CATALOG, SCHEMA, BACKFILL_MIN = "main", "ditcher_neira", ""

FQ = f"{CATALOG}.{SCHEMA}"

# ── Reloj de auditoría ───────────────────────────────────────────────────────
VISITAS_POR_MINUTO = 12      # ~12 planogramas auditados por minuto en toda la red
MIN_GAP_S = 20               # piso: evita ticks minúsculos si dos corridas se pisan
MAX_GAP_S = 300              # techo: tras una pausa larga no hace un backfill gigante

# Onda de estacionalidad: mantiene el gráfico "vivo" con picos y valles sin mover
# el promedio de la ventana (es una integral analítica, no ruido aleatorio).
CLOCK_EPOCH = datetime(2026, 1, 1)
SEASON_PERIOD_MIN = 16.0
SEASON_AMPLITUDE = 0.20      # ±20% sobre el ritmo base


def audit_clock(ts):
    """Visitas teóricas acumuladas desde CLOCK_EPOCH hasta ts.

    rate(t) = VISITAS_POR_MINUTO * (1 + A·cos(2πt/P)); esta es su integral.
    """
    t = (ts - CLOCK_EPOCH).total_seconds() / 60.0
    wave = (SEASON_AMPLITUDE * SEASON_PERIOD_MIN / (2 * math.pi)
            * math.sin(2 * math.pi * t / SEASON_PERIOD_MIN))
    return VISITAS_POR_MINUTO * (t + wave)


# Retención: la demo es una ventana viva, no un histórico. Cada tick borra lo que
# salió de la ventana para que las tablas no crezcan sin control y los paneles
# midan siempre el estado actual de la red.
RETENTION_MINUTES = 90

# Arranque en frío. Los KPIs de esta demo son porcentajes, y un porcentaje sobre
# 20 observaciones se ve errático aunque el generador esté bien calibrado. Cuando
# la tabla está vacía llenamos la ventana de golpe, así el Centro de Inteligencia
# abre con métricas ya convergidas en lugar de con ruido durante los primeros minutos.
BACKFILL_DEFAULT_MIN = 75

# Una demo pausada ayer y encendida hoy deja la tabla con dato viejo, no vacía.
# Sin este umbral el tick incremental solo cubriría los últimos 5 minutos y los
# paneles abrirían casi en blanco, así que un hueco largo se trata como frío.
STALE_GAP_MIN = 20

# ── Calibración por categoría ────────────────────────────────────────────────
# p_stock       : probabilidad de encontrar el SKU en anaquel (disponibilidad / OSA)
# p_plano       : probabilidad de cumplir planograma, dado que hay stock
# f_cliente     : caras promedio de un SKU del fabricante cliente
# f_competencia : caras promedio de un SKU de la competencia
#
# La ejecución perfecta resultante es p_stock × p_plano. Los valores están elegidos
# para que cuatro categorías queden cerca de su meta y **Culinarios quede rezagada**,
# que es la que abre la conversación sobre qué hace el agente al respecto.
#
# El cociente f_cliente/f_competencia fija el share of shelf del cliente:
#   SOS = (n_cli · f_cli) / (n_cli · f_cli + n_comp · f_comp)
CALIBRACION = {
    #                        p_stock  p_plano  f_cliente  f_competencia
    "Bebidas Calientes":     (0.9605,  0.8908,     3.34,         3.70),
    "Lácteos":               (0.9605,  0.8908,     3.43,         4.00),
    "Culinarios":            (0.8788,  0.8276,     2.88,         4.80),
    "Confitería y Snacks":   (0.9401,  0.8657,     3.01,         4.90),
    "Bebidas No Alcohólicas": (0.9708, 0.9029,     4.04,         4.60),
}

P_PROMO = 0.21               # participación en promoción típica de la región
DESVIO_PRECIO_SIGMA = 0.045  # dispersión del precio observado vs PVP sugerido
DESCUENTO_PROMO = (0.10, 0.28)

# Cuánto tarda el mercaderista en leer cada SKU del anaquel.
#
# Antes todas las observaciones de una visita compartían un único timestamp, y eso
# rompía el ticker de "lecturas en vivo": las 20 filas más recientes eran en
# realidad dos visitas, todas con la misma hora y la misma tienda, así que el
# panel se veía congelado. Dándole su propio segundo a cada lectura, la red
# produce ~2 lecturas por segundo (12 visitas/min × ~9 SKUs) y el flujo se puede
# revelar segundo a segundo.
SEGUNDOS_POR_SKU = 2.5

# COMMAND ----------

# MAGIC %md ## Cargar el universo medido

# COMMAND ----------

productos = spark.table(f"{FQ}.productos").select(
    "sku", "nombre", "marca", "fabricante", "categoria",
    "precio_sugerido_usd", "es_cliente"
).toPandas().sort_values("sku").reset_index(drop=True)

tiendas = spark.table(f"{FQ}.tiendas").select(
    "store_id", "canal", "cadena", "ciudad", "country_code"
).toPandas().sort_values("store_id").reset_index(drop=True)

paises = spark.table(f"{FQ}.paises").select("country_code", "moneda", "fx_usd").toPandas()
FX = {r.country_code: (r.moneda, float(r.fx_usd)) for r in paises.itertuples()}

# SKUs agrupados por categoría — cada visita audita una categoría completa.
skus_por_categoria = {}
for cat, grp in productos.groupby("categoria"):
    skus_por_categoria[cat] = [
        (r.sku, r.nombre, r.marca, r.fabricante, float(r.precio_sugerido_usd), bool(r.es_cliente))
        for r in grp.sort_values("sku").itertuples()
    ]

CATEGORIAS = sorted(c for c in skus_por_categoria if c in CALIBRACION)
tiendas_list = [
    (r.store_id, r.canal, r.cadena, r.ciudad, r.country_code)
    for r in tiendas.itertuples()
]

print(f"Universo: {len(productos)} SKUs · {len(tiendas_list)} PDV · {len(CATEGORIAS)} categorías")
for cat in CATEGORIAS:
    items = skus_por_categoria[cat]
    n_cli = sum(1 for i in items if i[5])
    p_stock, p_plano, f_cli, f_comp = CALIBRACION[cat]
    sos = (n_cli * f_cli) / (n_cli * f_cli + (len(items) - n_cli) * f_comp) * 100
    print(f"  {cat:<24} {len(items):>2} SKUs ({n_cli} cliente) · "
          f"ejecución esperada {p_stock * p_plano * 100:5.1f}% · SOS cliente {sos:4.1f}%")

# COMMAND ----------

# MAGIC %md ## Generar las visitas del intervalo

# COMMAND ----------

now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
last_visit = spark.sql(f"SELECT MAX(visit_ts) AS m FROM {FQ}.visitas").collect()[0]["m"]

if BACKFILL_MIN:
    # Backfill explícito pedido por quien ejecuta el notebook.
    gap_s = float(BACKFILL_MIN) * 60.0
    modo = f"backfill {BACKFILL_MIN} min"
elif last_visit is None or (now_utc - last_visit).total_seconds() > STALE_GAP_MIN * 60:
    # Tabla vacía o dato rancio: llenamos la ventana entera para no abrir con ruido.
    gap_s = BACKFILL_DEFAULT_MIN * 60.0
    modo = ("arranque en frío" if last_visit is None else "dato rancio")
    modo += f", backfill {BACKFILL_DEFAULT_MIN} min"
else:
    gap_s = min(MAX_GAP_S, max(MIN_GAP_S, (now_utc - last_visit).total_seconds()))
    modo = "tick incremental"

win_start = now_utc - timedelta(seconds=gap_s)

# Reparto determinístico por categoría: la diferencia de floors mantiene el conteo
# acumulado de cada categoría a menos de una visita de su valor teórico, sin
# necesidad de guardar estado entre ticks.
c_now, c_prev = audit_clock(now_utc), audit_clock(win_start)
share_cat = 1.0 / len(CATEGORIAS)

visitas_plan = []
for cat in CATEGORIAS:
    n = int(share_cat * c_now) - int(share_cat * c_prev)
    visitas_plan.extend([cat] * max(0, n))
random.shuffle(visitas_plan)

print(f"{modo}: {gap_s:.0f}s → {len(visitas_plan)} visitas "
      f"(base {VISITAS_POR_MINUTO}/min, onda ±{SEASON_AMPLITUDE:.0%})")

# COMMAND ----------

rows = []
for cat in visitas_plan:
    store_id, canal, cadena, ciudad, ccode = random.choice(tiendas_list)
    moneda, fx = FX.get(ccode, ("USD", 1.0))
    p_stock, p_plano, f_cli, f_comp = CALIBRACION[cat]

    visita_id = f"VIS-{uuid.uuid4().hex[:14]}"
    auditor_id = f"AUD-{random.randint(1, 40):03d}"
    # Repartimos las visitas sobre el hueco real para que el flujo quede parejo
    # en el tiempo y no en ráfagas al final del minuto.
    #
    # Este es el instante en que la visita TERMINA, no en que empieza: las lecturas
    # de cada SKU se reparten hacia atrás desde acá. Contarlo hacia adelante
    # empujaría las últimas lecturas más allá de `now_utc` y la tabla acabaría con
    # dato del futuro, que envenena todos los agregados de la demo.
    visita_fin = now_utc - timedelta(seconds=random.uniform(0, gap_s))

    # El canal tradicional tiene anaqueles más chicos y peor ejecución que el moderno.
    ajuste_canal = 0.94 if canal == "Tradicional" else 1.0

    observaciones = []
    for sku, nombre, marca, fabricante, pvp, es_cliente in skus_por_categoria[cat]:
        en_stock = random.random() < (p_stock * ajuste_canal)
        if en_stock:
            media_f = f_cli if es_cliente else f_comp
            facings = max(1, int(round(random.gauss(media_f, 0.9))))
            planograma_ok = random.random() < (p_plano * ajuste_canal)
        else:
            facings = 0
            planograma_ok = False

        en_promo = random.random() < P_PROMO
        desvio = random.gauss(0.0, DESVIO_PRECIO_SIGMA)
        precio_usd = pvp * (1.0 + desvio)
        if en_promo:
            precio_usd *= (1.0 - random.uniform(*DESCUENTO_PROMO))
        precio_usd = max(0.05, round(precio_usd, 2))

        observaciones.append({
            "sku": sku, "marca": marca, "fabricante": fabricante,
            "es_cliente": es_cliente, "facings": facings, "en_stock": en_stock,
            "planograma_ok": planograma_ok, "en_promo": en_promo,
            "precio_usd": precio_usd,
        })

    # share_of_shelf real: caras del SKU sobre el total de caras vistas en ESA visita.
    # Se calcula sobre la visita completa, así que no depende de cómo se reparten
    # los timestamps.
    total_facings = sum(o["facings"] for o in observaciones)

    # El recorrido del anaquel no sigue el orden del catálogo. Sin esto, la lectura
    # más nueva de cada visita sería siempre el último SKU de la categoría y el
    # tope del ticker rotaría entre apenas cinco productos.
    random.shuffle(observaciones)

    ultimo = len(observaciones) - 1
    for i, o in enumerate(observaciones):
        sos = (o["facings"] / total_facings) if total_facings > 0 else 0.0
        ejecucion = o["en_stock"] and o["planograma_ok"]
        # Hacia atrás desde el fin de la visita: el último SKU leído se queda en
        # `visita_fin` y los anteriores retroceden unos segundos cada uno.
        lectura_ts = visita_fin - timedelta(
            seconds=(ultimo - i) * SEGUNDOS_POR_SKU * random.uniform(0.6, 1.4)
        )
        rows.append((
            visita_id, store_id, o["sku"], lectura_ts, auditor_id,
            o["facings"],
            Decimal(str(round(o["precio_usd"] * fx, 2))),
            moneda,
            Decimal(str(o["precio_usd"])),
            o["en_stock"], o["en_promo"], o["planograma_ok"],
            Decimal(str(round(sos, 4))),
            Decimal(str(round(random.uniform(0.82, 0.99), 3))),
            ejecucion,
            canal, cadena, ciudad, ccode,
            o["marca"], o["fabricante"], cat, o["es_cliente"],
            lectura_ts.replace(second=0, microsecond=0),
        ))

print(f"Observaciones generadas: {len(rows)}")

# COMMAND ----------

visitas_schema = StructType([
    StructField("visita_id",          StringType(), False),
    StructField("store_id",           StringType(), False),
    StructField("sku",                StringType(), False),
    StructField("visit_ts",           TimestampType(), False),
    StructField("auditor_id",         StringType(), False),
    StructField("facings",            IntegerType(), False),
    StructField("precio_local",       DecimalType(12, 2), True),
    StructField("moneda",             StringType(), False),
    StructField("precio_usd",         DecimalType(10, 2), True),
    StructField("en_stock",           BooleanType(), False),
    StructField("en_promo",           BooleanType(), False),
    StructField("planograma_ok",      BooleanType(), False),
    StructField("share_of_shelf",     DecimalType(6, 4), False),
    StructField("confianza_ir",       DecimalType(5, 3), False),
    StructField("ejecucion_perfecta", BooleanType(), False),
    StructField("canal",              StringType(), False),
    StructField("cadena",             StringType(), False),
    StructField("ciudad",             StringType(), False),
    StructField("country_code",       StringType(), False),
    StructField("marca",              StringType(), False),
    StructField("fabricante",         StringType(), False),
    StructField("categoria",          StringType(), False),
    StructField("es_cliente",         BooleanType(), False),
    StructField("visit_minute",       TimestampType(), False),
])

if rows:
    spark.createDataFrame(rows, visitas_schema) \
        .write.format("delta").mode("append").saveAsTable(f"{FQ}.visitas")
    print(f"Escritas {len(rows)} observaciones en {FQ}.visitas")
else:
    print("Sin observaciones en este tick (hueco demasiado corto)")

# COMMAND ----------

# MAGIC %md ## Refrescar agregados por minuto (ventana móvil de 30 min)

# COMMAND ----------

spark.sql(f"""
DELETE FROM {FQ}.ejecucion_realtime
WHERE minute_ts >= current_timestamp() - INTERVAL 30 MINUTES
""")

spark.sql(f"""
INSERT INTO {FQ}.ejecucion_realtime
SELECT
  visit_minute AS minute_ts,
  country_code,
  categoria,
  COUNT(*) AS observaciones,
  CAST(AVG(CASE WHEN en_stock THEN 100.0 ELSE 0.0 END) AS DECIMAL(5,2)) AS disponibilidad_pct,
  CAST(AVG(CASE WHEN ejecucion_perfecta THEN 100.0 ELSE 0.0 END) AS DECIMAL(5,2)) AS ejecucion_pct,
  CAST(
    COALESCE(
      SUM(CASE WHEN es_cliente THEN facings ELSE 0 END) * 100.0 / NULLIF(SUM(facings), 0),
      0
    ) AS DECIMAL(5,2)
  ) AS sos_cliente_pct,
  CAST(AVG(CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) AS DECIMAL(5,2)) AS promo_pct
FROM {FQ}.visitas
WHERE visit_minute >= current_timestamp() - INTERVAL 30 MINUTES
GROUP BY visit_minute, country_code, categoria
""")

# COMMAND ----------

# MAGIC %md ## Poda — mantiene solo la ventana viva

# COMMAND ----------

for tbl, ts_col in [
    (f"{FQ}.visitas", "visit_ts"),
    (f"{FQ}.ejecucion_realtime", "minute_ts"),
]:
    spark.sql(f"""
        DELETE FROM {tbl}
        WHERE {ts_col} < current_timestamp() - INTERVAL {RETENTION_MINUTES} MINUTES
    """)
print(f"Podadas las filas con más de {RETENTION_MINUTES} min")

# COMMAND ----------

# MAGIC %md ## Verificación

# COMMAND ----------

display(spark.sql(f"""
  SELECT
    categoria,
    COUNT(*) AS observaciones,
    ROUND(AVG(CASE WHEN en_stock THEN 100.0 ELSE 0.0 END), 1) AS disponibilidad_pct,
    ROUND(AVG(CASE WHEN ejecucion_perfecta THEN 100.0 ELSE 0.0 END), 1) AS ejecucion_pct,
    ROUND(SUM(CASE WHEN es_cliente THEN facings ELSE 0 END) * 100.0
          / NULLIF(SUM(facings), 0), 1) AS sos_cliente_pct
  FROM {FQ}.visitas
  GROUP BY categoria ORDER BY categoria
"""))
