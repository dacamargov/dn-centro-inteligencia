#!/usr/bin/env bash
# Borra del workspace todo lo que creó la instalación.
#
#   ./desinstalar.sh
#   ./desinstalar.sh -t pruebas
#   ./desinstalar.sh --si            # sin preguntar
#
# Se borra: el app, los 9 jobs, el esquema con TODAS sus tablas, el dashboard, la
# sala de Genie y la instancia de Lakebase.
# El catálogo y el SQL Warehouse no se tocan: no los creó esta instalación.
#
# Ojo: el esquema es un recurso del bundle, así que su borrado se lleva el dato.
# Si lo que querés es vaciar el dato y conservar la instalación, usá
# `./scripts/limpiar.sh`.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/scripts/_comun.sh"
parsear_flags "$@"
SIN_PREGUNTAR=0
for a in ${RESTO[@]+"${RESTO[@]}"}; do [ "$a" = "--si" ] && SIN_PREGUNTAR=1; done
cargar_config

echo "════════════════════════════════════════════════════════════════"
echo "  Centro de Inteligencia — desinstalar (target '$TARGET')"
echo "════════════════════════════════════════════════════════════════"
echo
echo "  Se va a borrar:"
echo "    · el app        ${APP_NAME}"
echo "    · los jobs      prefijo '${JOB_PREFIX}'"
echo "    · el esquema    ${FQ_SCHEMA}  ← con todas sus tablas y su dato"
echo "    · el dashboard  del Centro de Inteligencia"
echo "    · la sala       ${GENIE_TITLE}"
echo "    · Lakebase      ${LAKEBASE_INSTANCE}  ← con el log de sugerencias"
echo

if [ "$SIN_PREGUNTAR" -eq 0 ]; then
    printf "  Escribí el nombre del esquema para confirmar (%s): " "$SCHEMA"
    read -r RESPUESTA
    if [ "$RESPUESTA" != "$SCHEMA" ]; then
        echo "  cancelado."
        exit 1
    fi
fi

# El dashboard va primero: no es un recurso del bundle, así que `destroy` no lo
# alcanza y quedaría huérfano en la carpeta del workspace.
#
# Se lo busca por nombre en el workspace, no en un archivo local: el id que
# `instalar.sh` deja en dashboards/ no está versionado, así que quien clone el
# repo para desinstalar no lo tiene, y el dashboard sobreviviría en silencio.
ID_FILE="$REPO_ROOT/dashboards/.dashboard_id.$TARGET"
TITULO="dichter & neira · Centro de Inteligencia"
[ "$TARGET" != "demo" ] && TITULO="$TITULO [$TARGET]"

DID=""
[ -f "$ID_FILE" ] && DID="$(tr -d '\n' < "$ID_FILE")"
if [ -z "$DID" ]; then
    DID="$(db api get /api/2.0/lakeview/dashboards 2>/dev/null | TITULO="$TITULO" python3 -c '
import json, os, sys
try: ds = json.load(sys.stdin).get("dashboards") or []
except Exception: ds = []
for d in ds:
    if d.get("display_name") == os.environ["TITULO"] and d.get("lifecycle_state") != "TRASHED":
        print(d.get("dashboard_id", "")); break
' || true)"
fi

if [ -n "$DID" ]; then
    db api delete "/api/2.0/lakeview/dashboards/$DID" >/dev/null 2>&1 \
      && echo "  borrado el dashboard $DID" \
      || echo "  no pude borrar el dashboard $DID (borralo desde la interfaz)"
fi
rm -f "$ID_FILE"

# La sala de Genie tampoco es un recurso del bundle. Se la busca por título, igual
# que el dashboard, para que desinstalar funcione desde un clon limpio.
GENIE_ID_FILE="$REPO_ROOT/scripts/.genie_id.$TARGET"
GID=""
[ -f "$GENIE_ID_FILE" ] && GID="$(tr -d '\n' < "$GENIE_ID_FILE")"
if [ -z "$GID" ]; then
    GID="$(db api get /api/2.0/genie/spaces 2>/dev/null | TITULO="$GENIE_TITLE" python3 -c '
import json, os, sys
try: salas = json.load(sys.stdin).get("spaces") or []
except Exception: salas = []
for s in salas:
    if s.get("title") == os.environ["TITULO"]:
        print(s.get("space_id", "")); break
' || true)"
fi

if [ -n "$GID" ]; then
    db genie trash-space "$GID" >/dev/null 2>&1 \
      && echo "  borrada la sala de Genie $GID" \
      || echo "  no pude borrar la sala $GID (borrala desde la interfaz)"
fi
rm -f "$GENIE_ID_FILE"

echo
(cd "$REPO_ROOT" && db bundle destroy -t "$TARGET" --auto-approve) 2>&1 | sed 's/^/  /'

# Databricks borra el app de forma asincrónica: `destroy` vuelve enseguida y el
# app se queda un rato en DELETING. Conviene esperarlo, porque si alguien
# reinstala en ese momento el nombre todavía está tomado.
if [ -n "$APP_NAME" ]; then
    for _ in $(seq 1 30); do
        db apps get "$APP_NAME" >/dev/null 2>&1 || break
        sleep 5
    done
    db apps get "$APP_NAME" >/dev/null 2>&1 \
      && echo "  ⚠ el app $APP_NAME sigue borrándose; esperá un minuto antes de reinstalar"
fi

# La instancia de Lakebase va al final y no antes: mientras el app exista, la
# tiene adjunta como recurso y el borrado se rechaza. Recién con el app fuera se
# puede soltar. Y hay que borrarla, porque una instancia de Postgres factura por
# existir aunque nadie la consulte.
if [ -n "$LAKEBASE_INSTANCE" ] && db database get-database-instance "$LAKEBASE_INSTANCE" >/dev/null 2>&1; then
    echo
    if db database delete-database-instance "$LAKEBASE_INSTANCE" >/dev/null 2>&1; then
        echo "  borrada la instancia de Lakebase $LAKEBASE_INSTANCE"
    else
        echo "  ⚠ no pude borrar la instancia $LAKEBASE_INSTANCE."
        echo "    Sigue facturando. Borrala a mano:"
        echo "    databricks database delete-database-instance $LAKEBASE_INSTANCE"
    fi
fi

echo
echo "✅ Desinstalado. El catálogo y el warehouse quedaron intactos."
