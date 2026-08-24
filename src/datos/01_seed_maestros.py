# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Semilla de maestros — países, fabricantes, SKUs, PDV y metas
# MAGIC
# MAGIC Notebook de una sola corrida. Se ejecuta una vez tras crear el esquema, o cuando
# MAGIC cambie la definición del universo medido. Es **idempotente**: reescribe las tablas
# MAGIC maestras completas, así que es seguro re-ejecutarlo.
# MAGIC
# MAGIC Contexto: **dichter & neira** mide ejecución en el punto de venta y desempeño de
# MAGIC categorías para marcas de consumo masivo en Latinoamérica. El fabricante marcado
# MAGIC como `es_cliente` es quien contrata el estudio; el resto del universo es la
# MAGIC competencia contra la que se calcula participación.
# MAGIC
# MAGIC Todos los datos son **sintéticos**. Las marcas y cadenas son reales solo como
# MAGIC ambientación del mercado LATAM; ninguna cifra proviene de una fuente real.

# COMMAND ----------

import random
from decimal import Decimal

from pyspark.sql import Row
from pyspark.sql.types import (
    BooleanType, DecimalType, DoubleType, IntegerType, StringType, StructField, StructType,
)

# Semilla fija: el universo medido debe ser idéntico en cada corrida para que las
# métricas del demo sean comparables entre sesiones.
random.seed(2026)

try:
    dbutils.widgets.text("catalog", "main")
    dbutils.widgets.text("schema", "ditcher_neira")
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
except NameError:
    CATALOG, SCHEMA = "main", "ditcher_neira"

FQ = f"{CATALOG}.{SCHEMA}"
print(f"Destino: {FQ}")

# COMMAND ----------

# MAGIC %md ## 1 · Países — huella real de operación de D&N en LATAM

# COMMAND ----------

# (código, país, moneda, unidades de moneda local por USD, región comercial D&N)
PAISES = [
    ("PA", "Panamá",             "USD",    1.00,   "North Latam"),
    ("GT", "Guatemala",          "GTQ",    7.80,   "North Latam"),
    ("CR", "Costa Rica",         "CRC",  515.00,   "North Latam"),
    ("HN", "Honduras",           "HNL",   24.70,   "North Latam"),
    ("SV", "El Salvador",        "USD",    1.00,   "North Latam"),
    ("NI", "Nicaragua",          "NIO",   36.80,   "North Latam"),
    ("DO", "República Dominicana", "DOP", 59.00,   "North Latam"),
    ("CO", "Colombia",           "COP", 4050.00,   "South Latam"),
    ("EC", "Ecuador",            "USD",    1.00,   "South Latam"),
    ("PE", "Perú",               "PEN",    3.75,   "South Latam"),
]

paises_schema = StructType([
    StructField("country_code", StringType(), False),
    StructField("pais",         StringType(), False),
    StructField("moneda",       StringType(), False),
    StructField("fx_usd",       DecimalType(12, 4), False),
    StructField("region_dn",    StringType(), False),
])

df_paises = spark.createDataFrame(
    [Row(country_code=c, pais=p, moneda=m, fx_usd=Decimal(str(fx)), region_dn=r)
     for c, p, m, fx, r in PAISES],
    schema=paises_schema,
)
df_paises.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.paises")
print(f"paises: {df_paises.count()} filas")

# COMMAND ----------

# MAGIC %md ## 2 · Fabricantes — el cliente del estudio y su competencia

# COMMAND ----------

# El fabricante cliente es quien contrata la medición. Su `share_objetivo_pct` es la
# participación de anaquel que su equipo comercial se comprometió a alcanzar.
# (fabricante, es_cliente, color, share objetivo)
FABRICANTES = [
    ("Nestlé",          True,  "#0D5CAB", 32.0),
    ("Unilever",        False, "#33BDEE", None),
    ("P&G",             False, "#24335F", None),
    ("Coca-Cola",       False, "#C8102E", None),
    ("PepsiCo",         False, "#1C293A", None),
    ("Colgate-Palmolive", False, "#969CA2", None),
    ("Alpina",          False, "#5B8DEF", None),
    ("Dos Pinos",       False, "#7FB3D5", None),
    ("Gloria",          False, "#A9CCE3", None),
    ("Pozuelo",         False, "#BFC9D4", None),
    ("Grupo Bimbo",     False, "#8E9AAF", None),
]

