#!/usr/bin/env python3
"""Crea el dashboard AI/BI (Lakeview) del Centro de Inteligencia vía API.

Un dashboard de Lakeview no es un recurso que el bundle pueda armar solo: su
definición son datasets con SQL que lleva el catálogo y el esquema adentro. Así
que se construye acá, con la misma configuración que el bundle, y `instalar.sh`
le pasa el id resultante al app.

La configuración llega por variables de entorno:
  PROFILE            perfil del CLI de Databricks
  WAREHOUSE_ID       id del SQL Warehouse
  CATALOG            catálogo de Unity Catalog
  SCHEMA             esquema de la instalación
  CLIENTE            marca-cliente del estudio
  PARENT_PATH        carpeta del workspace donde crear el dashboard
  DASHBOARD_TITLE    (opcional) nombre a mostrar
  DASHBOARD_ID_FILE  (opcional) dónde escribir el id creado
"""
import json
import os
import subprocess
import uuid

PROFILE = os.environ.get("PROFILE", "DEFAULT")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")
CATALOG = os.environ.get("CATALOG", "main")
SCHEMA = os.environ.get("SCHEMA", "ditcher_neira")
CLIENTE = os.environ.get("CLIENTE", "Nestlé")
PARENT_PATH = os.environ.get("PARENT_PATH", "")
FQ = f"{CATALOG}.{SCHEMA}"

# El título es configurable porque `main()` borra el dashboard que encuentre con
# este mismo nombre en esta misma carpeta. Dos instalaciones en el workspace
# (por ejemplo la real y una de pruebas) tienen que diferir en uno de los dos, o
# la segunda se lleva por delante el dashboard de la primera.
TITLE = os.environ.get("DASHBOARD_TITLE") or "dichter & neira · Centro de Inteligencia"

# Dónde se guarda el id creado; lo lee `instalar.sh` para configurar el app.
DASHBOARD_ID_FILE = os.environ.get("DASHBOARD_ID_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".dashboard_id"
)

# Paleta de la marca: azul corporativo, cian, y los semáforos de ejecución.
COLORS = ["#33BDEE", "#0D5CAB", "#00A972", "#FFAB00", "#FF3621", "#8BCAE7", "#AB4057", "#919191"]


def lines(*ls):
    """queryLines como lista de strings terminados en salto de línea.

    El API concatena los elementos sin separador, así que el salto tiene que ir
    dentro de cada elemento.
    """
    return [line + "\n" for line in ls]


