# Databricks notebook source
# MAGIC %md
# MAGIC # Lakeflow · 00 — Aterrizaje de dato CRUDO en un Volume de Unity Catalog
# MAGIC
# MAGIC Este es el **origen crudo** del journey de datos. Simula la descarga de
# MAGIC StoreConnect AI: el reconocimiento de imagen del anaquel escupe un archivo
# MAGIC JSON por lote de auditoría —tal como llegaría de un proveedor de captura en
# MAGIC campo— y lo deja en un **Volume** de Unity Catalog (`landing/auditorias/`).
# MAGIC
# MAGIC El JSON crudo trae sólo lo que el dispositivo observa: tienda, SKU, caras,
# MAGIC precio local, flags de stock/promo/planograma y la confianza del modelo de
# MAGIC visión. **No** trae nada derivado (ni el precio normalizado a USD, ni el
# MAGIC share-of-shelf, ni las dimensiones de tienda/producto): eso lo calcula el
# MAGIC pipeline de Lakeflow aguas abajo, uniendo contra los maestros gobernados.
# MAGIC
# MAGIC Corre como una tarea previa al pipeline declarativo (`pipeline_auditorias.py`),
# MAGIC que ingiere estos archivos con Auto Loader (bronze → silver → gold).

# COMMAND ----------

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

try:
    dbutils.widgets.text("catalog", "main")
    dbutils.widgets.text("schema", "ditcher_neira")
    dbutils.widgets.text("n_archivos", "6")        # lotes de auditoría a aterrizar
    dbutils.widgets.text("por_archivo", "450")      # lecturas por lote
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
    N_ARCHIVOS = int(dbutils.widgets.get("n_archivos") or "6")
    POR_ARCHIVO = int(dbutils.widgets.get("por_archivo") or "450")
except NameError:
    CATALOG, SCHEMA, N_ARCHIVOS, POR_ARCHIVO = "main", "ditcher_neira", 6, 450

FQ = f"{CATALOG}.{SCHEMA}"
VOLUME = "landing"
LANDING_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/auditorias"

print(f"origen crudo → {LANDING_DIR}")

# COMMAND ----------

# El Volume es el buzón de aterrizaje gobernado por Unity Catalog. Idempotente.
spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ}.{VOLUME} "
          f"COMMENT 'Buzón de aterrizaje del dato crudo de auditoría (StoreConnect AI)'")
dbutils.fs.mkdirs(LANDING_DIR)

# COMMAND ----------

# Los maestros gobernados dan el universo real: qué tiendas existen y qué SKUs
# audita cada una. El crudo referencia por id; el pipeline los une aguas abajo.
tiendas = [r.asDict() for r in spark.sql(
    f"SELECT store_id, canal, country_code FROM {FQ}.tiendas"
).collect()]
productos = [r.asDict() for r in spark.sql(
    f"SELECT sku, categoria FROM {FQ}.productos"
).collect()]

por_categoria = {}
for p in productos:
    por_categoria.setdefault(p["categoria"], []).append(p["sku"])

MONEDAS = {"GT": "GTQ", "PA": "USD", "CR": "CRC", "CO": "COP", "PE": "PEN",
           "EC": "USD", "DO": "DOP", "SV": "USD", "HN": "HNL", "NI": "NIO"}

AUDITORES = [f"AUD-{i:03d}" for i in range(1, 61)]

print(f"{len(tiendas)} tiendas · {len(productos)} SKUs · {len(por_categoria)} categorías")

# COMMAND ----------

def una_lectura(ahora: datetime) -> dict:
    """Una observación cruda de anaquel, tal cual la emite el dispositivo."""
    tienda = random.choice(tiendas)
    categoria = random.choice(list(por_categoria.keys()))
    sku = random.choice(por_categoria[categoria])
    en_stock = random.random() < 0.86
    facings = max(0, int(round(random.gauss(3.2, 1.1)))) if en_stock else 0
    moneda = MONEDAS.get(tienda["country_code"], "USD")
    # precio local crudo (sin normalizar); nulo si está agotado
    precio_local = round(random.uniform(0.8, 9.5) * (18 if moneda != "USD" else 1), 2) \
        if en_stock else None
    return {
        "visita_id": f"V-{uuid.uuid4().hex[:16]}",
        "store_id": tienda["store_id"],
        "sku": sku,
        # El crudo trae el timestamp como texto ISO, como cualquier payload de API.
        "visit_ts": (ahora - timedelta(seconds=random.randint(0, 540))).isoformat(),
        "auditor_id": random.choice(AUDITORES),
        "facings": facings,
        "precio_local": precio_local,
        "moneda": moneda,
        "en_stock": en_stock,
        "en_promo": bool(en_stock and random.random() < 0.18),
        "planograma_ok": bool(en_stock and random.random() < 0.82),
        "confianza_ir": round(random.uniform(0.78, 0.995), 3),
        # Metadato del dispositivo de captura; el pipeline lo conserva en bronze.
        "dispositivo": random.choice(["SCAI-mobile-v4", "SCAI-mobile-v5", "SCAI-kiosk-v2"]),
    }

# COMMAND ----------

ahora = datetime.now(timezone.utc)
escritos = 0
for i in range(N_ARCHIVOS):
    lote = [una_lectura(ahora) for _ in range(POR_ARCHIVO)]
    # NDJSON (un objeto por línea): el formato que Auto Loader ingiere directo.
    cuerpo = "\n".join(json.dumps(r) for r in lote)
    nombre = f"auditoria_{ahora.strftime('%Y%m%dT%H%M%S')}_{i:03d}_{uuid.uuid4().hex[:8]}.json"
    with open(f"{LANDING_DIR}/{nombre}", "w", encoding="utf-8") as fh:
        fh.write(cuerpo)
    escritos += len(lote)
    print(f"  ✍ {nombre} · {len(lote)} lecturas")

print(f"\n✅ {escritos} lecturas crudas aterrizadas en {N_ARCHIVOS} archivos")
print(f"   {LANDING_DIR}")

# COMMAND ----------

# Prueba de que el buzón quedó poblado (evidencia de ejecución).
archivos = dbutils.fs.ls(LANDING_DIR)
print(f"archivos en el buzón: {len(archivos)}")
for f in archivos[-5:]:
    print(f"  {f.name}  ({f.size} bytes)")
