#!/usr/bin/env bash
# Comprueba que una sala de Genie existe, que tenés permiso sobre ella y que
# responde, antes de configurarla en el app.
#
#   ./scripts/verificar_genie.sh <space_id>
#   ./scripts/verificar_genie.sh              # lista las salas del workspace
#
# Si pasa, configurala con:  ./instalar.sh --var genie_space_id=<space_id>
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_comun.sh"
parsear_flags "$@"

SPACE_ID="${RESTO[0]:-}"

if [ -z "$SPACE_ID" ]; then
    echo "Salas de Genie en este workspace:"
    db api get /api/2.0/genie/spaces 2>/dev/null | python3 -c '
import json, sys
salas = json.load(sys.stdin).get("spaces", [])
if not salas:
    print("  (ninguna — creá una desde Genie → New)")
for s in salas:
    print(f"  {s[\"space_id\"]}  {s.get(\"title\", \"(sin título)\")}")
'
    echo
    echo "Uso: $0 <space_id>"
    exit 1
fi

TITULO="$(db genie get-space "$SPACE_ID" -o json 2>/dev/null | python3 -c '
import json, sys
try: print(json.load(sys.stdin).get("title", ""))
except Exception: print("")
')"

if [ -z "$TITULO" ]; then
    echo "❌ No pude leer la sala $SPACE_ID. Revisá el id y tus permisos sobre ella."
    exit 1
fi
echo "✅ sala: $TITULO"

echo
echo "Prueba de humo — le mando una pregunta del modelo de datos:"
db genie start-conversation "$SPACE_ID" \
  "¿Cuántos productos hay en el catálogo?" -o json 2>&1 | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(f"  conversación {d.get(\"conversation_id\")} · mensaje {(d.get(\"message\") or {}).get(\"id\")}")
    print("  la sala responde.")
except Exception as e:
    print(f"  no respondió como se esperaba: {e}")
'

echo
echo "Para usarla:  ./instalar.sh --var genie_space_id=$SPACE_ID"
