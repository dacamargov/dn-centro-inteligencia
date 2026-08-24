#!/usr/bin/env bash
# Enciende la operación: los generadores primero, los agentes después.
#
#   ./encender.sh                 # arranque completo
#   ./encender.sh --solo-datos    # generadores nada más
#   ./encender.sh --sin-espera    # los agentes arrancan ya, con el dato que haya
#   ./encender.sh -t pruebas      # sobre la instalación de pruebas
#
# El orden no es capricho: un agente sin dato fresco no tiene nada que analizar y
# gasta un tick en decir que no ve nada. Por eso se espera ~75 s entre despausar
# los generadores y despausar los agentes.
#
# Lo mismo se puede hacer desde el propio app con el botón "Iniciar demo".
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/scripts/_comun.sh"
parsear_flags "$@"
MODO="${RESTO[0]:-completo}"
cargar_config

echo "════════════════════════════════════════════════════════════════"
echo "  Centro de Inteligencia — encender ($MODO)"
echo "  ${CATALOG}.${SCHEMA} · jobs '${JOB_PREFIX}'"
echo "════════════════════════════════════════════════════════════════"

encender_grupo() {
    local etiqueta="$1"; shift
    local encontrado=0
    printf '\n%s\n' "$etiqueta"
    while IFS=$'\t' read -r jid nombre; do
        [ -z "$jid" ] && continue
        encontrado=1
        pausar_job "$jid" "UNPAUSED"
        printf '  activo    %s\n' "$nombre"
        printf '  corrida %s  %s\n' "$(correr_job "$jid")" "$nombre"
    done < <("$@")
    [ "$encontrado" -eq 0 ] && echo "  (no encontré jobs — ¿corriste ./instalar.sh?)"
}

encender_grupo "[1/2] Generadores de datos" jobs_generadores

if [ "$MODO" = "--solo-datos" ]; then
    echo
    echo "✅ Generadores corriendo. Los agentes quedaron apagados."
    exit 0
fi

if [ "$MODO" != "--sin-espera" ]; then
    echo
    echo "  calentando el dato (75 s) para que los agentes vean visitas frescas..."
    sleep 75
fi

encender_grupo "[2/2] Agentes" jobs_agentes

echo
echo "✅ Operación en marcha. Generadores cada 1-5 min, agentes cada 2 min."
echo "   Apagar: ./apagar.sh${TARGET:+ -t $TARGET}"
