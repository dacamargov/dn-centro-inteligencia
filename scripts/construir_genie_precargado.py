#!/usr/bin/env python3
"""Genera app/server/canned_genie.json a partir del dato real de la demo.

El app usa ese archivo cuando GENIE_SPACE_ID está vacío (modo demostración): las
preguntas sugeridas responden con cifras coherentes con el esquema, en vez de
números inventados. Volver a correr este script después de sembrar el dato deja
las respuestas alineadas con lo que el tablero muestra.

Uso:
    ./scripts/construir_genie_precargado.sh
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from q import run_sql  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "app" / "server" / "canned_genie.json"

# Cada entrada: id, pregunta, palabras clave para el matcher difuso, el SQL que
# se muestra al usuario y una plantilla que arma el texto a partir de las filas.
PREGUNTAS = [
    {
        "id": "disponibilidad_categoria",
        "question": "¿Cuál es la disponibilidad en anaquel por categoría?",
        "keywords": ["disponibilidad", "anaquel", "categoria", "categoría", "stock", "quiebre"],
        "sql": """SELECT categoria,
       ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100, 1) AS disponibilidad_pct,
       COUNT(*) AS observaciones
FROM {S}.visitas
WHERE visit_ts >= current_timestamp() - INTERVAL 30 MINUTES
GROUP BY categoria
ORDER BY disponibilidad_pct""",
        "resumen": lambda rows: (
            f"La disponibilidad promedio va de {rows[0][1]}% en {rows[0][0]} a "
            f"{rows[-1][1]}% en {rows[-1][0]}. {rows[0][0]} es la categoría con más "
            f"riesgo de quiebre en la última media hora."
        ),
    },
    {
        "id": "peor_ejecucion_pdv",
        "question": "¿Qué puntos de venta tienen la peor ejecución esta hora?",
        "keywords": ["peor", "ejecucion", "ejecución", "punto de venta", "pdv", "tienda", "tiendas"],
        "sql": """SELECT t.nombre, t.cadena, t.ciudad, t.country_code,
       ROUND(AVG(CASE WHEN v.es_cliente THEN CAST(v.ejecucion_perfecta AS INT) END) * 100, 1) AS ejecucion_pct
FROM {S}.visitas v
JOIN {S}.tiendas t ON t.store_id = v.store_id
WHERE v.visit_ts >= current_timestamp() - INTERVAL 60 MINUTES
GROUP BY t.nombre, t.cadena, t.ciudad, t.country_code
HAVING COUNT(*) >= 20
ORDER BY ejecucion_pct
LIMIT 5""",
        "resumen": lambda rows: (
            f"El PDV más débil es {rows[0][0]} ({rows[0][1]}, {rows[0][2]}) con "
            f"{rows[0][4]}% de ejecución perfecta. Los cinco de la lista están todos "
            f"por debajo de {rows[-1][4]}%."
        ),
    },
    {
        "id": "sos_por_pais",
        "question": "¿Cuál es el share of shelf de nuestras marcas por país?",
        "keywords": ["share of shelf", "sos", "espacio", "anaquel", "pais", "país", "facings"],
        "sql": """SELECT p.pais,
       ROUND(SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END)
             / NULLIF(SUM(v.facings), 0) * 100, 1) AS sos_pct
FROM {S}.visitas v
JOIN {S}.paises p ON p.country_code = v.country_code
WHERE v.visit_ts >= current_timestamp() - INTERVAL 30 MINUTES
GROUP BY p.pais
ORDER BY sos_pct DESC""",
        "resumen": lambda rows: (
            f"{rows[0][0]} lidera con {rows[0][1]}% de share of shelf y "
            f"{rows[-1][0]} cierra con {rows[-1][1]}%. La brecha entre el mejor y el "
            f"peor mercado es de {round(float(rows[0][1]) - float(rows[-1][1]), 1)} puntos."
        ),
    },
    {
        "id": "skus_agotados",
        "question": "¿Qué SKUs están agotados en más puntos de venta?",
        "keywords": ["sku", "agotado", "agotados", "quiebre", "faltante", "out of stock"],
        "sql": """SELECT v.sku, pr.nombre AS producto, pr.marca,
       COUNT(DISTINCT CASE WHEN NOT v.en_stock THEN v.store_id END) AS pdv_agotado,
       ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1) AS disponibilidad_pct
FROM {S}.visitas v
JOIN {S}.productos pr ON pr.sku = v.sku
WHERE v.visit_ts >= current_timestamp() - INTERVAL 30 MINUTES
  AND v.es_cliente
