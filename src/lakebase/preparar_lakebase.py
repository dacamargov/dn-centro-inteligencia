# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase · preparar el camino caliente
# MAGIC
# MAGIC Deja Postgres listo para el copiloto de campo en tres pasos: aplica el
# MAGIC esquema, siembra los perfiles de PDV desde Unity Catalog y le otorga
# MAGIC privilegios al service principal del app.
# MAGIC
# MAGIC Corre **dentro** de Databricks y no en la máquina de quien instala. Esa es la
# MAGIC única razón por la que existe como notebook: la versión anterior era un script
# MAGIC de shell que canalizaba SQL a `psql`, y eso obligaba al cliente a tener
# MAGIC PostgreSQL instalado localmente para poder instalar la demo. Acá el único
# MAGIC requisito es el CLI de Databricks.
# MAGIC
# MAGIC Es idempotente: el esquema usa `IF NOT EXISTS`, la semilla hace UPSERT y los
# MAGIC grants se pueden repetir sin efecto. Volver a correrlo sobre una instancia
# MAGIC viva refresca los perfiles y no pierde el log de sugerencias.

# COMMAND ----------

# MAGIC %pip install "psycopg[binary]" --quiet
# MAGIC %restart_python

# COMMAND ----------

import os

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "ditcher_neira")
dbutils.widgets.text("lakebase_instance", "")
dbutils.widgets.text("lakebase_db", "databricks_postgres")
dbutils.widgets.text("app_name", "")
# El bundle pasa la ruta absoluta al .sql; vacío = al lado del notebook.
dbutils.widgets.text("ddl_path", "")

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
INSTANCIA = dbutils.widgets.get("lakebase_instance").strip()
DB = dbutils.widgets.get("lakebase_db").strip() or "databricks_postgres"
APP_NAME = dbutils.widgets.get("app_name").strip()
DDL_PATH = dbutils.widgets.get("ddl_path").strip()

FQ = f"{CATALOG}.{SCHEMA}"

if not INSTANCIA:
    raise ValueError("falta el parámetro lakebase_instance")

print(f"instancia : {INSTANCIA}")
print(f"base      : {DB}")
print(f"origen    : {FQ}")

# COMMAND ----------

import uuid

import psycopg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Se llama a la API REST en vez de a `w.database`, que es la forma cómoda: el
# databricks-sdk que trae el entorno serverless es más viejo que esa parte de la
# API y el atributo no existe. Las rutas son estables y así el notebook no
# depende de qué versión del SDK haya en el entorno.
instancia = w.api_client.do("GET", f"/api/2.0/database/instances/{INSTANCIA}")
HOST = instancia.get("read_write_dns")
USUARIO = w.current_user.me().user_name

print(f"host      : {HOST}")
print(f"usuario   : {USUARIO}")
print(f"estado    : {instancia.get('state')}")

if not HOST:
    raise RuntimeError(
        f"la instancia '{INSTANCIA}' no tiene host todavía "
        f"(estado {instancia.get('state')}) — esperá a que quede AVAILABLE"
    )

# El token de Lakebase es de vida corta y se pide en el momento. No se imprime.
credencial = w.api_client.do(
    "POST", "/api/2.0/database/credentials",
    body={"instance_names": [INSTANCIA], "request_id": str(uuid.uuid4())},
)
TOKEN = credencial.get("token")
if not TOKEN:
    raise RuntimeError(f"no pude emitir credencial para '{INSTANCIA}': {credencial}")


def conectar():
    return psycopg.connect(
        host=HOST, port=5432, dbname=DB, user=USUARIO,
        password=TOKEN, sslmode="require", connect_timeout=60,
    )


# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Esquema
# MAGIC
# MAGIC El DDL vive en `src/esquema/lakebase_schema.sql` y no embebido acá para que se
# MAGIC pueda leer y revisar como cualquier otro contrato del modelo de datos.

# COMMAND ----------


def resolver_ddl(ruta: str) -> str:
    if ruta:
        return ruta if ruta.startswith("/Workspace") else f"/Workspace{ruta}"
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    aqui = os.path.dirname(ctx.notebookPath().get())
    # El notebook vive en src/lakebase/ y el .sql en src/esquema/.
    return f"/Workspace{os.path.dirname(aqui)}/esquema/lakebase_schema.sql"


