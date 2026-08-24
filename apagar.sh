#!/usr/bin/env bash
# Pausa todos los jobs de la operación. El dato queda donde está; para vaciarlo,
# `./scripts/limpiar.sh`.
#
#   ./apagar.sh
#   ./apagar.sh -t pruebas
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/scripts/_comun.sh"
parsear_flags "$@"
cargar_config

echo "════════════════════════════════════════════════════════════════"
echo "  Centro de Inteligencia — apagar"
echo "════════════════════════════════════════════════════════════════"
echo

encontrado=0
# Solo generadores y agentes: el job `instalar` no tiene agenda, así que no hay
# nada que pausarle.
{ jobs_generadores; jobs_agentes; } | while IFS=$'\t' read -r jid nombre; do
    [ -z "$jid" ] && continue
    pausar_job "$jid" "PAUSED"
    printf '  pausado   %s\n' "$nombre"
done

echo
echo "✅ Jobs pausados. Las corridas en vuelo terminan solas."
echo "   Encender: ./encender.sh${TARGET:+ -t $TARGET}"