CLIENTE = "Nestlé"

fab_schema = StructType([
    StructField("fabricante",         StringType(), False),
    StructField("es_cliente",         BooleanType(), False),
    StructField("color_hex",          StringType(), True),
    StructField("share_objetivo_pct", DecimalType(5, 2), True),
])

df_fab = spark.createDataFrame(
    [Row(fabricante=f, es_cliente=c, color_hex=col,
         share_objetivo_pct=(Decimal(str(s)) if s is not None else None))
     for f, c, col, s in FABRICANTES],
    schema=fab_schema,
)
df_fab.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.fabricantes")
print(f"fabricantes: {df_fab.count()} filas · cliente = {CLIENTE}")

# COMMAND ----------

# MAGIC %md ## 3 · Catálogo de SKUs auditados
# MAGIC
# MAGIC Cinco categorías donde compite el fabricante cliente. Cada SKU lleva su PVP
# MAGIC sugerido en USD, que es la base contra la que se miden los desvíos de precio
# MAGIC observados en anaquel.

# COMMAND ----------

# categoría -> subcategoría -> lista de (marca, fabricante, producto, presentación, PVP USD, emoji)
#
# La proporción de SKUs del cliente frente a la competencia está deliberadamente
# balanceada: el cliente es un jugador fuerte pero no dominante, que es lo que hace
# que el share of shelf medido sea una conversación interesante y no un número fijo.
CATALOGO = {
    "Bebidas Calientes": {
        "Café soluble": [
            ("Nescafé",      "Nestlé",      "Nescafé Clásico",             "170 g",  6.90, "☕"),
            ("Nescafé",      "Nestlé",      "Nescafé Tradición",           "100 g",  4.50, "☕"),
            ("Juan Valdez",  "Alpina",      "Juan Valdez Soluble",         "170 g",  7.40, "☕"),
        ],
        # El molido va aparte del soluble a propósito: rinde muy distinto por gramo,
        # así que mezclarlos haría que el índice de precio comparara peras con manzanas.
        "Café molido": [
            ("Café Britt",   "Pozuelo",     "Café Britt Molido",           "340 g",  8.20, "☕"),
            ("Café León",    "Pozuelo",     "Café León Molido",            "460 g",  6.10, "☕"),
        ],
        "Modificadores lácteos": [
            ("Nesquik",      "Nestlé",      "Nesquik Chocolate",           "400 g",  4.80, "🥤"),
            ("Milo",         "Nestlé",      "Milo Activ-Go",               "400 g",  5.40, "🥤"),
            ("Toddy",        "PepsiCo",     "Toddy Chocolate",             "400 g",  4.50, "🥤"),
            ("Corona",       "Grupo Bimbo", "Chocolate Corona",            "400 g",  4.20, "🍫"),
        ],
        "Té e infusiones": [
            ("Lipton",       "Unilever",    "Lipton Té Negro",             "25 sobres", 2.30, "🍵"),
            ("Hindú",        "Alpina",      "Hindú Manzanilla",            "25 sobres", 1.80, "🍵"),
        ],
    },
    "Lácteos": {
        "Leche en polvo": [
            ("Nido",         "Nestlé",      "Nido Fortificada",            "800 g", 11.50, "🥛"),
            ("Nido",         "Nestlé",      "Nido Crecimiento 1+",         "800 g", 13.20, "🥛"),
            ("Svelty",       "Nestlé",      "Svelty Deslactosada",         "700 g", 10.80, "🥛"),
            ("Gloria",       "Gloria",      "Gloria Leche en Polvo",       "800 g",  9.90, "🥛"),
            ("Alpina",       "Alpina",      "Alpina Entera en Polvo",      "760 g", 10.20, "🥛"),
            ("Anchor",       "Dos Pinos",   "Anchor Leche en Polvo",       "900 g", 11.80, "🥛"),
        ],
        "Leche condensada": [
            ("La Lechera",   "Nestlé",      "La Lechera Condensada",       "395 g",  2.90, "🍮"),
            ("La Lechera",   "Nestlé",      "La Lechera Crema",            "300 g",  2.40, "🍮"),
            ("Dos Pinos",    "Dos Pinos",   "Dos Pinos Leche Condensada",  "397 g",  2.75, "🍮"),
        ],
        "Leche evaporada": [
            ("Ideal",        "Nestlé",      "Nestlé Ideal Evaporada",      "410 g",  2.10, "🥫"),
            ("Gloria",       "Gloria",      "Gloria Leche Evaporada",      "410 g",  1.95, "🥫"),
        ],
        "Yogurt": [
            ("Alpina",       "Alpina",      "Alpina Yogurt Griego",        "150 g",  1.35, "🥣"),
            ("Dos Pinos",    "Dos Pinos",   "Dos Pinos Yogurt Natural",    "200 g",  1.20, "🥣"),
        ],
    },
    "Culinarios": {
        # Culinarios es la categoría tensionada de la demo: el cliente quedó por encima
        # de la banda de precio justo donde la competencia empuja más promoción. Los
        # PVP de abajo dejan el índice del cliente cerca de 118, no por accidente.
        # Los PVP están puestos en precio por 100 g, no al ojo: el índice compara
        # por contenido, así que un sazonador de 100 g y un caldo de 8 cubos (88 g)
        # solo son comparables si sus precios por gramo lo son. Con esta escala el
        # cliente queda entre 106 y 117 — caro y discutible, que es donde el
        # simulador tiene algo que proponer. A 130+ ninguna estrategia cierra.
        "Caldos y sopas": [
            ("Maggi",        "Nestlé",      "Maggi Caldo de Pollo",        "8 cubos", 1.58, "🍲"),
            ("Maggi",        "Nestlé",      "Maggi Sopa de Fideos",        "60 g",    1.02, "🍲"),
            ("Maggi",        "Nestlé",      "Maggi Sazonador Completo",    "100 g",   1.88, "🍲"),
            ("Knorr",        "Unilever",    "Knorr Caldo de Costilla",     "8 cubos", 1.43, "🍲"),
            ("Knorr",        "Unilever",    "Knorr Crema de Champiñones",  "70 g",    1.09, "🍲"),
            ("Malher",       "Pozuelo",     "Malher Sopa de Pollo",        "57 g",    0.74, "🍲"),
            ("Naturas",      "Grupo Bimbo", "Naturas Consomé de Pollo",    "100 g",   1.40, "🍲"),
        ],
        "Salsas y aderezos": [
            ("Maggi",        "Nestlé",      "Maggi Salsa de Tomate",       "400 g",  2.00, "🍅"),
            ("Knorr",        "Unilever",    "Knorr Mayonesa",              "400 g",  2.60, "🥫"),
            ("Ducal",        "Pozuelo",     "Ducal Frijoles Molidos",      "400 g",  1.45, "🥫"),
            ("Kern's",       "Grupo Bimbo", "Kern's Salsa de Tomate",      "397 g",  1.35, "🍅"),
        ],
    },
    "Confitería y Snacks": {
        "Chocolates": [
            ("Crunch",       "Nestlé",      "Nestlé Crunch",               "40 g",   1.10, "🍫"),
            ("KitKat",       "Nestlé",      "KitKat 4 Fingers",            "41 g",   1.25, "🍫"),
            ("Galak",        "Nestlé",      "Galak Chocolate Blanco",      "35 g",   1.05, "🍫"),
            ("Snickers",     "Grupo Bimbo", "Snickers",                    "50 g",   1.15, "🍫"),
            ("Ricolino",     "Grupo Bimbo", "Ricolino Paleta Payaso",      "45 g",   1.05, "🍭"),
        ],
        "Galletas": [
            ("Nestlé",       "Nestlé",      "Galletas Nestlé Surtidas",    "300 g",  3.10, "🍪"),
            ("Pozuelo",      "Pozuelo",     "Pozuelo Chikys",              "120 g",  1.30, "🍪"),
            ("Pozuelo",      "Pozuelo",     "Pozuelo María",               "200 g",  1.55, "🍪"),
            ("Bimbo",        "Grupo Bimbo", "Bimbo Panqué Casero",         "250 g",  2.80, "🍰"),
            ("Ricitos",      "Pozuelo",     "Ricitos de Oro",              "150 g",  1.25, "🍪"),
        ],
        "Snacks salados": [
            ("Lay's",        "PepsiCo",     "Lay's Clásicas",              "150 g",  2.30, "🥔"),
            ("Doritos",      "PepsiCo",     "Doritos Nacho",               "150 g",  2.45, "🌮"),
        ],
    },
    "Bebidas No Alcohólicas": {
        "Agua embotellada": [
            ("Pure Life",    "Nestlé",      "Nestlé Pure Life",            "600 ml", 0.75, "💧"),
            ("Pure Life",    "Nestlé",      "Nestlé Pure Life Familiar",   "1.5 L",  1.35, "💧"),
            ("Dasani",       "Coca-Cola",   "Dasani",                      "600 ml", 0.72, "💧"),
            ("Cristal",      "Alpina",      "Agua Cristal",                "600 ml", 0.68, "💧"),
        ],
        "Gaseosas": [
            ("Coca-Cola",    "Coca-Cola",   "Coca-Cola Original",          "1.5 L",  1.65, "🥤"),
            ("Sprite",       "Coca-Cola",   "Sprite",                      "1.5 L",  1.55, "🥤"),
            ("Fanta",        "Coca-Cola",   "Fanta Naranja",               "1.5 L",  1.50, "🥤"),
            ("Pepsi",        "PepsiCo",     "Pepsi",                       "1.5 L",  1.50, "🥤"),
        ],
        "Isotónicos y jugos": [
            ("Gatorade",     "PepsiCo",     "Gatorade Tropical",           "500 ml", 1.30, "🧃"),
            ("Powerade",     "Coca-Cola",   "Powerade Mora",               "500 ml", 1.25, "🧃"),
        ],
    },
}

