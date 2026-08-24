#!/usr/bin/env bash
# Prepara Lakebase (Postgres) para el copiloto de campo: aplica el esquema, siembra
# los perfiles de PDV desde Unity Catalog y le otorga privilegios al service
# principal del app.
#
#   ./scripts/habilitar_lakebase.sh \
#       --instancia projects/<proyecto>/branches/<rama>/endpoints/<endpoint> \
#       [--host <host>] [--db dncentro] [--psql /ruta/a/psql]
#
# Es el segundo de dos pasos. El primero es adjuntarle al app el recurso
# `database`, que es lo que hace que Databricks le cree al service principal su rol
# de Postgres. Ver docs/LAKEBASE.md — ahí está el orden completo y por qué importa.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_comun.sh"

INSTANCIA=""
HOST=""
DB="dncentro"
PUERTO="5432"
PSQL="${PSQL_BIN:-/opt/homebrew/opt/postgresql@16/bin/psql}"

ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --instancia) INSTANCIA="$2"; shift 2 ;;
        --host)      HOST="$2"; shift 2 ;;
        --db)        DB="$2"; shift 2 ;;
        --puerto)    PUERTO="$2"; shift 2 ;;
        --psql)      PSQL="$2"; shift 2 ;;
        *)           ARGS+=("$1"); shift ;;
    esac
done
parsear_flags "${ARGS[@]:-}"
cargar_config

echo "════════════════════════════════════════════════════════════════"
echo "  Lakebase — copiloto de campo"
echo "════════════════════════════════════════════════════════════════"

if [ -z "$INSTANCIA" ]; then
    echo "❌ Falta --instancia."
    echo "   Formato: projects/<proyecto>/branches/<rama>/endpoints/<endpoint>"
    echo "   Listalas con:  databricks postgres list-projects -o json"
    exit 1
fi
[ -x "$PSQL" ] || {
    echo "❌ No encontré psql en '$PSQL'."
    echo "   Instalalo (brew install postgresql@16) o pasá --psql <ruta>."
    exit 1
}

EMAIL="$(db current-user me -o json | python3 -c '
import json,sys; print(json.load(sys.stdin)["userName"])')"

# El host se puede deducir de la rama: es el endpoint de esa misma rama.
RAMA="$(echo "$INSTANCIA" | sed -E 's#/endpoints/.*##')"
if [ -z "$HOST" ]; then
    HOST="$(db postgres list-endpoints "$RAMA" -o json | python3 -c '
import json,sys; print(json.load(sys.stdin)[0]["status"]["hosts"]["host"])')"
fi
echo "  host $HOST · db $DB · usuario $EMAIL"

TOKEN="$(db postgres generate-database-credential "$INSTANCIA" -o json | python3 -c '
import json,sys; print(json.load(sys.stdin)["token"])')"
CONN="host=$HOST port=$PUERTO dbname=$DB user=$EMAIL sslmode=require"

echo
echo "[1/3] Aplicando src/esquema/lakebase_schema.sql..."
PGPASSWORD="$TOKEN" "$PSQL" "$CONN" -q -v ON_ERROR_STOP=1 \
  -f "$REPO_ROOT/src/esquema/lakebase_schema.sql"

echo "[2/3] Sembrando perfiles de PDV desde ${FQ_SCHEMA}..."
SEMILLA="$(mktemp)"; trap 'rm -f "$SEMILLA"' EXIT
PROFILE="${PROFILE:-DEFAULT}" WAREHOUSE_ID="$WAREHOUSE_ID" CATALOG="$CATALOG" \
  SCHEMA="$SCHEMA" FQ_SCHEMA="$FQ_SCHEMA" \
  python3 "$REPO_ROOT/scripts/sembrar_lakebase.py" > "$SEMILLA"
PGPASSWORD="$TOKEN" "$PSQL" "$CONN" -q -v ON_ERROR_STOP=1 -f "$SEMILLA"
FILAS="$(PGPASSWORD="$TOKEN" "$PSQL" "$CONN" -t -A -c 'SELECT COUNT(*) FROM campo.pdv_perfiles')"

echo "[3/3] Privilegios para el service principal del app..."
# Adjuntar el recurso `database` le crea al SP su rol de Postgres, pero el rol nace
# sin privilegios: las tablas las creó tu usuario y son tuyas. Sin estos grants el
# app conecta bien y falla en el primer SELECT. El nombre del rol es el application
# id del service principal, tal cual.
SP="$(db apps get "$APP_NAME" -o json 2>/dev/null | python3 -c '
import json,sys
try: print(json.load(sys.stdin).get("service_principal_client_id") or "")
except Exception: print("")
')"

if [ -z "$SP" ]; then
    echo "  ⚠ no encontré el app '$APP_NAME'. Instalá primero y repetí este paso."
else
    PGPASSWORD="$TOKEN" "$PSQL" "$CONN" -q -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$SP') THEN
    RAISE NOTICE 'el rol $SP todavía no existe — adjuntale el recurso database al app (ver docs/LAKEBASE.md) y volvé a correr esto';
    RETURN;
  END IF;

  EXECUTE format('GRANT USAGE ON SCHEMA campo, public TO %I', '$SP');
  EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA campo, public TO %I', '$SP');
  EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA campo, public TO %I', '$SP');
  -- El TRUNCATE del botón de limpieza necesita permiso propio: no viene con DELETE.
  EXECUTE format('GRANT TRUNCATE ON campo.sugerencias_log, public.genie_interactions TO %I', '$SP');
  -- Y que lo que se cree después herede los mismos privilegios.
  EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA campo, public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', '$SP');
  EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA campo, public GRANT USAGE, SELECT ON SEQUENCES TO %I', '$SP');
END
\$\$;
SQL
    echo "  privilegios otorgados a $SP"
fi

echo
echo "✅ Lakebase listo: $FILAS perfiles de PDV servibles por clave."
echo "   Si la pestaña Campo sigue diciendo 'no configurado', falta desplegar el app"
echo "   con lakebase_host — ver docs/LAKEBASE.md."