ddl_file = resolver_ddl(DDL_PATH)
print(f"DDL: {ddl_file}")

with open(ddl_file, "r", encoding="utf-8") as fh:
    ddl = fh.read()

with conectar() as conn:
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('campo', 'public')
              AND table_type = 'BASE TABLE'
            ORDER BY 1, 2
        """)
        for esq, tabla in cur.fetchall():
            print(f"  {esq}.{tabla}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Semilla de perfiles de PDV — desde la capa GOLD
# MAGIC
# MAGIC El perfil servible **no** se recalcula ad-hoc: se deriva de la capa gobernada
# MAGIC `pdv_perfil_gold`, que a su vez sale de la capa gold de Lakeflow
# MAGIC (`ejecucion_pdv_gold`) + la salida del modelo (`predicciones_riesgo`) + los
# MAGIC maestros de UC. Así los features de serving y de entrenamiento salen del mismo
# MAGIC lugar y **no pueden desalinearse**.
# MAGIC
# MAGIC El handoff gold → Lakebase se hace aquí con un UPSERT gobernado. En un
# MAGIC workspace con permiso de `CREATE CATALOG` sobre el metastore, el mismo
# MAGIC `pdv_perfil_gold` (ya tiene PK y Change Data Feed) se registra como **synced
# MAGIC table continua** con un solo comando —ver `docs/LAKEBASE.md`.

# COMMAND ----------

# Construye la capa gold de serving desde el lakehouse gobernado. El SQL vive en
# src/datos/05_perfil_gold.sql (único origen, revisable) y se lee de ahí: no se
# duplica la lógica en el notebook.
def _resolver_sql(rel: str) -> str:
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    aqui = os.path.dirname(ctx.notebookPath().get())
    # El notebook vive en src/lakebase/; el .sql en src/datos/.
    return f"/Workspace{os.path.dirname(aqui)}/{rel}"


perfil_file = _resolver_sql("datos/05_perfil_gold.sql")
print(f"GOLD serving SQL: {perfil_file}")
with open(perfil_file, "r", encoding="utf-8") as fh:
    perfil_sql = fh.read().replace("{cat}", CATALOG).replace("{sch}", SCHEMA)

_lineas = [l for l in perfil_sql.splitlines() if not l.strip().startswith("--")]
for _stmt in [s.strip() for s in "\n".join(_lineas).split(";") if s.strip()]:
    spark.sql(_stmt)
print(f"✅ {FQ}.pdv_perfil_gold construida desde gold + modelo (una fila por PDV)")

# El serving lee EXACTAMENTE esa tabla gold — handoff gold -> Lakebase, sin
# recálculo paralelo que pueda derivar frente a los features del modelo.
PERFILES_SQL = f"""
  SELECT store_id, nombre, canal, cadena, formato, ciudad, country_code, pais,
         mercaderista, visitas_mes_meta, categorias_prioritarias, skus_foco,
         disponibilidad_hist, ejecucion_hist, sos_hist, riesgo_quiebre,
         ticket_categoria_usd, ultima_visita
  FROM {FQ}.pdv_perfil_gold
  ORDER BY store_id