# Equivalencia en gramos de las presentaciones que se venden por unidades. Sin esto
# no se puede calcular un precio por contenido, y el índice de precio compararía
# empaques de tamaños distintos.
EQUIVALENCIA_UNIDAD_G = {"cubos": 11.0, "sobres": 2.0}


def normalizar_contenido(presentacion):
    """Devuelve (cantidad, unidad) normalizada a gramos o mililitros."""
    cantidad_txt, unidad = presentacion.split(" ", 1)
    cantidad = float(cantidad_txt)
    unidad = unidad.strip().lower()
    if unidad == "l":
        return cantidad * 1000.0, "ml"
    if unidad == "ml":
        return cantidad, "ml"
    if unidad == "g":
        return cantidad, "g"
    if unidad in EQUIVALENCIA_UNIDAD_G:
        return cantidad * EQUIVALENCIA_UNIDAD_G[unidad], "g"
    raise ValueError(f"Presentación no reconocida: {presentacion!r}")


productos = []
sku_seq = 1
for categoria, subcats in CATALOGO.items():
    for subcategoria, items in subcats.items():
        for marca, fabricante, nombre, presentacion, pvp, emoji in items:
            contenido, unidad = normalizar_contenido(presentacion)
            productos.append(Row(
                sku=f"SKU-{sku_seq:04d}",
                nombre=nombre,
                marca=marca,
                fabricante=fabricante,
                categoria=categoria,
                subcategoria=subcategoria,
                presentacion=presentacion,
                contenido_norm=Decimal(str(round(contenido, 2))),
                unidad_norm=unidad,
                precio_sugerido_usd=Decimal(str(pvp)),
                es_cliente=(fabricante == CLIENTE),
                emoji=emoji,
            ))
            sku_seq += 1

