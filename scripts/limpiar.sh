#!/usr/bin/env bash
# Vacía el dato vivo y deja la instalación lista para volver a arrancar.
#
#   ./scripts/limpiar.sh            # vacía solo las tablas transitorias
#   ./scripts/limpiar.sh --completo # además vuelve a sembrar los maestros
#   ./scripts/limpiar.sh -t pruebas
#
# Se conserva:  el esquema, los maestros (países, PDV, productos, metas), el
#               dashboard y el app.
# Se vacía:     visitas, precios, social, recomendaciones, bitácoras, traslados.
#
# Lo mismo está disponible desde el app, en el botón "Limpiar datos" del
# encabezado, que además muestra cuántas filas hay en cada tabla antes de borrar.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_comun.sh"
parsear_flags "$@"
MODO="${RESTO[0]:-suave}"
cargar_config

echo "════════════════════════════════════════════════════════════════"
echo "  Centro de Inteligencia — limpiar ($MODO)"
echo "  ${FQ_SCHEMA}"
echo "════════════════════════════════════════════════════════════════"

echo
echo "[1/3] Pausando los jobs..."
{ jobs_generadores; jobs_agentes; } | while IFS=$'\t' read -r jid nombre; do
    [ -z "$jid" ] && continue
    pausar_job "$jid" "PAUSED"
    printf '  pausado   %s\n' "$nombre"
done

# Estas son las tablas que crecen con el tiempo. Los maestros no están en la
# lista a propósito: vaciarlos deja la demo sin universo medido y hay que volver
# a sembrar, que tarda.
TRANSITORIAS=(
  visitas
  ejecucion_realtime
  precios_competencia
  social_posts
  recomendaciones
  runs
  action_log
  acciones_campo
  campanas
  traslados
)

echo
echo "[2/3] Vaciando tablas transitorias..."
for t in "${TRANSITORIAS[@]}"; do
    estado="$(sql "TRUNCATE TABLE ${FQ_SCHEMA}.${t}" | estado_sql)"
    printf '  %-10s %s\n' "$estado" "$t"
done

echo
if [ "$MODO" = "--completo" ] || [ "$MODO" = "completo" ]; then
    echo "[3/3] Volviendo a sembrar los maestros..."
    (cd "$REPO_ROOT" && db bundle run instalar -t "$TARGET" --only maestros) 2>&1 | sed 's/^/  /'
else
    echo "[3/3] Maestros conservados (para re-sembrarlos: --completo)."
fi

echo
echo "✅ Listo. Los jobs quedaron pausados."
echo "   Arrancar de nuevo: ./encender.sh${TARGET:+ -t $TARGET}"
