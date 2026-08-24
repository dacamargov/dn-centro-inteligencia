#!/usr/bin/env bash
# =============================================================================
# dichter & neira · Centro de Inteligencia — instalación completa
# =============================================================================
# Un comando deja el workspace listo: esquema, tablas, datos, jobs, dashboard y
# el app corriendo.
#
#   ./instalar.sh
#
# Opciones:
#   -p, --profile <perfil>   perfil del CLI (por defecto, el configurado)
#       --host <url>         workspace destino, si no se usa un perfil
#   -t, --target <target>    target del bundle: demo (default) | pruebas
#       --warehouse <id>     SQL Warehouse a usar (por defecto lo descubre)
#       --catalog <nombre>   catálogo de Unity Catalog (default: main)
#       --schema <nombre>    esquema (default: ditcher_neira)
#       --cliente <nombre>   fabricante del estudio (default: Nestlé)
#       --sin-dashboard      omite el dashboard AI/BI
#       --sin-genie          omite la sala de Genie (el app queda en modo demo)
#       --sin-datos          crea todo pero no siembra (útil para reinstalar)
#       --var clave=valor    cualquier otra variable del bundle (repetible);
#                            por ejemplo --var lakebase_capacity=CU_2.
#                            Ver databricks.yml.
#
# El workspace no está escrito en ninguna parte del repositorio: sale del perfil
# del CLI, de --host, o de DATABRICKS_HOST. Lo mismo el catálogo, el esquema y el
# warehouse. Este repositorio no conoce ningún workspace en particular.
#
# Casi todo lo hace `databricks bundle deploy`. Este script existe por las cosas
# que un bundle no puede resolver solo:
#   1. descubrir el warehouse, para no pedirle un id al que instala;
#   2. crear la instancia de Lakebase, porque el app la necesita adjunta como
#      recurso y un bundle no garantiza ese orden;
#   3. crear el dashboard AI/BI y la sala de Genie, cuyos ids el app recibe como
#      variables de entorno — y la sala, además, después de sembrar, porque Genie
#      valida las tablas al crearse;
#   4. otorgarle permisos al service principal del app, que no existe hasta que
#      el app existe — y sin esos permisos el tablero abre vacío.
#
# Lakebase forma parte de la instalación estándar. Es una instancia de Postgres
# gestionada y factura mientras exista, aunque nadie la consulte: `./desinstalar.sh`
# la borra. Para instalar sin ella hay que comentar el recurso `lakebase` en
# resources/04_app.yml. Ver docs/LAKEBASE.md.
# =============================================================================
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

TARGET="demo"
PROFILE=""
HOST=""
WAREHOUSE_ID=""
CATALOG=""
SCHEMA=""
CLIENTE=""
CON_DASHBOARD=1
CON_GENIE=1
CON_DATOS=1
EXTRA_VARS=()

while [ $# -gt 0 ]; do
    case "$1" in
        -p|--profile)     PROFILE="$2"; shift 2 ;;
        --host)           HOST="$2"; shift 2 ;;
        -t|--target)      TARGET="$2"; shift 2 ;;
        --warehouse)      WAREHOUSE_ID="$2"; shift 2 ;;
        --catalog)        CATALOG="$2"; shift 2 ;;
        --schema)         SCHEMA="$2"; shift 2 ;;
        --cliente)        CLIENTE="$2"; shift 2 ;;
        --sin-dashboard)  CON_DASHBOARD=0; shift ;;
        --sin-genie)      CON_GENIE=0; shift ;;
        --sin-datos)      CON_DATOS=0; shift ;;
        --var)            EXTRA_VARS+=(--var="$2"); shift 2 ;;
        --var=*)          EXTRA_VARS+=(--var="${1#--var=}"); shift ;;
        # La ayuda es el encabezado de este archivo, para no escribirla dos veces.
        # El sed va en dos pasos porque el `\?` de GNU no existe en el sed de macOS.
        -h|--help)        sed -n '2,42p' "$0" | sed -e 's/^# //' -e 's/^#//'; exit 0 ;;
        *) echo "opción desconocida: $1 (probá --help)"; exit 1 ;;
    esac