prod_schema = StructType([
    StructField("sku",                 StringType(), False),
    StructField("nombre",              StringType(), False),
    StructField("marca",               StringType(), False),
    StructField("fabricante",          StringType(), False),
    StructField("categoria",           StringType(), False),
    StructField("subcategoria",        StringType(), True),
    StructField("presentacion",        StringType(), True),
    StructField("contenido_norm",      DecimalType(10, 2), False),
    StructField("unidad_norm",         StringType(), False),
    StructField("precio_sugerido_usd", DecimalType(10, 2), False),
    StructField("es_cliente",          BooleanType(), False),
    StructField("emoji",               StringType(), True),
])

df_prod = spark.createDataFrame(productos, schema=prod_schema)
df_prod.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.productos")
print(f"productos: {df_prod.count()} SKUs "
      f"({sum(1 for p in productos if p.es_cliente)} del cliente)")

# COMMAND ----------

# MAGIC %md ## 4 · Universo de puntos de venta
# MAGIC
# MAGIC Mezcla de canal moderno (cadenas por país) y canal tradicional (colmado, pulpería,
# MAGIC bodega — el nombre cambia según el país, igual que en la operación real).

# COMMAND ----------

# país -> cadenas de canal moderno con presencia real en ese mercado
CADENAS_MODERNO = {
    "PA": ["Super 99", "El Rey", "PriceSmart", "Riba Smith"],
    "GT": ["Walmart", "La Torre", "Paiz", "PriceSmart"],
    "CR": ["Automercado", "Walmart", "Maxi Palí", "PriceSmart"],
    "HN": ["La Colonia", "Walmart", "PriceSmart"],
    "SV": ["Súper Selectos", "Walmart", "PriceSmart"],
    "NI": ["La Unión", "Walmart", "Maxi Palí"],
    "DO": ["Jumbo", "Nacional", "PriceSmart", "Bravo"],
    "CO": ["Éxito", "Olímpica", "D1", "PriceSmart"],
    "EC": ["Supermaxi", "Mi Comisariato", "Tía"],
    "PE": ["Tottus", "Wong", "Plaza Vea", "Metro"],
}