# ============================================================
# DATASETS
# ============================================================
DATASETS = [
    {
        "name": "ds_kpi_disponibilidad",
        "displayName": "KPI: disponibilidad en anaquel",
        "queryLines": lines(
            "SELECT ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100, 1)",
            "       AS disponibilidad_pct",
            f"FROM {FQ}.visitas",
            "WHERE visit_ts >= current_timestamp() - INTERVAL 30 MINUTES",
        ),
    },
    {
        "name": "ds_kpi_ejecucion",
        "displayName": "KPI: ejecución perfecta",
        "queryLines": lines(
            "SELECT ROUND(AVG(CASE WHEN es_cliente THEN CAST(ejecucion_perfecta AS INT) END) * 100, 1)",
            "       AS ejecucion_pct",
            f"FROM {FQ}.visitas",
            "WHERE visit_ts >= current_timestamp() - INTERVAL 30 MINUTES",
        ),
    },
    {
        "name": "ds_kpi_sos",
        "displayName": "KPI: share of shelf",
        "queryLines": lines(
            "SELECT ROUND(SUM(CASE WHEN es_cliente THEN facings ELSE 0 END)",
            "             / NULLIF(SUM(facings), 0) * 100, 1) AS sos_pct",
            f"FROM {FQ}.visitas",
            "WHERE visit_ts >= current_timestamp() - INTERVAL 30 MINUTES",
        ),
    },
    {
        "name": "ds_kpi_quiebres",
        "displayName": "KPI: quiebres detectados",
        "queryLines": lines(
            "SELECT SUM(CASE WHEN es_cliente AND NOT en_stock THEN 1 ELSE 0 END) AS quiebres",
            f"FROM {FQ}.visitas",
            "WHERE visit_ts >= current_timestamp() - INTERVAL 30 MINUTES",
        ),
    },
    {
        "name": "ds_timeline_ejecucion",
        "displayName": "Ejecución por minuto y categoría",
        "queryLines": lines(
            "SELECT DATE_TRUNC('MINUTE', visit_ts) AS minuto,",
            "       categoria,",
            "       ROUND(AVG(CASE WHEN es_cliente THEN CAST(en_stock AS INT) END) * 100, 1)",
            "         AS disponibilidad_pct",
            f"FROM {FQ}.visitas",
            "WHERE visit_ts >= current_timestamp() - INTERVAL 45 MINUTES",
            "GROUP BY 1, 2",
            "ORDER BY 1",
        ),
    },
    {
        "name": "ds_meta_vs_realizado",
        "displayName": "Meta vs realizado por categoría",
        "queryLines": lines(
            "WITH r AS (",
            "  SELECT categoria,",
            "         AVG(CASE WHEN es_cliente THEN CAST(ejecucion_perfecta AS INT) END) * 100 AS realizado",
            f"  FROM {FQ}.visitas",
            "  WHERE visit_ts >= current_timestamp() - INTERVAL 45 MINUTES",
            "  GROUP BY categoria",
            ")",
            "SELECT m.categoria,",
            "       ROUND(COALESCE(r.realizado, 0), 1)                            AS ejecucion_pct,",
            "       ROUND(m.meta_ejecucion_pct, 1)                                AS meta_pct,",
            "       ROUND(COALESCE(r.realizado, 0) - m.meta_ejecucion_pct, 1)     AS brecha_pp",
            f"FROM {FQ}.metas_categoria m",
            "LEFT JOIN r ON r.categoria = m.categoria",
            "ORDER BY brecha_pp",
        ),
    },
    {
        "name": "ds_skus_criticos",
        "displayName": "SKUs con peor disponibilidad",
        "queryLines": lines(
            "SELECT v.sku,",
            "       p.nombre  AS producto,",
            "       p.marca,",
            "       p.categoria,",
            "       COUNT(DISTINCT CASE WHEN NOT v.en_stock THEN v.store_id END) AS pdv_agotado,",
            "       ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1)                 AS disponibilidad_pct",
            f"FROM {FQ}.visitas v",
            f"JOIN {FQ}.productos p ON p.sku = v.sku",
            "WHERE v.visit_ts >= current_timestamp() - INTERVAL 45 MINUTES",
            "  AND v.es_cliente",
            "GROUP BY v.sku, p.nombre, p.marca, p.categoria",
            "HAVING COUNT(*) >= 5",
            "ORDER BY disponibilidad_pct ASC",
            "LIMIT 20",
        ),
    },
    {
        "name": "ds_ejecucion_pais",
        "displayName": "Ejecución por país",
        "queryLines": lines(
            "SELECT pa.pais,",
            "       ROUND(AVG(CASE WHEN v.es_cliente THEN CAST(v.en_stock AS INT) END) * 100, 1)",
            "         AS disponibilidad_pct",
            f"FROM {FQ}.visitas v",
            f"JOIN {FQ}.paises pa ON pa.country_code = v.country_code",
            "WHERE v.visit_ts >= current_timestamp() - INTERVAL 45 MINUTES",
            "GROUP BY pa.pais",
            "ORDER BY disponibilidad_pct DESC",
        ),
    },
    {
        "name": "ds_sentimiento_cliente",
        "displayName": "Sentimiento sobre nuestras marcas",
        "queryLines": lines(
            "SELECT sentiment, COUNT(*) AS posts",
            f"FROM {FQ}.social_posts",
            f"WHERE fabricante = '{CLIENTE}'",
            "  AND posted_at >= current_timestamp() - INTERVAL 60 MINUTES",
            "GROUP BY sentiment",
        ),
    },
]