done

# El workspace se elige por perfil o por host. Con --host se exporta la variable
# que ya entiende el CLI, así que no hay que pasarla en cada llamada.
[ -n "$HOST" ] && export DATABRICKS_HOST="$HOST"

db() { if [ -n "$PROFILE" ]; then databricks "$@" -p "$PROFILE"; else databricks "$@"; fi; }

paso() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
aviso(){ printf '  \033[33m!\033[0m %s\n' "$1"; }
malo() { printf '  \033[31m✗\033[0m %s\n' "$1"; }

echo "════════════════════════════════════════════════════════════════"
echo "  dichter & neira · Centro de Inteligencia"
echo "  instalación — target '$TARGET'"
echo "════════════════════════════════════════════════════════════════"

# ---------------------------------------------------------------------------
paso "1/9 · Revisando prerrequisitos"
# ---------------------------------------------------------------------------
command -v databricks >/dev/null || {
    malo "No encontré el CLI de Databricks."
    echo "     Instalalo: https://docs.databricks.com/dev-tools/cli/install.html"
    exit 1
}
command -v python3 >/dev/null || { malo "No encontré python3."; exit 1; }

VERSION="$(databricks --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
ok "CLI de Databricks v${VERSION:-?}"
# El recurso `apps` del bundle y `schemas` con grants necesitan CLI moderno. Con
# una versión vieja el deploy falla con un error de campo desconocido, que no
# dice nada útil, así que conviene avisar acá.
MAYOR="${VERSION%%.*}"; RESTO="${VERSION#*.}"; MENOR="${RESTO%%.*}"
if [ "${MAYOR:-0}" -eq 0 ] && [ "${MENOR:-0}" -lt 240 ]; then
    aviso "Versión antigua: el recurso 'apps' del bundle puede no existir. Actualizá el CLI."
fi

YO="$(db current-user me -o json 2>/dev/null | python3 -c '
import json,sys
try: print(json.load(sys.stdin)["userName"])
except Exception: print("")
' || true)"
if [ -z "$YO" ]; then
    malo "El CLI no está autenticado contra ningún workspace."
    echo "     Corré:  databricks auth login${PROFILE:+ --profile $PROFILE}"
    echo "     O apuntá a uno:  ./instalar.sh --host https://<tu-workspace>"
    exit 1
fi
ok "autenticado como $YO"
if [ -n "$HOST" ]; then
    ok "workspace  $HOST"
elif [ -n "$PROFILE" ]; then
    ok "workspace  perfil $PROFILE"
else
    ok "workspace  perfil por defecto del CLI"
fi

# ---------------------------------------------------------------------------
paso "2/9 · Resolviendo el SQL Warehouse"
# ---------------------------------------------------------------------------
if [ -z "$WAREHOUSE_ID" ]; then
    # Se prefiere uno serverless y encendido: es el que responde sin esperar el
    # arranque en frío, que en una demo se nota.
    WAREHOUSE_ID="$(db warehouses list -o json 2>/dev/null | python3 -c '
import json, sys
try: ws = json.load(sys.stdin)
except Exception: ws = []
def puntaje(w):
    return (
        1 if w.get("enable_serverless_compute") else 0,
        1 if (w.get("state") or "") == "RUNNING" else 0,
        w.get("cluster_size") == "Small",
    )
ws = [w for w in ws if w.get("id")]
if ws:
    print(sorted(ws, key=puntaje, reverse=True)[0]["id"])
' || true)"
    if [ -z "$WAREHOUSE_ID" ]; then
        malo "No encontré ningún SQL Warehouse en el workspace."
        echo "     Creá uno (serverless, Small alcanza) y volvé a correr con --warehouse <id>."
        exit 1
    fi
    ok "descubierto: $WAREHOUSE_ID"
else
    ok "indicado: $WAREHOUSE_ID"
fi

