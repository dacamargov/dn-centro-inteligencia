# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase · evidencia de serving (lectura caliente por clave)
# MAGIC
# MAGIC Mide el camino caliente real del copiloto de campo: una lectura por clave
# MAGIC primaria sobre `campo.pdv_perfiles` en Lakebase (Postgres gestionado). Reporta
# MAGIC conteo de perfiles, latencia p50/p95 de la lectura por clave, inventario de
# MAGIC tablas y privilegios otorgados al service principal del app. Exporta todo como
# MAGIC JSON por `dbutils.notebook.exit` para que quede como evidencia de texto.

# COMMAND ----------

# MAGIC %pip install "psycopg[binary]" --quiet
# MAGIC %restart_python

# COMMAND ----------

import json
import time
import uuid

import psycopg
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("lakebase_instance", "dn-centro-lakebase")
dbutils.widgets.text("lakebase_db", "databricks_postgres")
dbutils.widgets.text("app_name", "dn-centro-inteligencia")
INSTANCIA = dbutils.widgets.get("lakebase_instance").strip()
DB = dbutils.widgets.get("lakebase_db").strip() or "databricks_postgres"
APP_NAME = dbutils.widgets.get("app_name").strip()

w = WorkspaceClient()
inst = w.api_client.do("GET", f"/api/2.0/database/instances/{INSTANCIA}")
HOST = inst.get("read_write_dns")
USUARIO = w.current_user.me().user_name
cred = w.api_client.do("POST", "/api/2.0/database/credentials",
                       body={"instance_names": [INSTANCIA], "request_id": str(uuid.uuid4())})
TOKEN = cred["token"]


def conectar():
    return psycopg.connect(host=HOST, port=5432, dbname=DB, user=USUARIO,
                           password=TOKEN, sslmode="require", connect_timeout=60)


ev = {"instancia": INSTANCIA, "host": HOST, "base": DB, "estado": inst.get("state")}

with conectar() as conn:
    with conn.cursor() as cur:
        # inventario de tablas
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('campo','public') AND table_type='BASE TABLE'
            ORDER BY 1,2
        """)
        ev["tablas"] = [f"{s}.{t}" for s, t in cur.fetchall()]

        # conteo de perfiles servibles
        cur.execute("SELECT COUNT(*) FROM campo.pdv_perfiles")
        ev["perfiles"] = cur.fetchone()[0]

        # una clave de muestra
        cur.execute("SELECT store_id FROM campo.pdv_perfiles ORDER BY store_id LIMIT 1")
        clave = cur.fetchone()[0]
        ev["clave_muestra"] = clave

        # fila de ejemplo servida (el payload que consume el copiloto)
        cur.execute("""
            SELECT store_id, nombre, cadena, pais, disponibilidad_hist,
                   riesgo_quiebre, categorias_prioritarias
            FROM campo.pdv_perfiles WHERE store_id = %s
        """, (clave,))
        cols = [d.name for d in cur.description]
        ev["fila_ejemplo"] = dict(zip(cols, cur.fetchone()))

        # --- latencia de lectura por clave (camino caliente) ---
        tiempos = []
        for _ in range(50):
            t0 = time.perf_counter()
            cur.execute("SELECT * FROM campo.pdv_perfiles WHERE store_id = %s", (clave,))
            cur.fetchone()
            tiempos.append((time.perf_counter() - t0) * 1000.0)
        tiempos.sort()
        ev["latencia_ms"] = {
            "n": len(tiempos),
            "p50": round(tiempos[len(tiempos) // 2], 2),
            "p95": round(tiempos[int(len(tiempos) * 0.95)], 2),
            "min": round(tiempos[0], 2),
            "max": round(tiempos[-1], 2),
        }

        # privilegios del service principal del app
        sp = ""
        try:
            app = w.api_client.do("GET", f"/api/2.0/apps/{APP_NAME}")
            sp = app.get("service_principal_client_id") or ""
        except Exception:
            pass
        ev["service_principal"] = sp
        if sp:
            cur.execute("""
                SELECT table_schema, privilege_type
                FROM information_schema.table_privileges
                WHERE grantee = %s AND table_schema IN ('campo','public')
                ORDER BY 1,2
            """, (sp,))
            ev["grants_sp"] = sorted({f"{s}:{p}" for s, p in cur.fetchall()})

# convierte tipos no serializables
def _ser(o):
    try:
        json.dumps(o); return o
    except TypeError:
        return str(o)

ev["fila_ejemplo"] = {k: _ser(v) for k, v in ev["fila_ejemplo"].items()}
salida = json.dumps(ev, ensure_ascii=False, default=str)
print(salida)
dbutils.notebook.exit(salida)
