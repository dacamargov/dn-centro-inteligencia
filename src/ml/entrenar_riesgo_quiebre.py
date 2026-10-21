# Databricks notebook source
# MAGIC %md
# MAGIC # ML · Modelo de riesgo de quiebre de stock
# MAGIC
# MAGIC **Problema de negocio:** anticipar dónde se va a quebrar el stock antes de que
# MAGIC el auditor lo encuentre. Hoy el quiebre se descubre en la visita; el modelo lo
# MAGIC predice por combinación tienda × categoría para que la red priorice la
# MAGIC reposición donde más duele.
# MAGIC
# MAGIC **Enfoque (sin fuga de etiqueta):** se agrega el histórico de `visitas` a nivel
# MAGIC tienda × categoría y se aprende la **tasa de quiebre** esperada a partir de
# MAGIC features de contexto que existen *antes* de la observación —categoría, canal,
# MAGIC cadena, país, mezcla de cliente/competencia, promo— nunca a partir de campos que
# MAGIC se derivan del propio `en_stock` (facings, planograma, ejecución).
# MAGIC
# MAGIC **Journey:** entrena con scikit-learn, registra en **MLflow** + **Unity Catalog
# MAGIC Model Registry**, y hace **inferencia batch** escribiendo `predicciones_riesgo`
# MAGIC en UC — la tabla que el resto de la demo (Genie, dashboard, agentes) puede
# MAGIC consumir para accionar. Todo queda gobernado en el mismo esquema.

# COMMAND ----------

# MAGIC %pip install --quiet scikit-learn mlflow pandas
# MAGIC %restart_python

# COMMAND ----------

try:
    dbutils.widgets.text("catalog", "main")
    dbutils.widgets.text("schema", "ditcher_neira")
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
except NameError:
    CATALOG, SCHEMA = "main", "ditcher_neira"