# ============================================================
# WIDGETS
# ============================================================
def kpi_counter(name, dataset_name, value_field, title, decimals=1):
    return {
        "name": name,
        "queries": [{
            "name": "main_query",
            "query": {
                "datasetName": dataset_name,
                "fields": [{"name": "value", "expression": f"`{value_field}`"}],
                "disaggregated": True,
            },
        }],
        "spec": {
            "version": 2,
            "widgetType": "counter",
            "encodings": {
                "value": {
                    "fieldName": "value",
                    "displayName": title,
                    "format": {
                        "type": "number-plain",
                        "abbreviation": "compact",
                        "decimalPlaces": {"type": "max", "places": decimals},
                    },
                },
            },
            "frame": {"showTitle": True, "title": title},
        },
    }


W_KPI_DISP = kpi_counter("w_kpi_disp", "ds_kpi_disponibilidad", "disponibilidad_pct",
                         "Disponibilidad en anaquel (%)")
W_KPI_EJEC = kpi_counter("w_kpi_ejec", "ds_kpi_ejecucion", "ejecucion_pct",
                         "Ejecución perfecta (%)")
W_KPI_SOS = kpi_counter("w_kpi_sos", "ds_kpi_sos", "sos_pct", "Share of shelf (%)")
W_KPI_QUIEBRES = kpi_counter("w_kpi_quiebres", "ds_kpi_quiebres", "quiebres",
                             "Quiebres detectados", decimals=0)


W_TIMELINE = {
    "name": "w_timeline",
    "queries": [{
        "name": "main_query",
        "query": {
            "datasetName": "ds_timeline_ejecucion",
            "fields": [
                {"name": "minuto", "expression": "`minuto`"},
                {"name": "categoria", "expression": "`categoria`"},
                {"name": "disponibilidad_pct", "expression": "AVG(`disponibilidad_pct`)"},
            ],
            "disaggregated": False,
        },
    }],
    "spec": {
        "version": 3,
        "widgetType": "line",
        "encodings": {
            "x": {"fieldName": "minuto", "scale": {"type": "temporal"}, "displayName": "Minuto"},
            "y": {"fieldName": "disponibilidad_pct", "scale": {"type": "quantitative"},
                  "displayName": "Disponibilidad (%)"},
            "color": {"fieldName": "categoria", "scale": {"type": "categorical"},
                      "displayName": "Categoría"},
        },
        "frame": {"showTitle": True,
                  "title": "Disponibilidad por minuto y categoría (últimos 45 min)"},
        "mark": {"colors": COLORS},
    },
}


W_META = {
    "name": "w_meta",
    "queries": [{
        "name": "main_query",
        "query": {
            "datasetName": "ds_meta_vs_realizado",
            "fields": [
                {"name": "categoria", "expression": "`categoria`"},
                {"name": "brecha_pp", "expression": "SUM(`brecha_pp`)"},
            ],
            "disaggregated": False,
        },
    }],
    "spec": {
        "version": 3,
        "widgetType": "bar",
        "encodings": {
            "x": {"fieldName": "brecha_pp", "scale": {"type": "quantitative"},
                  "displayName": "Brecha contra la meta (pp)"},
            "y": {"fieldName": "categoria",
                  "scale": {"type": "categorical", "sort": {"by": "x-reversed"}},
                  "displayName": "Categoría"},
            "label": {"show": True},
        },
        "frame": {"showTitle": True, "title": "Meta vs realizado · ejecución perfecta"},
        "mark": {"colors": COLORS},
    },
}


W_PAIS = {
    "name": "w_pais",
    "queries": [{
        "name": "main_query",
        "query": {
            "datasetName": "ds_ejecucion_pais",
            "fields": [
                {"name": "pais", "expression": "`pais`"},
                {"name": "disponibilidad_pct", "expression": "AVG(`disponibilidad_pct`)"},
            ],
            "disaggregated": False,
        },
    }],
    "spec": {
        "version": 3,
        "widgetType": "bar",
        "encodings": {
            "x": {"fieldName": "disponibilidad_pct", "scale": {"type": "quantitative"},
                  "displayName": "Disponibilidad (%)"},
            "y": {"fieldName": "pais",
                  "scale": {"type": "categorical", "sort": {"by": "x-reversed"}},
                  "displayName": "País"},
            "label": {"show": True},
        },
        "frame": {"showTitle": True, "title": "Disponibilidad por país"},
        "mark": {"colors": COLORS},
    },
}


