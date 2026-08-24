#!/usr/bin/env bash
# Borra del workspace todo lo que creó la instalación.
#
#   ./desinstalar.sh
#   ./desinstalar.sh -t pruebas
#   ./desinstalar.sh --si            # sin preguntar
#
# Se borra: el app, los 7 jobs, el esquema con TODAS sus tablas y el dashboard.
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
ID_FILE="$REPO_ROOT/dashboards/.dashboard_id.$TARGET"
if [ -f "$ID_FILE" ]; then
    DID="$(tr -d '\n' < "$ID_FILE")"
    if [ -n "$DID" ]; then
        db api delete "/api/2.0/lakeview/dashboards/$DID" >/dev/null 2>&1 \
          && echo "  borrado el dashboard $DID" \
          || echo "  no pude borrar el dashboard $DID (borralo desde la interfaz)"
    fi
    rm -f "$ID_FILE"
fi

echo
(cd "$REPO_ROOT" && db bundle destroy -t "$TARGET" --auto-approve) 2>&1 | sed 's/^/  /'

echo
echo "✅ Desinstalado. El catálogo y el warehouse quedaron intactos."
