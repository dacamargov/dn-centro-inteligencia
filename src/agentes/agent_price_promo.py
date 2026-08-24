# Databricks notebook source
# MAGIC %md
# MAGIC # Agente — Vigía de Precio y Promoción
# MAGIC
# MAGIC Corre como Job agendado cada 2 minutos mientras la demo está encendida.
# MAGIC
# MAGIC **Misión:** vigilar el posicionamiento de precio del fabricante cliente frente a su
# MAGIC competencia directa, cadena por cadena y país por país, y detectar dónde el precio o
# MAGIC la presión promocional lo están dejando fuera de juego.
# MAGIC
# MAGIC El índice de precio está normalizado por contenido (precio por 100 g / 100 ml) y
# MAGIC calculado dentro de la subcategoría, así que 100 significa paridad real con productos
# MAGIC sustituibles, no una comparación entre tamaños de empaque distintos.

# COMMAND ----------

# MAGIC %pip install --quiet openai httpx
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./_shared

# COMMAND ----------

AGENT_NAME = "price_promo"

# COMMAND ----------

def _posicion_precio_por_categoria() -> str:
    rows = sql_to_records(f"""
        SELECT categoria,
               ROUND(AVG(CASE WHEN es_cliente THEN indice_precio END), 1) AS indice_cliente,
               ROUND(AVG(CASE WHEN NOT es_cliente THEN indice_precio END), 1) AS indice_competencia,
               ROUND(AVG(CASE WHEN es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END), 1)
                   AS promo_cliente_pct,
               ROUND(AVG(CASE WHEN NOT es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END), 1)
                   AS promo_competencia_pct,
               COUNT(*) AS observaciones
        FROM {FQ}.precios_competencia
        GROUP BY categoria
        ORDER BY indice_cliente DESC
    """, limit=20)
    return json.dumps(rows, default=str)