FQ = f"{CATALOG}.{SCHEMA}"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.modelo_riesgo_quiebre"
print(f"esquema: {FQ}")
print(f"modelo:  {MODEL_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Dataset de entrenamiento — agregado tienda × categoría
# MAGIC
# MAGIC Una fila por (tienda, categoría) con la tasa de quiebre histórica (la etiqueta)
# MAGIC y el contexto estructural. Se exige un mínimo de observaciones para que la tasa
# MAGIC no sea ruido de muestras chicas.

# COMMAND ----------

dataset = spark.sql(f"""
    SELECT
        v.store_id,
        v.categoria,
        v.canal,
        v.cadena,
        v.country_code,
        ROUND(AVG(CASE WHEN v.es_cliente THEN 1.0 ELSE 0.0 END), 3) AS share_cliente,
        ROUND(AVG(CASE WHEN v.en_promo THEN 1.0 ELSE 0.0 END), 3)   AS promo_rate,
        ROUND(AVG(v.confianza_ir), 3)                               AS confianza_prom,
        COUNT(*)                                                    AS observaciones,
        -- etiqueta: tasa de quiebre (fracción de lecturas sin stock)
        ROUND(AVG(CASE WHEN v.en_stock THEN 0.0 ELSE 1.0 END), 4)   AS tasa_quiebre
    FROM {FQ}.visitas v
    GROUP BY v.store_id, v.categoria, v.canal, v.cadena, v.country_code
    HAVING COUNT(*) >= 8
""").toPandas()

# Spark ROUND() devuelve Decimal; sklearn/MLflow necesitan float nativo.
for _c in ["share_cliente", "promo_rate", "confianza_prom", "tasa_quiebre"]:
    dataset[_c] = dataset[_c].astype(float)
dataset["observaciones"] = dataset["observaciones"].astype(int)

print(f"filas (tienda×categoría): {len(dataset)}")
print(dataset[["tasa_quiebre", "observaciones", "promo_rate", "share_cliente"]].describe().round(3).to_string())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Entrenamiento con MLflow autolog

# COMMAND ----------

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

mlflow.set_registry_uri("databricks-uc")

CAT_FEATURES = ["categoria", "canal", "cadena", "country_code"]
NUM_FEATURES = ["share_cliente", "promo_rate", "confianza_prom"]
FEATURES = CAT_FEATURES + NUM_FEATURES
TARGET = "tasa_quiebre"

X = dataset[FEATURES]
y = dataset[TARGET]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

pre = ColumnTransformer(
    transformers=[("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES)],
    remainder="passthrough",
)
modelo = Pipeline([
    ("pre", pre),
    ("gbr", GradientBoostingRegressor(n_estimators=250, max_depth=3,
                                      learning_rate=0.05, random_state=42)),
])

with mlflow.start_run(run_name="riesgo_quiebre_gbr") as run:
    modelo.fit(X_train, y_train)
    pred = modelo.predict(X_test)
    mae = mean_absolute_error(y_test, pred)
    r2 = r2_score(y_test, pred)
    # baseline: predecir siempre la media del train
    base_mae = mean_absolute_error(y_test, np.full_like(y_test, y_train.mean()))

    mlflow.log_params({
        "modelo": "GradientBoostingRegressor",
        "n_estimators": 250, "max_depth": 3, "learning_rate": 0.05,
        "n_filas_train": len(X_train), "n_filas_test": len(X_test),
        "features": ",".join(FEATURES),
    })
    mlflow.log_metrics({
        "mae": round(float(mae), 4),
        "r2": round(float(r2), 4),
        "baseline_mae": round(float(base_mae), 4),
        "mejora_vs_baseline_pct": round(float((base_mae - mae) / base_mae * 100), 1),
    })

    firma = mlflow.models.infer_signature(X_train, modelo.predict(X_train))
    mlflow.sklearn.log_model(
        modelo, artifact_path="model",
        signature=firma, input_example=X_train.head(3),
        registered_model_name=MODEL_NAME,
    )
    run_id = run.info.run_id

print(f"\nMLflow run: {run_id}")
print(f"  MAE            : {mae:.4f}")
print(f"  R²             : {r2:.4f}")
print(f"  baseline MAE   : {base_mae:.4f}")
print(f"  mejora vs base : {(base_mae - mae) / base_mae * 100:.1f}%")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Promover a alias @campeon en Unity Catalog

# COMMAND ----------

from mlflow.tracking import MlflowClient

client = MlflowClient(registry_uri="databricks-uc")
versiones = client.search_model_versions(f"name = '{MODEL_NAME}'")
ultima = max(int(v.version) for v in versiones)
client.set_registered_model_alias(MODEL_NAME, "campeon", ultima)
print(f"✅ {MODEL_NAME} v{ultima} → alias @campeon")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Inferencia batch — scoring de toda la red a `predicciones_riesgo`

# COMMAND ----------

scoring = dataset.copy()
scoring["riesgo_predicho"] = modelo.predict(scoring[FEATURES]).clip(0, 1).round(4)


def tier(r):
    return "ALTO" if r >= 0.18 else ("MEDIO" if r >= 0.10 else "BAJO")


scoring["tier_riesgo"] = scoring["riesgo_predicho"].apply(tier)
scoring["modelo_version"] = ultima
salida = scoring[[
    "store_id", "categoria", "canal", "cadena", "country_code",
    "observaciones", "tasa_quiebre", "riesgo_predicho", "tier_riesgo", "modelo_version",
]]

from pyspark.sql import functions as F

sdf = spark.createDataFrame(salida)
sdf = sdf.withColumn("scored_at", F.current_timestamp())
(sdf.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{FQ}.predicciones_riesgo"))

spark.sql(f"COMMENT ON TABLE {FQ}.predicciones_riesgo IS "
          f"'Riesgo de quiebre predicho por tienda×categoría (modelo UC {MODEL_NAME}). Inferencia batch.'")

print(f"✅ {salida.shape[0]} predicciones escritas en {FQ}.predicciones_riesgo")
print("\nDistribución por tier:")
print(salida["tier_riesgo"].value_counts().to_string())
print("\nTop 10 tiendas×categoría de mayor riesgo:")
print(salida.sort_values("riesgo_predicho", ascending=False)
      .head(10).to_string(index=False))
