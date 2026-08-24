# Variables y helpers compartidos por los scripts de operación.
# No es ejecutable por sí solo: se hace `source`.
#
# La única fuente de verdad es `databricks.yml`. Nadie acá guarda un id ni un
# nombre: se le pregunta al bundle con `bundle validate -o json`, que devuelve la
# configuración ya resuelta (variables, targets y nombres de recurso). Así no hay
# un segundo archivo de configuración que se pueda desincronizar del bundle.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TARGET="${TARGET:-demo}"
PROFILE="${PROFILE:-}"

# ---- Parseo de flags comunes -------------------------------------------------
# Cada script llama a `parsear_flags "$@"` y después usa "${RESTO[@]}" para lo suyo.
# El workspace se elige igual que en el instalador: por perfil, por --host, o por
# lo que ya tenga configurado el CLI. Ninguno está escrito en el repositorio.
RESTO=()
parsear_flags() {
    RESTO=()
    while [ $# -gt 0 ]; do
        case "$1" in
            -t|--target)  TARGET="$2"; shift 2 ;;
            -p|--profile) PROFILE="$2"; shift 2 ;;
            --host)       export DATABRICKS_HOST="$2"; shift 2 ;;
            *)            RESTO+=("$1"); shift ;;
        esac
    done
}

# ---- CLI de Databricks -------------------------------------------------------
db() {
    if [ -n "$PROFILE" ]; then
        databricks "$@" -p "$PROFILE"
    else
        databricks "$@"
    fi
}

perfil_args() {
    [ -n "$PROFILE" ] && printf '%s\n%s\n' "-p" "$PROFILE"
}

# ---- El workspace tiene que estar accesible ---------------------------------
# Sin esto los scripts siguen adelante con la configuración estática del bundle,
# no encuentran ningún job —porque no pueden listarlos— y terminan anunciando
# éxito sin haber hecho nada. Falla temprano y con un mensaje que dice qué hacer.
verificar_workspace() {
    local yo
    yo="$(db current-user me -o json 2>/dev/null | python3 -c '
import json, sys
try: print(json.load(sys.stdin)["userName"])
except Exception: print("")
' || true)"
    if [ -z "$yo" ]; then
        echo "❌ No pude conectarme a ningún workspace de Databricks."
        echo "   Autenticate:  databricks auth login${PROFILE:+ --profile $PROFILE}"
        echo "   O indicá uno: $(basename "$0") --host https://<tu-workspace>"
        return 1
    fi
    return 0
}

# ---- Lectura de la configuración resuelta del bundle ------------------------
_BUNDLE_JSON=""

cargar_bundle() {
    [ -n "$_BUNDLE_JSON" ] && return 0
    _BUNDLE_JSON="$(cd "$REPO_ROOT" && db bundle validate -t "$TARGET" -o json 2>/dev/null || true)"
    # `bundle validate` puede escribir JSON parcial aunque haya fallado, así que
    # no alcanza con ver si la salida está vacía: hay que confirmar que trae las
    # variables resueltas.
    if ! python3 -c '
import json, sys
d = json.loads(sys.stdin.read())
sys.exit(0 if (d.get("variables") or {}).get("schema") else 1)
' <<< "$_BUNDLE_JSON" 2>/dev/null; then
        echo "❌ No pude leer la configuración del bundle para el target '$TARGET'."
        echo "   Probá:  databricks bundle validate -t $TARGET"
        _BUNDLE_JSON=""
        return 1
    fi
    return 0
}

# var <nombre> → valor resuelto de una variable del bundle
var() {
    cargar_bundle || return 1
    CLAVE="$1" python3 -c '
import json, os, sys
d = json.loads(sys.stdin.read())
v = (d.get("variables") or {}).get(os.environ["CLAVE"]) or {}
val = v.get("value", v.get("default", ""))
print("" if val is None else val)
' <<< "$_BUNDLE_JSON"
}

# nombre_recurso <tipo> <clave> → el `name` con el que quedó en el workspace
nombre_recurso() {
    cargar_bundle || return 1
    TIPO="$1" CLAVE="$2" python3 -c '
import json, os, sys
d = json.loads(sys.stdin.read())
r = ((d.get("resources") or {}).get(os.environ["TIPO"]) or {}).get(os.environ["CLAVE"]) or {}
print(r.get("name", ""))
' <<< "$_BUNDLE_JSON"
}