GROUP BY v.sku, pr.nombre, pr.marca
ORDER BY pdv_agotado DESC
LIMIT 5""",
        "resumen": lambda rows: (
            f"{rows[0][1]} ({rows[0][2]}) es el peor caso: agotado en {rows[0][3]} puntos "
            f"de venta, con {rows[0][4]}% de disponibilidad. Los cinco SKUs de la lista "
            f"concentran la mayor parte de los quiebres del período."
        ),
    },
    {
        "id": "indice_precio_cadena",
        "question": "¿Cómo se compara nuestro índice de precio con la competencia por cadena?",
        "keywords": ["precio", "indice", "índice", "cadena", "competencia", "caro", "barato"],
        "sql": """SELECT cadena,
       ROUND(AVG(CASE WHEN es_cliente THEN indice_precio END), 1) AS indice_nuestro,
       ROUND(AVG(CASE WHEN NOT es_cliente THEN indice_precio END), 1) AS indice_rival
FROM {S}.precios_competencia
GROUP BY cadena
ORDER BY indice_nuestro DESC
LIMIT 6""",
        "resumen": lambda rows: (
            f"En {rows[0][0]} estamos en índice {rows[0][1]} contra {rows[0][2]} de la "
            f"competencia: es la cadena donde más pesa el sobreprecio. La más equilibrada "
            f"de la lista es {rows[-1][0]} con índice {rows[-1][1]}."
        ),
    },
    {
        "id": "moderno_vs_tradicional",
        "question": "¿Qué diferencia hay en ejecución entre canal moderno y tradicional?",
        "keywords": ["canal", "moderno", "tradicional", "diferencia", "brecha", "comparar"],
        "sql": """SELECT t.canal,
       ROUND(AVG(CASE WHEN v.es_cliente THEN CAST(v.en_stock AS INT) END) * 100, 1) AS disponibilidad_pct,
       ROUND(AVG(CASE WHEN v.es_cliente THEN CAST(v.ejecucion_perfecta AS INT) END) * 100, 1) AS ejecucion_pct,
       COUNT(DISTINCT v.store_id) AS pdv
FROM {S}.visitas v
JOIN {S}.tiendas t ON t.store_id = v.store_id
WHERE v.visit_ts >= current_timestamp() - INTERVAL 30 MINUTES
GROUP BY t.canal
ORDER BY ejecucion_pct DESC""",
        "resumen": lambda rows: (
            f"{rows[0][0]} ejecuta {rows[0][2]}% contra {rows[-1][2]}% de {rows[-1][0]}: "
            f"{round(float(rows[0][2]) - float(rows[-1][2]), 1)} puntos de brecha. El canal "
            f"más débil también arrastra la disponibilidad, en {rows[-1][1]}%."
        ),
    },
]


def main() -> int:
    profile = os.environ.get("PROFILE") or os.environ.get("DATABRICKS_PROFILE", "DEFAULT")
    warehouse = os.environ.get("WAREHOUSE_ID", "")
    fq = os.environ.get("FQ_SCHEMA") or (
        f"{os.environ.get('CATALOG', 'main')}.{os.environ.get('SCHEMA', 'ditcher_neira')}"
    )
    if not warehouse:
        print("❌ WAREHOUSE_ID vacío. Corré este script vía ./scripts/construir_genie_precargado.sh")
        return 1

    answers = []
    for p in PREGUNTAS:
        stmt = p["sql"].replace("{S}", fq)
        cols, rows = run_sql(profile, warehouse, stmt)
        if not rows:
            print(f"⚠ sin filas para '{p['id']}' — se omite")
            continue
        answers.append(
            {
                "id": p["id"],
                "question": p["question"],
                "keywords": p["keywords"],
                "text": p["resumen"](rows),
                # El SQL se guarda con el marcador y no con el esquema real: el
                # archivo se commitea, y el catálogo de quien clone el repo no es
                # el nuestro. El app lo sustituye al cargarlo.
                "sql": p["sql"].replace("{S}", "__FQ__"),
                "query_result": {
                    "columns": cols,
                    "rows": rows,
                    "row_count": len(rows),
                    "truncated": False,
                },
            }
        )
        print(f"  ✅ {p['id']}  ({len(rows)} filas)")

    payload = {
        "_comment": (
            "Respuestas preconfiguradas que usa el app cuando GENIE_SPACE_ID está vacío "
            "(modo demostración). Generadas por scripts/construir_genie_precargado.sh a partir del "
            "dato real de la demo. Para usar un Genie Space real, completa GENIE_SPACE_ID "
            "con --var genie_space_id — ver docs/GENIE.md."
        ),
        "answers": answers,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"\n✅ {len(answers)} respuestas escritas en {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