W_SKUS = {
    "name": "w_skus",
    "queries": [{
        "name": "main_query",
        "query": {
            "datasetName": "ds_skus_criticos",
            "fields": [
                {"name": "sku", "expression": "`sku`"},
                {"name": "producto", "expression": "`producto`"},
                {"name": "marca", "expression": "`marca`"},
                {"name": "categoria", "expression": "`categoria`"},
                {"name": "pdv_agotado", "expression": "`pdv_agotado`"},
                {"name": "disponibilidad_pct", "expression": "`disponibilidad_pct`"},
            ],
            "disaggregated": True,
        },
    }],
    "spec": {
        "version": 1,
        "widgetType": "table",
        "encodings": {
            "columns": [
                {"fieldName": "sku", "type": "string", "displayAs": "string", "title": "SKU"},
                {"fieldName": "producto", "type": "string", "displayAs": "string",
                 "title": "Producto"},
                {"fieldName": "marca", "type": "string", "displayAs": "string", "title": "Marca"},
                {"fieldName": "categoria", "type": "string", "displayAs": "string",
                 "title": "Categoría"},
                {"fieldName": "pdv_agotado", "type": "integer", "displayAs": "number",
                 "numberFormat": "0", "title": "PDV agotado", "alignContent": "right"},
                {"fieldName": "disponibilidad_pct", "type": "float", "displayAs": "number",
                 "numberFormat": "0.0", "title": "Disponibilidad %", "alignContent": "right"},
            ],
        },
        "frame": {"showTitle": True, "title": "SKUs que exigen reposición"},
    },
}


W_SENTIMIENTO = {
    "name": "w_sentimiento",
    "queries": [{
        "name": "main_query",
        "query": {
            "datasetName": "ds_sentimiento_cliente",
            "fields": [
                {"name": "sentiment", "expression": "`sentiment`"},
                {"name": "posts", "expression": "SUM(`posts`)"},
            ],
            "disaggregated": False,
        },
    }],
    "spec": {
        "version": 3,
        "widgetType": "pie",
        "encodings": {
            "angle": {"fieldName": "posts", "scale": {"type": "quantitative"},
                      "displayName": "Posts"},
            "color": {
                "fieldName": "sentiment",
                "scale": {
                    "type": "categorical",
                    "mappings": [
                        {"value": "positivo", "color": "#00A972"},
                        {"value": "neutral",  "color": "#919191"},
                        {"value": "negativo", "color": "#FF3621"},
                    ],
                },
                "displayName": "Sentimiento",
            },
            "label": {"show": True},
        },
        "frame": {"showTitle": True, "title": f"Conversación sobre {CLIENTE} (última hora)"},
    },
}


# ============================================================
# LAYOUT (grilla de 6 columnas)
# ============================================================
LAYOUT = [
    {"widget": W_KPI_DISP,     "position": {"x": 0, "y": 0, "width": 1, "height": 2}},
    {"widget": W_KPI_EJEC,     "position": {"x": 1, "y": 0, "width": 1, "height": 2}},
    {"widget": W_KPI_SOS,      "position": {"x": 2, "y": 0, "width": 1, "height": 2}},
    {"widget": W_KPI_QUIEBRES, "position": {"x": 3, "y": 0, "width": 1, "height": 2}},
    {"widget": W_SENTIMIENTO,  "position": {"x": 4, "y": 0, "width": 2, "height": 6}},
    {"widget": W_TIMELINE,     "position": {"x": 0, "y": 2, "width": 4, "height": 4}},
    {"widget": W_META,         "position": {"x": 0, "y": 6, "width": 3, "height": 5}},
    {"widget": W_PAIS,         "position": {"x": 3, "y": 6, "width": 3, "height": 5}},
    {"widget": W_SKUS,         "position": {"x": 0, "y": 11, "width": 6, "height": 6}},
]