# El canal tradicional se llama distinto en cada mercado.
NOMBRE_TRADICIONAL = {
    "PA": "Abarrotería", "GT": "Tienda de barrio", "CR": "Pulpería",
    "HN": "Pulpería",    "SV": "Tienda",           "NI": "Pulpería",
    "DO": "Colmado",     "CO": "Tienda de barrio", "EC": "Tienda",
    "PE": "Bodega",
}

FORMATOS_MODERNO = ["Hipermercado", "Supermercado", "Club de precio", "Conveniencia"]

CIUDADES = {
    "PA": ["Ciudad de Panamá", "David", "Colón"],
    "GT": ["Ciudad de Guatemala", "Quetzaltenango", "Escuintla"],
    "CR": ["San José", "Alajuela", "Heredia"],
    "HN": ["Tegucigalpa", "San Pedro Sula"],
    "SV": ["San Salvador", "Santa Ana"],
    "NI": ["Managua", "León"],
    "DO": ["Santo Domingo", "Santiago"],
    "CO": ["Bogotá", "Medellín", "Cali", "Barranquilla"],
    "EC": ["Quito", "Guayaquil", "Cuenca"],
    "PE": ["Lima", "Arequipa", "Trujillo"],
}

# Centro geográfico aproximado por país, para dispersar los PDV en el mapa.
GEO = {
    "PA": (8.98, -79.52), "GT": (14.63, -90.51), "CR": (9.93, -84.09),
    "HN": (14.07, -87.19), "SV": (13.69, -89.19), "NI": (12.11, -86.24),
    "DO": (18.49, -69.93), "CO": (4.71, -74.07),  "EC": (-0.18, -78.47),
    "PE": (-12.05, -77.04),
}

MERCADERISTAS = [
    "A. Rodríguez", "M. Fernández", "J. Castillo", "L. Mendoza", "C. Rojas",
    "P. Guzmán", "S. Herrera", "D. Vargas", "R. Salazar", "N. Bonilla",
    "V. Espinoza", "T. Aguilar", "F. Cordero", "G. Ramírez", "B. Navarro",
]