def _plazas_mas_caras(limit: int = 12) -> str:
    """Combinaciones país + cadena donde el cliente está más caro frente a su competencia."""
    limit = max(1, min(25, int(limit)))
    rows = sql_to_records(f"""
        SELECT country_code, cadena, categoria,
               ROUND(AVG(CASE WHEN es_cliente THEN indice_precio END), 1) AS indice_cliente,
               ROUND(AVG(CASE WHEN NOT es_cliente THEN indice_precio END), 1) AS indice_competencia,
               ROUND(AVG(CASE WHEN es_cliente THEN indice_precio END)
                     - AVG(CASE WHEN NOT es_cliente THEN indice_precio END), 1) AS brecha_pp
        FROM {FQ}.precios_competencia
        GROUP BY country_code, cadena, categoria
        HAVING AVG(CASE WHEN es_cliente THEN indice_precio END) IS NOT NULL
           AND AVG(CASE WHEN NOT es_cliente THEN indice_precio END) IS NOT NULL
        ORDER BY brecha_pp DESC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _presion_promocional(limit: int = 12) -> str:
    """Dónde la competencia está promocionando mucho más que el cliente."""
    limit = max(1, min(25, int(limit)))
    rows = sql_to_records(f"""
        SELECT categoria, country_code,
               ROUND(AVG(CASE WHEN es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END), 1)
                   AS promo_cliente_pct,
               ROUND(AVG(CASE WHEN NOT es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END), 1)
                   AS promo_competencia_pct,
               ROUND(AVG(CASE WHEN NOT es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END)
                     - AVG(CASE WHEN es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END), 1)
                   AS brecha_promo_pp
        FROM {FQ}.precios_competencia
        GROUP BY categoria, country_code
        ORDER BY brecha_promo_pp DESC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _detalle_sku(sku: str = "", categoria: str = "", limit: int = 15) -> str:
    """Precios observados de un SKU o de una categoría, por país y cadena."""
    limit = max(1, min(30, int(limit)))
    filtros = []
    if sku:
        filtros.append(f"sku = '{sku.replace(chr(39), '')}'")
    if categoria:
        filtros.append(f"categoria = '{categoria.replace(chr(39), '')}'")
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    rows = sql_to_records(f"""
        SELECT sku, marca, fabricante, es_cliente, categoria, subcategoria,
               country_code, cadena, precio_usd, en_promo, indice_precio
        FROM {FQ}.precios_competencia
        {where}
        ORDER BY indice_precio DESC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _cruce_precio_ejecucion() -> str:
    """Cruza posición de precio con ejecución en anaquel, por categoría.

    Es el cruce más valioso del tablero: una categoría cara Y mal ejecutada pierde
    venta por dos frentes a la vez, y la acción correcta es distinta según cuál pese más.
    """
    rows = sql_to_records(f"""
        WITH precio AS (
          SELECT categoria,
                 AVG(CASE WHEN es_cliente THEN indice_precio END) AS indice_cliente,
                 AVG(CASE WHEN NOT es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END)
                   AS promo_competencia_pct,
                 AVG(CASE WHEN es_cliente THEN (CASE WHEN en_promo THEN 100.0 ELSE 0.0 END) END)
                   AS promo_cliente_pct
          FROM {FQ}.precios_competencia GROUP BY categoria
        ),
        ejecucion AS (
          SELECT categoria,
                 AVG(CASE WHEN ejecucion_perfecta THEN 100.0 ELSE 0.0 END) AS ejecucion_pct,
                 SUM(CASE WHEN es_cliente THEN facings ELSE 0 END) * 100.0
                   / NULLIF(SUM(facings), 0) AS sos_cliente_pct
          FROM {FQ}.visitas
          WHERE visit_ts >= current_timestamp() - INTERVAL 45 MINUTES
          GROUP BY categoria
        )
        SELECT p.categoria,
               ROUND(p.indice_cliente, 1) AS indice_precio_cliente,
               ROUND(p.promo_cliente_pct, 1) AS promo_cliente_pct,
               ROUND(p.promo_competencia_pct, 1) AS promo_competencia_pct,
               ROUND(e.ejecucion_pct, 1) AS ejecucion_pct,
               m.meta_ejecucion_pct,
               ROUND(e.sos_cliente_pct, 1) AS sos_cliente_pct,
               m.meta_sos_pct
        FROM precio p
        JOIN ejecucion e USING (categoria)
        JOIN {FQ}.metas_categoria m USING (categoria)
        ORDER BY e.ejecucion_pct ASC
    """, limit=20)
    return json.dumps(rows, default=str)


# COMMAND ----------

TOOLS = [
    Tool(
        name="posicion_precio_por_categoria",
        description="Índice de precio del cliente vs competencia y participación en promoción, "
                    "por categoría. Índice 100 = paridad. Empieza siempre por aquí.",
        parameters={"type": "object", "properties": {}, "required": []},
        fn=_posicion_precio_por_categoria,
    ),
    Tool(
        name="plazas_mas_caras",
        description="Combinaciones de país + cadena + categoría donde el cliente está más caro "
                    "frente a su competencia directa, ordenadas por la brecha.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 12}},
            "required": [],
        },
        fn=_plazas_mas_caras,
    ),
    Tool(
        name="presion_promocional",
        description="Dónde la competencia está promocionando mucho más que el cliente, "
                    "por categoría y país.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 12}},
            "required": [],
        },
        fn=_presion_promocional,
    ),
    Tool(
        name="detalle_sku",
        description="Precios observados de un SKU concreto o de una categoría, abiertos por "
                    "país y cadena. Úsalo para aterrizar una recomendación en un producto real.",
        parameters={
            "type": "object",
            "properties": {
                "sku": {"type": "string", "default": ""},
                "categoria": {"type": "string", "default": ""},
                "limit": {"type": "integer", "default": 15},
            },
            "required": [],
        },
        fn=_detalle_sku,
    ),
    Tool(
        name="cruce_precio_ejecucion",
        description="Cruza posición de precio con ejecución en anaquel por categoría. "
                    "Revela dónde el problema es de precio, dónde es de ejecución, y dónde son ambos.",
        parameters={"type": "object", "properties": {}, "required": []},
        fn=_cruce_precio_ejecucion,
    ),
]

# COMMAND ----------

SYSTEM_PROMPT = """Eres el agente "Vigía de Precio y Promoción" de dichter & neira. Analizas
el seguimiento continuo de precios en el punto de venta y produces recomendaciones para el
equipo de revenue growth del fabricante cliente.

Cómo leer el índice de precio: está normalizado por contenido (precio por 100 g o 100 ml) y
calculado dentro de la subcategoría. Un índice de 112 significa que el producto cuesta 12%
más por gramo que el promedio de productos sustituibles en ese mismo anaquel. 100 es paridad.

Tienes 5 herramientas. Usa entre 2 y 4 antes de decidir. Nunca repitas una herramienta con
los mismos parámetros.

Busca UNA de estas situaciones:
1. Una categoría donde el cliente está muy por encima de la competencia en índice de precio
2. Una plaza concreta (país + cadena) con una brecha de precio anómala frente al resto
3. Una categoría donde la competencia promociona mucho más que el cliente
4. Una categoría cara Y mal ejecutada a la vez — el caso más grave, porque pierde por dos frentes
5. Una categoría donde el cliente está barato y podría recuperar margen

Criterios de severidad:
- "low"      → desvío pequeño, informativo
- "medium"   → brecha de 8 a 15 puntos de índice, o de promoción, en una categoría
- "high"     → brecha mayor a 15 puntos, o brecha de precio combinada con ejecución bajo meta
- "critical" → el cliente está fuera de mercado en una categoría completa

Reglas de calidad, importantes:
- Cita SIEMPRE el índice del cliente, el de la competencia y la brecha en puntos.
- Nombra la categoría, el país y la cadena concretos. "Revisar precios" no es una recomendación.
- Un precio alto NO es automáticamente un error: una marca líder sostiene premium. Lo que hay
  que señalar es cuando el premium es inconsistente entre plazas, o cuando coincide con
  ejecución por debajo de meta, porque ahí sí se está perdiendo venta.
- Si recomiendas bajar precio, di cuánto y en qué plaza. Si recomiendas activar promoción,
  di en qué categoría y contra qué competidor.
- Usa should_recommend: false SOLO si la tabla de precios está vacía.

Tipos válidos para suggested_action.type:
- "ajustar_precio" — params: {"categoria": "...", "country_code": "...", "cadena": "...",
                              "indice_actual": X, "indice_objetivo": Y}
- "activar_promo"  — params: {"categoria": "...", "country_code": "...",
                              "promo_actual_pct": X, "promo_competencia_pct": Y}"""

USER_PROMPT = """Analiza la posición de precio y promoción del fabricante cliente frente a su
competencia. Empieza por posicion_precio_por_categoria y profundiza donde veas la brecha más
relevante. Decide si hay algo que merezca una recomendación ahora.
Responde en JSON, en español latinoamericano."""

# COMMAND ----------

run_id = log_agent_run_start(AGENT_NAME)
recs_generated = 0
status = "success"
error = None

try:
    parsed = run_agent(AGENT_NAME, SYSTEM_PROMPT, USER_PROMPT, TOOLS)

    if parsed and parsed.get("should_recommend"):
        rec_id = write_recommendation(
            agent_name=AGENT_NAME,
            severity=parsed.get("severity", "medium"),
            title=parsed.get("title", "(sin título)")[:200],
            analysis=parsed.get("analysis", ""),
            recommendation=parsed.get("recommendation", ""),
            suggested_action=parsed.get("suggested_action", {}),
            supporting_data=parsed.get("supporting_data", {}),
        )
        recs_generated = 1
        print(f"✅ Recomendación {rec_id}: {parsed.get('title')}")
    else:
        print("➖ Sin recomendación en este tick")
        if parsed:
            print(f"   Salida: {json.dumps(parsed, indent=2, ensure_ascii=False)}")
except Exception as e:
    status = "error"
    error = f"{type(e).__name__}: {e}"
    print(f"❌ Error del agente: {error}")
    raise
finally:
    log_agent_run_end(run_id, status, recs_generated, error)