cargar_config() {
    verificar_workspace || return 1
    cargar_bundle || return 1
    CATALOG="$(var catalog)"
    SCHEMA="$(var schema)"
    CLIENTE="$(var cliente)"
    JOB_PREFIX="$(var job_prefix)"
    APP_NAME="$(var app_name)"
    WAREHOUSE_ID="$(var warehouse_id)"
    FQ_SCHEMA="${CATALOG}.${SCHEMA}"

    # El warehouse lo elige `instalar.sh` en el momento, así que su default en el
    # bundle está vacío. En vez de guardarlo en un archivo local —que se
    # desincroniza y no viaja entre máquinas— se le pregunta al app instalado:
    # el recurso adjunto es la respuesta correcta por definición, porque es el
    # warehouse sobre el que el app tiene permiso.
    if [ -z "$WAREHOUSE_ID" ] && [ -n "$APP_NAME" ]; then
        WAREHOUSE_ID="$(db apps get "$APP_NAME" -o json 2>/dev/null | python3 -c '
import json, sys
try: recursos = json.load(sys.stdin).get("resources") or []
except Exception: recursos = []
for r in recursos:
    w = r.get("sql_warehouse") or {}
    if w.get("id"):
        print(w["id"]); break
' || true)"
    fi

    export CATALOG SCHEMA CLIENTE JOB_PREFIX APP_NAME WAREHOUSE_ID FQ_SCHEMA
}

# ---- Jobs de la demo --------------------------------------------------------
# Se localizan por nombre, nunca por id: el id cambia en cada instalación y el
# nombre lo fija el bundle. El job `instalar` queda afuera a propósito — no es
# parte del latido de la demo y no debe encenderse con ella.

jobs_por_patron() {
    local patron="$1" salida
    salida="$(db jobs list -o json 2>/dev/null || true)"
    PAT="$patron" python3 -c '
import json, os, sys
try:
    jobs = json.loads(sys.stdin.read())
except Exception:
    # Sin lista de jobs no hay nada que reportar. El script que llama distingue
    # "no hay jobs" de "no pude preguntar" por el estado del workspace, que ya
    # se verificó antes de llegar acá.
    sys.exit(0)
pat = os.environ["PAT"]
for j in jobs or []:
    nombre = (j.get("settings") or {}).get("name", "")
    if nombre.startswith(pat):
        print(j["job_id"], nombre, sep="\t")
' <<< "$salida"
}

jobs_generadores() { jobs_por_patron "$JOB_PREFIX datagen"; }
jobs_agentes()     { jobs_por_patron "$JOB_PREFIX agent"; }

pausar_job() {
    local jid="$1" estado="$2" payload
    payload=$(db jobs get "$jid" -o json | JID="$jid" ESTADO="$estado" python3 -c '
import json, os, sys
d = json.load(sys.stdin)
s = d["settings"]
s.setdefault("schedule", {})["pause_status"] = os.environ["ESTADO"]
print(json.dumps({"job_id": int(os.environ["JID"]), "new_settings": s}))
')
    db jobs reset "$jid" --json "$payload" >/dev/null 2>&1
}

correr_job() {
    db jobs run-now "$1" --no-wait -o json 2>/dev/null | python3 -c '
import json, sys
print(json.load(sys.stdin).get("run_id", "?"))
'
}

# ---- SQL contra el warehouse de la instalación ------------------------------
sql() {
    local stmt="$1"
    [ -n "${WAREHOUSE_ID:-}" ] || { echo "  (sin warehouse: no puedo correr SQL)"; return 1; }
    local payload
    payload=$(WID="$WAREHOUSE_ID" STMT="$stmt" python3 -c '
import json, os
print(json.dumps({"warehouse_id": os.environ["WID"], "statement": os.environ["STMT"],
                  "wait_timeout": "30s"}))
')
    db api post /api/2.0/sql/statements --json "$payload" 2>/dev/null
}

estado_sql() {
    python3 -c '
import json, sys
try: print(json.load(sys.stdin).get("status", {}).get("state", "?"))
except Exception: print("?")
'
}