"""

filas = [tuple(r) for r in spark.sql(PERFILES_SQL).collect()]
print(f"{len(filas)} PDV leídos de Unity Catalog")
if not filas:
    raise RuntimeError(
        f"no hay puntos de venta en {FQ}.tiendas — corré primero el job de instalación"
    )

# COMMAND ----------

# Los valores van como parámetros y no interpolados en el SQL: psycopg mapea las
# listas de Python a arrays de Postgres y se evita todo el trabajo de escapado.
UPSERT = """
INSERT INTO campo.pdv_perfiles (
    store_id, nombre, canal, cadena, formato, ciudad, country_code, pais,
    mercaderista, visitas_mes_meta, categorias_prioritarias, skus_foco,
    disponibilidad_hist, ejecucion_hist, sos_hist, riesgo_quiebre,
    ticket_categoria_usd, ultima_visita, actualizado_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
)
ON CONFLICT (store_id) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    canal = EXCLUDED.canal,
    cadena = EXCLUDED.cadena,
    formato = EXCLUDED.formato,
    ciudad = EXCLUDED.ciudad,
    country_code = EXCLUDED.country_code,
    pais = EXCLUDED.pais,
    mercaderista = EXCLUDED.mercaderista,
    visitas_mes_meta = EXCLUDED.visitas_mes_meta,
    categorias_prioritarias = EXCLUDED.categorias_prioritarias,
    skus_foco = EXCLUDED.skus_foco,
    disponibilidad_hist = EXCLUDED.disponibilidad_hist,
    ejecucion_hist = EXCLUDED.ejecucion_hist,
    sos_hist = EXCLUDED.sos_hist,
    riesgo_quiebre = EXCLUDED.riesgo_quiebre,
    ticket_categoria_usd = EXCLUDED.ticket_categoria_usd,
    ultima_visita = EXCLUDED.ultima_visita,
    actualizado_at = NOW()
"""

with conectar() as conn:
    with conn.cursor() as cur:
        cur.executemany(UPSERT, filas)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM campo.pdv_perfiles")
        total = cur.fetchone()[0]

print(f"✅ {total} perfiles de PDV servibles por clave")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Privilegios del service principal
# MAGIC
# MAGIC Adjuntarle el recurso `database` al app le crea al service principal su rol de
# MAGIC Postgres, pero el rol nace sin privilegios: las tablas las creó el usuario que
# MAGIC instaló y son suyas. Sin estos grants el app conecta bien y falla en el primer
# MAGIC `SELECT`, que es un síntoma bastante desorientador.
# MAGIC
# MAGIC El nombre del rol es el application id del service principal, tal cual.

# COMMAND ----------

sp = ""
if APP_NAME:
    try:
        app = w.api_client.do("GET", f"/api/2.0/apps/{APP_NAME}")
        sp = app.get("service_principal_client_id") or ""
    except Exception as exc:  # noqa: BLE001
        print(f"  no pude leer el app '{APP_NAME}': {exc}")

if not sp:
    print("⚠ sin service principal todavía. El app se despliega después de este paso;")
    print("  volvé a correr esta tarea cuando exista y el copiloto va a poder leer.")
else:
    # GRANT no acepta el nombre del rol como parámetro, así que va como
    # identificador. `sql.Identifier` lo entrecomilla del lado del cliente, que es
    # lo que hace falta: el application id trae guiones y sin comillas Postgres lo
    # parte en pedazos.
    from psycopg import sql

    GRANTS = [
        "GRANT USAGE ON SCHEMA campo, public TO {rol}",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA campo, public TO {rol}",
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA campo, public TO {rol}",
        # El TRUNCATE del botón de limpieza necesita permiso propio: no viene con DELETE.
        "GRANT TRUNCATE ON campo.sugerencias_log, public.genie_interactions TO {rol}",
        # Y que lo que se cree después herede los mismos privilegios.
        "ALTER DEFAULT PRIVILEGES IN SCHEMA campo, public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {rol}",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA campo, public "
        "GRANT USAGE, SELECT ON SEQUENCES TO {rol}",
    ]

    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (sp,))
            existe = cur.fetchone() is not None

        if not existe:
            print(f"⚠ el rol {sp} todavía no existe en Postgres.")
            print("  Lo crea Databricks al adjuntarle el recurso `database` al app,")
            print("  así que hay que desplegar el app y repetir esta tarea.")
            otorgados = 0
        else:
            with conn.cursor() as cur:
                for plantilla in GRANTS:
                    cur.execute(
                        sql.SQL(plantilla).format(rol=sql.Identifier(sp))
                    )
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.table_privileges "
                    "WHERE grantee = %s AND table_schema = 'campo'", (sp,)
                )
                otorgados = cur.fetchone()[0]
            print(f"✅ privilegios otorgados a {sp} ({otorgados} sobre campo)")

# COMMAND ----------

print()
print("════════════════════════════════════════════════════════")
print(f"  Lakebase listo · {HOST}")
print(f"  base {DB} · {total} perfiles de PDV")
print("════════════════════════════════════════════════════════")