tiendas = []
store_seq = 1
for code, pais, _, _, _ in PAISES:
    lat0, lon0 = GEO[code]
    ciudades = CIUDADES[code]
    cadenas = CADENAS_MODERNO[code]
    # ~14 PDV por país: 9 canal moderno + 5 canal tradicional.
    for i in range(14):
        es_moderno = i < 9
        if es_moderno:
            cadena = cadenas[i % len(cadenas)]
            formato = ("Club de precio" if cadena == "PriceSmart"
                       else FORMATOS_MODERNO[i % len(FORMATOS_MODERNO)])
            canal = "Moderno"
            # El canal moderno se audita más seguido que el tradicional.
            visitas_mes = 4
        else:
            cadena = "Independiente"
            formato = NOMBRE_TRADICIONAL[code]
            canal = "Tradicional"
            visitas_mes = 2
        ciudad = ciudades[i % len(ciudades)]
        tiendas.append(Row(
            store_id=f"PDV-{store_seq:04d}",
            nombre=f"{cadena} {ciudad} #{store_seq}" if es_moderno
                   else f"{formato} {ciudad} #{store_seq}",
            canal=canal,
            cadena=cadena,
            formato=formato,
            ciudad=ciudad,
            country_code=code,
            latitude=round(lat0 + random.uniform(-0.45, 0.45), 5),
            longitude=round(lon0 + random.uniform(-0.45, 0.45), 5),
            mercaderista=MERCADERISTAS[store_seq % len(MERCADERISTAS)],
            visitas_mes_meta=visitas_mes,
        ))
        store_seq += 1

tiendas_schema = StructType([
    StructField("store_id",         StringType(), False),
    StructField("nombre",           StringType(), False),
    StructField("canal",            StringType(), False),
    StructField("cadena",           StringType(), False),
    StructField("formato",          StringType(), False),
    StructField("ciudad",           StringType(), False),
    StructField("country_code",     StringType(), False),
    StructField("latitude",         DoubleType(), False),
    StructField("longitude",        DoubleType(), False),
    StructField("mercaderista",     StringType(), True),
    StructField("visitas_mes_meta", IntegerType(), False),
])

df_tiendas = spark.createDataFrame(tiendas, schema=tiendas_schema)
df_tiendas.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.tiendas")
print(f"tiendas: {df_tiendas.count()} PDV en {len(PAISES)} países")

# COMMAND ----------

# MAGIC %md ## 5 · Metas de ejecución por categoría
# MAGIC
# MAGIC Son **niveles objetivo en porcentaje**, no acumulados. El panel "Meta vs Realizado"
# MAGIC compara nivel contra nivel, así que se mantiene estable sin importar cuánto tiempo
# MAGIC lleve corriendo la demo — a diferencia de una meta de venta acumulada, que sube
# MAGIC sola con las horas.
# MAGIC
# MAGIC Están calibradas contra lo que produce `02_visitas_generator.py`: cuatro categorías
# MAGIC cerca de cumplir y **Culinarios rezagada**, que es la que abre la conversación sobre
# MAGIC la acción del agente.

# COMMAND ----------

# (categoría, meta disponibilidad %, meta ejecución perfecta %, meta share of shelf cliente %)
METAS = [
    ("Bebidas Calientes",     95.0, 82.0, 34.0),
    ("Lácteos",               95.0, 82.0, 38.0),
    ("Culinarios",            95.0, 82.0, 30.0),
    ("Confitería y Snacks",   93.0, 78.0, 26.0),
    ("Bebidas No Alcohólicas", 96.0, 84.0, 18.0),
]

metas_schema = StructType([
    StructField("categoria",               StringType(), False),
    StructField("meta_disponibilidad_pct", DecimalType(5, 2), False),
    StructField("meta_ejecucion_pct",      DecimalType(5, 2), False),
    StructField("meta_sos_pct",            DecimalType(5, 2), False),
])

df_metas = spark.createDataFrame(
    [Row(categoria=c, meta_disponibilidad_pct=Decimal(str(d)),
         meta_ejecucion_pct=Decimal(str(e)), meta_sos_pct=Decimal(str(s)))
     for c, d, e, s in METAS],
    schema=metas_schema,
)
df_metas.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.metas_categoria")
print(f"metas_categoria: {df_metas.count()} categorías")

# COMMAND ----------

# MAGIC %md ## 6 · Verificación

# COMMAND ----------

for t in ("paises", "fabricantes", "productos", "tiendas", "metas_categoria"):
    n = spark.table(f"{FQ}.{t}").count()
    print(f"  {t:<20} {n:>5} filas")

display(
    spark.sql(f"""
        SELECT categoria, COUNT(*) AS skus,
               SUM(CASE WHEN es_cliente THEN 1 ELSE 0 END) AS skus_cliente
        FROM {FQ}.productos
        GROUP BY categoria ORDER BY categoria
    """)
)