# Variables que se le pasan al bundle. Se arman como arreglo para que un valor
# con espacios (por ejemplo el nombre del cliente) no se parta en dos.
VARS=(--var="warehouse_id=$WAREHOUSE_ID")
[ -n "$CATALOG" ] && VARS+=(--var="catalog=$CATALOG")
[ -n "$SCHEMA" ]  && VARS+=(--var="schema=$SCHEMA")
[ -n "$CLIENTE" ] && VARS+=(--var="cliente=$CLIENTE")
[ ${#EXTRA_VARS[@]} -gt 0 ] && VARS+=("${EXTRA_VARS[@]}")

# La configuración resuelta se pide una sola vez y se lee de la caché: llamar a
# `bundle validate` por cada variable es lento y multiplica las formas de fallar.
CONFIG_JSON=""
leer_var() {
    CLAVE="$1" python3 -c '
import json, os, sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
v = (d.get("variables") or {}).get(os.environ["CLAVE"]) or {}
val = v.get("value", v.get("default", ""))
print("" if val is None else val)
' <<< "$CONFIG_JSON"
}

paso "3/9 · Validando el bundle"
CONFIG_JSON="$( (cd "$REPO_ROOT" && db bundle validate -t "$TARGET" "${VARS[@]}" -o json 2>/dev/null) || true )"
if [ -z "$CONFIG_JSON" ]; then
    malo "El bundle no valida. Corré para ver el detalle:"
    echo "     databricks bundle validate -t $TARGET"
    exit 1
fi
EFF_CATALOG="$(leer_var catalog)"
EFF_SCHEMA="$(leer_var schema)"
EFF_CLIENTE="$(leer_var cliente)"
EFF_APP="$(leer_var app_name)"
EFF_PREFIX="$(leer_var job_prefix)"
EFF_LB_INSTANCIA="$(leer_var lakebase_instance)"
EFF_LB_DB="$(leer_var lakebase_db)"
EFF_LB_CAPACIDAD="$(leer_var lakebase_capacity)"
EFF_GENIE_TITULO="$(leer_var genie_title)"
# El catálogo por defecto es 'main' porque es el nombre habitual, pero no está
# garantizado: hay workspaces que nunca lo crearon. Conviene decirlo acá, con la
# lista de los que sí existen, y no dejar que reviente adentro del deploy.
if ! db catalogs get "$EFF_CATALOG" >/dev/null 2>&1; then
    malo "El catálogo '$EFF_CATALOG' no existe o no tenés acceso."
    DISPONIBLES="$(db catalogs list -o json 2>/dev/null | python3 -c '
import json, sys
try: cats = json.load(sys.stdin)
except Exception: cats = []
# Los catálogos de sistema y de Delta Sharing son de solo lectura: ofrecerlos
# como destino sería mandar al que instala a un error de permisos.
print("  ".join(c["name"] for c in cats
                if c.get("catalog_type") not in ("SYSTEM_CATALOG", "DELTASHARING_CATALOG")))
' || true)"
    [ -n "$DISPONIBLES" ] && echo "     Podés escribir en:  $DISPONIBLES"
    echo "     Elegí uno:  ./instalar.sh --catalog <nombre>"
    exit 1
fi

ok "esquema  ${EFF_CATALOG}.${EFF_SCHEMA}"
ok "app      ${EFF_APP}"
ok "jobs     prefijo '${EFF_PREFIX}'"
ok "cliente  ${EFF_CLIENTE}"
ok "lakebase ${EFF_LB_INSTANCIA} (${EFF_LB_CAPACIDAD})"

# ---------------------------------------------------------------------------
paso "4/9 · Instancia de Lakebase"
# ---------------------------------------------------------------------------
# Va antes del deploy porque el app la lleva adjunta como recurso: si no existe,
# el deploy del app falla. Y ese vínculo es justamente lo que hace que Databricks
# le cree al service principal su rol de Postgres dentro de la instancia.
#
# Crear una instancia tarda varios minutos. Si ya existe se reusa tal cual, así
# que reinstalar no vuelve a esperar ni duplica el costo.
LB_ESTADO="$(db database get-database-instance "$EFF_LB_INSTANCIA" -o json 2>/dev/null | python3 -c '
import json,sys
try: print(json.load(sys.stdin).get("state") or "")
except Exception: print("")
' || true)"

if [ -z "$LB_ESTADO" ]; then
    echo "  creando '$EFF_LB_INSTANCIA' ($EFF_LB_CAPACIDAD) — tarda unos minutos..."
    PAYLOAD="$(NOMBRE="$EFF_LB_INSTANCIA" CAP="$EFF_LB_CAPACIDAD" python3 -c '
import json, os
print(json.dumps({"name": os.environ["NOMBRE"], "capacity": os.environ["CAP"]}))
')"
    if ! db database create-database-instance --json "$PAYLOAD" >/dev/null 2>&1; then
        malo "No pude crear la instancia de Lakebase '$EFF_LB_INSTANCIA'."
        echo "     Probá a mano para ver el error real:"
        echo "     databricks database create-database-instance --json '$PAYLOAD'"
        echo "     Si tu workspace no tiene Lakebase habilitado, comentá el recurso"
        echo "     'lakebase' en resources/04_app.yml y volvé a instalar."
        exit 1
    fi
    ok "instancia creada"
elif [ "$LB_ESTADO" = "AVAILABLE" ]; then
    ok "ya existía y está disponible"
else
    # Una instancia detenida no acepta conexiones, y el job de más abajo fallaría
    # con un timeout que no explica nada.
    aviso "estado '$LB_ESTADO' — intento reanudarla"
    db database update-database-instance "$EFF_LB_INSTANCIA" \
        --json '{"stopped": false}' >/dev/null 2>&1 || true
fi

# El host se resuelve siempre, existiera la instancia o no: es lo que recibe el
# app como LAKEBASE_HOST y no se guarda en ningún archivo del repositorio.
LB_HOST="$(db database get-database-instance "$EFF_LB_INSTANCIA" -o json 2>/dev/null | python3 -c '
import json,sys
try: print(json.load(sys.stdin).get("read_write_dns") or "")
except Exception: print("")
' || true)"

if [ -z "$LB_HOST" ]; then
    malo "La instancia existe pero no tiene host todavía."
    echo "     Esperá a que quede AVAILABLE y volvé a correr el instalador:"
    echo "     databricks database get-database-instance $EFF_LB_INSTANCIA"
    exit 1
fi
ok "host     $LB_HOST"
VARS+=(--var="lakebase_host=$LB_HOST")

# ---------------------------------------------------------------------------
paso "5/9 · Dashboard AI/BI"
# ---------------------------------------------------------------------------
# Va antes del deploy porque el app recibe el id del dashboard como variable de
# entorno. Hacerlo después obligaría a un segundo deploy solo para eso.
DASHBOARD_ID=""
if [ "$CON_DASHBOARD" -eq 1 ]; then
    PARENT_PATH="/Workspace/Users/$YO/.bundle/dn-centro-inteligencia/$TARGET/dashboards"
    ID_FILE="$REPO_ROOT/dashboards/.dashboard_id.$TARGET"
    db workspace mkdirs "$PARENT_PATH" >/dev/null 2>&1 || true
    TITULO="dichter & neira · Centro de Inteligencia"
    [ "$TARGET" != "demo" ] && TITULO="$TITULO [$TARGET]"
    if PROFILE="${PROFILE:-DEFAULT}" WAREHOUSE_ID="$WAREHOUSE_ID" \
       CATALOG="$EFF_CATALOG" SCHEMA="$EFF_SCHEMA" CLIENTE="$EFF_CLIENTE" \
       PARENT_PATH="$PARENT_PATH" DASHBOARD_TITLE="$TITULO" DASHBOARD_ID_FILE="$ID_FILE" \
       python3 "$REPO_ROOT/dashboards/construir_dashboard.py" 2>&1 | sed 's/^/  /'; then
        [ -f "$ID_FILE" ] && DASHBOARD_ID="$(tr -d '\n' < "$ID_FILE")"
    fi
    if [ -n "$DASHBOARD_ID" ]; then
        ok "dashboard $DASHBOARD_ID"
    else
        aviso "no se pudo crear el dashboard; el app va a ocultar esa pestaña"
    fi
else
    aviso "omitido por --sin-dashboard"
fi
[ -n "$DASHBOARD_ID" ] && VARS+=(--var="dashboard_id=$DASHBOARD_ID")

# ---------------------------------------------------------------------------
paso "6/9 · Desplegando el bundle (esquema, jobs, app)"
# ---------------------------------------------------------------------------
(cd "$REPO_ROOT" && db bundle deploy -t "$TARGET" "${VARS[@]}") 2>&1 | sed 's/^/  /'
ok "esquema, 9 jobs y el app creados"

# ---------------------------------------------------------------------------
paso "7/9 · Creando las tablas y sembrando el dato"
# ---------------------------------------------------------------------------
if [ "$CON_DATOS" -eq 1 ]; then
    echo "  esto tarda un par de minutos: aplica el DDL, siembra los maestros y"
    echo "  corre un primer pulso de cada generador para que el tablero no abra vacío."
    (cd "$REPO_ROOT" && db bundle run instalar -t "$TARGET" "${VARS[@]}") 2>&1 | sed 's/^/  /'
    ok "tablas creadas y sembradas en ${EFF_CATALOG}.${EFF_SCHEMA}"
else
    aviso "omitido por --sin-datos (después: databricks bundle run instalar -t $TARGET)"
fi


# ---------------------------------------------------------------------------
paso "8/9 · Sala de Genie"
# ---------------------------------------------------------------------------
# Va después de la semilla y no antes, aunque el app necesite el id de la sala:
# Genie valida las tablas al crear el espacio y falla si todavía no existen. Por
# eso el id se aplica con un segundo `bundle deploy`, que solo toca la
# configuración del app y es rápido.
#
# La sala se crea con las tablas cargadas y con las instrucciones del negocio, que
# es la parte que importa: sin ellas Genie promedia sobre toda la competencia
# cuando la pregunta era sobre nuestras marcas, y responde plausible y mal.
GENIE_ID=""
if [ "$CON_GENIE" -eq 1 ]; then
    GENIE_TITULO="$EFF_GENIE_TITULO"
    GENIE_ID_FILE="$REPO_ROOT/scripts/.genie_id.$TARGET"
    if PROFILE="${PROFILE:-DEFAULT}" WAREHOUSE_ID="$WAREHOUSE_ID" \
       CATALOG="$EFF_CATALOG" SCHEMA="$EFF_SCHEMA" CLIENTE="$EFF_CLIENTE" \
       GENIE_TITLE="$GENIE_TITULO" GENIE_ID_FILE="$GENIE_ID_FILE" \
       PARENT_PATH="/Users/$YO" \
       python3 "$REPO_ROOT/scripts/crear_genie.py" 2>&1 | sed 's/^/  /'; then
        [ -f "$GENIE_ID_FILE" ] && GENIE_ID="$(tr -d '\n' < "$GENIE_ID_FILE")"
    fi
    if [ -z "$GENIE_ID" ]; then
        aviso "sin sala real; el app va a usar el modo demostración precargado"
    fi
else
    aviso "omitido por --sin-genie (el app usa preguntas precargadas)"
fi
if [ -n "$GENIE_ID" ]; then
    VARS+=(--var="genie_space_id=$GENIE_ID")
    echo "  aplicando el id de la sala en la configuración del app..."
    (cd "$REPO_ROOT" && db bundle deploy -t "$TARGET" "${VARS[@]}") >/dev/null 2>&1 \
      && ok "app configurado con la sala real" \
      || aviso "no pude reconfigurar el app; va a quedar en modo demostración"
fi

# ---------------------------------------------------------------------------
paso "9/9 · Permisos, arranque y camino caliente"
# ---------------------------------------------------------------------------
# El app corre con su propio service principal, que recién existe ahora. Adjuntar
# el warehouse le dio permiso sobre el warehouse, no sobre el dato: sin estos
# grants todas las rutas devuelven INSUFFICIENT_PERMISSIONS.
SP="$(db apps get "$EFF_APP" -o json 2>/dev/null | python3 -c '
import json,sys
try: print(json.load(sys.stdin).get("service_principal_client_id") or "")
except Exception: print("")
' || true)"

if [ -z "$SP" ]; then
    aviso "no pude leer el service principal del app; otorgá los permisos a mano (ver docs/INSTALACION.md)"
else
    ok "service principal $SP"
    correr_sql() {
        local payload estado
        payload=$(WID="$WAREHOUSE_ID" STMT="$1" python3 -c '
import json, os
print(json.dumps({"warehouse_id": os.environ["WID"], "statement": os.environ["STMT"],
                  "wait_timeout": "30s"}))
')
        estado=$(db api post /api/2.0/sql/statements --json "$payload" 2>/dev/null | python3 -c '
import json,sys
try: print(json.load(sys.stdin).get("status",{}).get("state","?"))
except Exception: print("?")
')
        printf '    %-10s %s\n' "$estado" "${1:0:66}"
    }
    correr_sql "GRANT USE CATALOG ON CATALOG \`$EFF_CATALOG\` TO \`$SP\`"
    correr_sql "GRANT USE SCHEMA, SELECT, MODIFY ON SCHEMA \`$EFF_CATALOG\`.\`$EFF_SCHEMA\` TO \`$SP\`"

    # El botón "Iniciar demo" enciende y apaga los jobs desde la interfaz, así que
    # el service principal tiene que poder administrarlos.
    echo "  permisos sobre los jobs de la demo:"
    db jobs list -o json 2>/dev/null | PREFIX="$EFF_PREFIX" python3 -c '
import json, os, sys
p = os.environ["PREFIX"]
for j in json.load(sys.stdin):
    n = (j.get("settings") or {}).get("name", "")
    if n.startswith(p):
        print(j["job_id"], n, sep="\t")
' | while IFS=$'\t' read -r JID NOMBRE; do
        PAYLOAD=$(SP="$SP" python3 -c '
import json, os
print(json.dumps({"access_control_list": [{
    "service_principal_name": os.environ["SP"], "permission_level": "CAN_MANAGE"}]}))
')
        if db api patch "/api/2.0/permissions/jobs/$JID" --json "$PAYLOAD" >/dev/null 2>&1; then
            printf '    ok         %s\n' "$NOMBRE"
        else
            printf '    a mano     %s\n' "$NOMBRE"
        fi
    done

    # La sala de Genie es un objeto con su propia lista de control de acceso: el
    # app la consulta con la identidad del service principal, no con la de quien
    # instaló. Sin este permiso la pestaña devuelve 403.
    if [ -n "$GENIE_ID" ]; then
        PAYLOAD=$(SP="$SP" python3 -c '
import json, os
print(json.dumps({"access_control_list": [{
    "service_principal_name": os.environ["SP"], "permission_level": "CAN_RUN"}]}))
')
        if db api patch "/api/2.0/permissions/genie/$GENIE_ID" --json "$PAYLOAD" >/dev/null 2>&1; then
            printf '    ok         sala de Genie\n'
        else
            printf '    a mano     sala de Genie (dale CAN_RUN al service principal)\n'
        fi
    fi
fi

# `bundle deploy` crea el app y sube el código, pero no lo despliega: el app
# queda con el compute encendido y sin servir nada. `bundle run` sobre el
# recurso del app es lo que instala dependencias y levanta el proceso. Arrancar
# el compute con `apps start` no alcanza — el app contesta 502.
echo "  desplegando el código en el app (instala dependencias, tarda unos minutos)..."
if ! (cd "$REPO_ROOT" && db bundle run centro_inteligencia -t "$TARGET" "${VARS[@]}") 2>&1 | sed 's/^/    /'; then
    malo "El app no llegó a desplegarse."
    echo "     Reintentá:  databricks bundle run centro_inteligencia -t $TARGET"
    exit 1
fi

# El estado se confirma contra la API, no se asume: un app que quedó
# UNAVAILABLE con el compute ACTIVE se ve igual de bien en el log del deploy.
APP_JSON="$(db apps get "$EFF_APP" -o json 2>/dev/null || true)"
URL="$(python3 -c '
import json,sys
try: print(json.load(sys.stdin).get("url") or "")
except Exception: print("")
' <<< "$APP_JSON")"
APP_ESTADO="$(python3 -c '
import json,sys
try: print((json.load(sys.stdin).get("app_status") or {}).get("state") or "")
except Exception: print("")
' <<< "$APP_JSON")"

if [ "$APP_ESTADO" = "RUNNING" ]; then
    ok "app sirviendo"
else
    echo "  ⚠ el app quedó en estado '${APP_ESTADO:-desconocido}'."
    echo "    Mirá los logs en ${URL:-la consola} o reintentá:"
    echo "    databricks bundle run centro_inteligencia -t $TARGET"
fi

# Recién ahora se puede preparar Postgres, y el orden no es casual: el rol del
# service principal dentro de la instancia lo crea Databricks al desplegar el app
# con el recurso `database` adjunto. Correr esto antes dejaría las tablas sin
# permisos para el app, que conectaría bien y fallaría en el primer SELECT.
LB_LISTO=0
if [ "$CON_DATOS" -eq 1 ]; then
    echo "  preparando Lakebase (esquema, perfiles de PDV y permisos)..."
    if (cd "$REPO_ROOT" && db bundle run lakebase -t "$TARGET" "${VARS[@]}") 2>&1 | sed 's/^/    /'; then
        ok "copiloto de campo listo"
        LB_LISTO=1
    else
        aviso "el copiloto de campo quedó sin preparar. Reintentá:"
        echo "    databricks bundle run lakebase -t $TARGET"
    fi
else
    aviso "Lakebase sin sembrar por --sin-datos (después: databricks bundle run lakebase -t $TARGET)"
fi

echo
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ Instalación completa"
echo "════════════════════════════════════════════════════════════════"
echo
echo "  App          ${URL:-(mirala en Compute > Apps)}"
[ -n "$DASHBOARD_ID" ] && echo "  Dashboard    $DASHBOARD_ID"
[ -n "$GENIE_ID" ]     && echo "  Genie        $GENIE_ID"
echo "  Esquema      ${EFF_CATALOG}.${EFF_SCHEMA}"
if [ "$LB_LISTO" -eq 1 ]; then
    echo "  Lakebase     ${EFF_LB_INSTANCIA} · base ${EFF_LB_DB}"
else
    echo "  Lakebase     ${EFF_LB_INSTANCIA} (sin preparar)"
fi
echo

# Databricks no guarda los `--var` con los que se desplegó, así que los scripts
# de operación necesitan los mismos flags. En vez de pedir que se los acuerden,
# se imprimen los comandos ya armados con lo que efectivamente se usó.
COMUNES="${TARGET:+ -t $TARGET}${PROFILE:+ -p $PROFILE}"
[ -n "$CATALOG" ] && COMUNES="$COMUNES --catalog $EFF_CATALOG"
[ -n "$SCHEMA" ]  && COMUNES="$COMUNES --schema $EFF_SCHEMA"

echo "  Encender la operación   ./encender.sh$COMUNES"
echo "  Apagarla                ./apagar.sh$COMUNES"
echo "  Vaciar el dato vivo     ./scripts/limpiar.sh$COMUNES"
echo "  Desinstalar todo        ./desinstalar.sh$COMUNES"
echo
echo "  También podés encenderla desde el propio app, con el botón"
echo "  \"Iniciar demo\" arriba a la derecha."
echo
