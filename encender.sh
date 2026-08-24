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

# Deja en ENCENDIDOS cuántos jobs despausó. Se lleva la cuenta porque anunciar
# "operación en marcha" sin haber despausado un solo job es la peor salida
# posible: el problema se descubre recién durante la demo.
ENCENDIDOS=0
encender_grupo() {
    local etiqueta="$1"; shift
    ENCENDIDOS=0
    printf '\n%s\n' "$etiqueta"
    while IFS=$'\t' read -r jid nombre; do
        [ -z "$jid" ] && continue
        ENCENDIDOS=$((ENCENDIDOS + 1))
        pausar_job "$jid" "UNPAUSED"
        printf '  activo    %s\n' "$nombre"
        printf '  corrida %s  %s\n' "$(correr_job "$jid")" "$nombre"
    done < <("$@")
}

encender_grupo "[1/2] Generadores de datos" jobs_generadores
if [ "$ENCENDIDOS" -eq 0 ]; then
    echo
    echo "❌ No encontré ningún job con el prefijo '$JOB_PREFIX'."
    echo "   ¿Instalaste este target?  ./instalar.sh$(flags_usados)"
    exit 1
fi

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
if [ "$ENCENDIDOS" -eq 0 ]; then
    echo
    echo "⚠ Los generadores quedaron corriendo, pero no encontré agentes."
    echo "   Redesplegá para crearlos:  databricks bundle deploy -t $TARGET"
    exit 1
fi

echo
echo "✅ Operación en marcha. Generadores cada 1-5 min, agentes cada 2 min."
echo "   Apagar: ./apagar.sh$(flags_usados)"
