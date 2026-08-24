#!/usr/bin/env bash
# Corre SQL contra el warehouse de la instalación, sin abrir la interfaz.
#
#   ./scripts/consultar.sh "SELECT COUNT(*) FROM {S}.visitas"
#   ./scripts/consultar.sh --json "SELECT * FROM {S}.recomendaciones LIMIT 3"
#   echo "SELECT 1" | ./scripts/consultar.sh
#
# `{S}` se expande al catálogo.esquema de la instalación, así que las consultas
# de ejemplo de la documentación funcionan tal cual estén escritas.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_comun.sh"
parsear_flags "$@"
cargar_config

PROFILE="${PROFILE:-DEFAULT}" WAREHOUSE_ID="$WAREHOUSE_ID" FQ_SCHEMA="$FQ_SCHEMA" \
  python3 "$REPO_ROOT/scripts/consultar.py" ${RESTO[@]+"${RESTO[@]}"}