PAGE = {
    "name": uuid.uuid4().hex[:8],
    "displayName": "Ejecución en el punto de venta",
    "pageType": "PAGE_TYPE_CANVAS",
    "layout": LAYOUT,
}


SERIALIZED = {
    "datasets": DATASETS,
    "pages": [PAGE],
    "uiSettings": {
        "theme": {"widgetHeaderAlignment": "ALIGNMENT_UNSPECIFIED"},
        "applyModeEnabled": False,
    },
}


# ============================================================
# CREACIÓN
# ============================================================
def cli(*args):
    return subprocess.run(
        ["databricks", *args, "-p", PROFILE], capture_output=True, text=True,
    )


def dashboard_existente():
    """El dashboard activo con este nombre, si lo hay.

    Se compara solo por `display_name`: la lista de la API devuelve
    `parent_path` en null, así que exigir que coincida hacía que nunca se
    encontrara nada y cada reinstalación chocara contra su propio dashboard.
    """
    salida = cli("api", "get", "/api/2.0/lakeview/dashboards")
    try:
        candidatos = json.loads(salida.stdout).get("dashboards", [])
    except Exception:
        return None
    for d in candidatos:
        if d.get("display_name") == TITLE and d.get("lifecycle_state") != "TRASHED":
            return d.get("dashboard_id")
    return None


def guardar_id(did):
    with open(DASHBOARD_ID_FILE, "w") as f:
        f.write((did or "") + "\n")


def main():
    payload = {
        "display_name": TITLE,
        "warehouse_id": WAREHOUSE_ID,
        "parent_path": PARENT_PATH,
        "serialized_dashboard": json.dumps(SERIALIZED, ensure_ascii=False),
    }
    cli("workspace", "mkdirs", PARENT_PATH)

    # Reinstalar sobre una instalación previa tiene que funcionar, y crear un
    # dashboard nuevo cada vez rompería los enlaces que alguien haya guardado.
    # Si ya existe, se actualiza en su lugar y se conserva su id.
    previo = dashboard_existente()
    if previo:
        actualizado = cli(
            "api", "patch", f"/api/2.0/lakeview/dashboards/{previo}",
            "--json", json.dumps({
                "display_name": TITLE,
                "warehouse_id": WAREHOUSE_ID,
                "serialized_dashboard": json.dumps(SERIALIZED, ensure_ascii=False),
            }, ensure_ascii=False),
        )
        if actualizado.returncode == 0:
            print("\n✅ Dashboard actualizado")
            print(f"  dashboard_id : {previo}")
            print(f"  display_name : {TITLE}")
            guardar_id(previo)
            return
        print(f"  no pude actualizar el dashboard {previo}, intento recrearlo")
        cli("api", "delete", f"/api/2.0/lakeview/dashboards/{previo}")

    out = cli("api", "post", "/api/2.0/lakeview/dashboards",
              "--json", json.dumps(payload, ensure_ascii=False))

    # Borrar un dashboard lo manda a la papelera pero deja su archivo .lvdash.json
    # en la carpeta, y ese archivo basta para que el POST choque por nombre
    # repetido. Se limpia el huérfano y se reintenta una vez.
    if out.returncode != 0 and "already exists" in (out.stderr or ""):
        print("  quedaba un archivo de dashboard huérfano; lo borro y reintento")
        cli("workspace", "delete", f"{PARENT_PATH}/{TITLE}.lvdash.json")
        out = cli("api", "post", "/api/2.0/lakeview/dashboards",
                  "--json", json.dumps(payload, ensure_ascii=False))

    if out.returncode != 0:
        print("❌ falló la creación del dashboard")
        print(out.stderr[:1000])
        return

    try:
        d = json.loads(out.stdout)
        print("\n✅ Dashboard creado")
        print(f"  dashboard_id : {d.get('dashboard_id')}")
        print(f"  display_name : {d.get('display_name')}")
        print(f"  path         : {d.get('path')}")
        guardar_id(d.get("dashboard_id"))
    except json.JSONDecodeError:
        print("No pude interpretar la respuesta como JSON:")
        print(out.stdout[:1000])


if __name__ == "__main__":
    main()
