#!/usr/bin/env bash
# Regenera las respuestas precargadas del chat de Genie con las cifras de ESTE
# workspace, para que el modo demostración no muestre números de otra instalación.
#
#   ./scripts/construir_genie_precargado.sh      # con la operación andando un rato
#
# Reescribe `src/app/server/canned_genie.json`. Después hay que volver a desplegar
# el app para que se lo lleve:  databricks bundle deploy -t demo
#
# Solo hace falta si se usa el modo demostración. Con un Genie Space real
# (`--var genie_space_id=…`) el app consulta la sala y este archivo no se usa.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_comun.sh"
parsear_flags "$@"
cargar_config

export PROFILE="${PROFILE:-DEFAULT}" WAREHOUSE_ID CATALOG SCHEMA CLIENTE FQ_SCHEMA
exec python3 "$REPO_ROOT/scripts/construir_genie_precargado.py" "${RESTO[@]:-}"
