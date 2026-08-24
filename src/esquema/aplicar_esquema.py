# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Aplicar el modelo de datos
# MAGIC
# MAGIC Lee `uc_schema.sql` y ejecuta su DDL contra el esquema de la instalación.
# MAGIC Es la primera tarea del job `instalar`, antes de cualquier semilla.
# MAGIC
# MAGIC El DDL vive en un `.sql` y no embebido acá a propósito: es el contrato del
# MAGIC modelo de datos y hay que poder leerlo, revisarlo en un pull request y
# MAGIC ejecutarlo a mano en un editor SQL sin arrastrar un notebook detrás.
# MAGIC
# MAGIC Es idempotente (`CREATE ... IF NOT EXISTS`), así que volver a correrlo sobre
# MAGIC una instalación viva no borra ni reescribe nada.

# COMMAND ----------

import os

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "ditcher_neira")
# El bundle pasa acá `${workspace.file_path}/src/esquema/uc_schema.sql`. Se deja
# vacío por defecto para poder correr el notebook a mano: en ese caso se resuelve
# contra la ruta del propio notebook.
dbutils.widgets.text("ddl_path", "")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
DDL_PATH = dbutils.widgets.get("ddl_path").strip()

# COMMAND ----------


def resolver_ddl(ruta: str) -> str:
    """Ruta absoluta al uc_schema.sql, venga del bundle o de una corrida manual.

    Cuando el job la inyecta llega absoluta y no hay nada que adivinar. Si el
    notebook se corre a mano, se busca al lado del propio notebook — que es donde
    el bundle deja el `.sql` al sincronizar `src/esquema/` completo.
    """
    if ruta:
        return ruta if ruta.startswith("/Workspace") else f"/Workspace{ruta}"
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    aqui = ctx.notebookPath().get()
    return f"/Workspace{os.path.dirname(aqui)}/uc_schema.sql"


ddl_file = resolver_ddl(DDL_PATH)
print(f"catálogo.esquema : {CATALOG}.{SCHEMA}")
print(f"DDL              : {ddl_file}")

with open(ddl_file, "r", encoding="utf-8") as fh:
    ddl_bruto = fh.read()

# COMMAND ----------


def sentencias(texto: str, catalog: str, schema: str):
    """Parte el archivo en sentencias ejecutables.

    Los comentarios se quitan ANTES de partir por `;`. Al revés, un punto y coma
    dentro de un comentario corta la sentencia por la mitad y el pedazo suelto
    falla. `USE CATALOG` se descarta: cada nombre se califica completo, que es lo
    que hace que el mismo DDL sirva en cualquier catálogo.
    """
    cuerpo = "\n".join(
        linea for linea in texto.splitlines() if not linea.strip().startswith("--")
    )
    cuerpo = cuerpo.replace("__CATALOG__", catalog).replace("__SCHEMA__", schema)
    for bruto in cuerpo.split(";"):
        s = bruto.strip()
        if not s or s.upper().startswith("USE CATALOG"):
            continue
        yield s.replace(
            f"CREATE TABLE IF NOT EXISTS {schema}.",
            f"CREATE TABLE IF NOT EXISTS {catalog}.{schema}.",
        )


# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")
print(f"esquema listo: {CATALOG}.{SCHEMA}")

fallidas = []
for i, stmt in enumerate(sentencias(ddl_bruto, CATALOG, SCHEMA), start=1):
    etiqueta = " ".join(stmt.split())[:78]
    try:
        spark.sql(stmt)
        print(f"  {i:02d} ok       {etiqueta}")
    except Exception as exc:  # noqa: BLE001 — se reportan todas juntas al final
        fallidas.append((etiqueta, str(exc)))
        print(f"  {i:02d} FALLÓ    {etiqueta}")

# COMMAND ----------

if fallidas:
    detalle = "\n".join(f"  · {e}\n      {m[:300]}" for e, m in fallidas)
    raise RuntimeError(f"{len(fallidas)} sentencia(s) del DDL fallaron:\n{detalle}")

tablas = spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`").count()
print(f"\n✅ modelo de datos aplicado — {tablas} tablas en {CATALOG}.{SCHEMA}")
