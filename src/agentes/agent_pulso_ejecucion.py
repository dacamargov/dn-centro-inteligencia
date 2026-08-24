# Databricks notebook source
# MAGIC %md
# MAGIC # Agente — Pulso de Ejecución
# MAGIC
# MAGIC Corre como Job agendado cada 2 minutos mientras la demo está encendida.
# MAGIC
# MAGIC **Misión:** vigilar la ejecución en el punto de venta —disponibilidad, cumplimiento
# MAGIC de planograma y share of shelf— y levantar **una** recomendación accionable por tick,
# MAGIC o ninguna si no hay nada que valga la pena.
# MAGIC
# MAGIC El agente no recibe los datos masticados: recibe herramientas y decide cuáles
# MAGIC consultar. Eso es lo que lo hace un agente y no un reporte con plantilla.

# COMMAND ----------

# MAGIC %pip install --quiet openai httpx
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./_shared

# COMMAND ----------

AGENT_NAME = "pulso_ejecucion"

# COMMAND ----------

def _resumen_ejecucion(window_minutes: int = 30) -> str:
    window_minutes = max(5, min(90, int(window_minutes)))
    general = sql_to_records(f"""
        SELECT COUNT(*) AS observaciones,
               COUNT(DISTINCT store_id) AS pdv_auditados,
               ROUND(AVG(CASE WHEN en_stock THEN 100.0 ELSE 0.0 END), 1) AS disponibilidad_pct,
               ROUND(AVG(CASE WHEN ejecucion_perfecta THEN 100.0 ELSE 0.0 END), 1) AS ejecucion_pct,
               ROUND(AVG(CASE WHEN en_promo THEN 100.0 ELSE 0.0 END), 1) AS promo_pct
        FROM {FQ}.visitas
        WHERE visit_ts >= current_timestamp() - INTERVAL {window_minutes} MINUTES
    """, limit=1)

    por_categoria = sql_to_records(f"""
        SELECT v.categoria,
               COUNT(*) AS observaciones,
               ROUND(AVG(CASE WHEN v.en_stock THEN 100.0 ELSE 0.0 END), 1) AS disponibilidad_pct,
               m.meta_disponibilidad_pct,
               ROUND(AVG(CASE WHEN v.ejecucion_perfecta THEN 100.0 ELSE 0.0 END), 1) AS ejecucion_pct,
               m.meta_ejecucion_pct,
               ROUND(SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END) * 100.0
                     / NULLIF(SUM(v.facings), 0), 1) AS sos_cliente_pct,
               m.meta_sos_pct
        FROM {FQ}.visitas v
        JOIN {FQ}.metas_categoria m USING (categoria)
        WHERE v.visit_ts >= current_timestamp() - INTERVAL {window_minutes} MINUTES
        GROUP BY v.categoria, m.meta_disponibilidad_pct, m.meta_ejecucion_pct, m.meta_sos_pct
        ORDER BY ejecucion_pct ASC
    """, limit=20)

    return json.dumps({"ventana_min": window_minutes, "general": general[0] if general else {},
                       "por_categoria": por_categoria}, default=str)


def _quiebres_criticos(limit: int = 12) -> str:
    """SKUs del cliente con peor disponibilidad, agrupados por país y cadena."""
    limit = max(1, min(25, int(limit)))
    rows = sql_to_records(f"""
        SELECT sku, ANY_VALUE(marca) AS marca, categoria, country_code, cadena,
               COUNT(*) AS observaciones,
               ROUND(AVG(CASE WHEN en_stock THEN 100.0 ELSE 0.0 END), 1) AS disponibilidad_pct
        FROM {FQ}.visitas
        WHERE visit_ts >= current_timestamp() - INTERVAL 45 MINUTES
          AND es_cliente
        GROUP BY sku, categoria, country_code, cadena
        HAVING COUNT(*) >= 4
        ORDER BY disponibilidad_pct ASC, observaciones DESC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _pdv_peor_ejecucion(limit: int = 10) -> str:
    """Puntos de venta con peor ejecución perfecta, con su mercaderista asignado."""
    limit = max(1, min(20, int(limit)))
    rows = sql_to_records(f"""
        SELECT v.store_id, t.nombre AS tienda, t.canal, t.cadena, t.ciudad,
               t.country_code, t.mercaderista,
               COUNT(*) AS observaciones,
               ROUND(AVG(CASE WHEN v.ejecucion_perfecta THEN 100.0 ELSE 0.0 END), 1) AS ejecucion_pct,
               ROUND(AVG(CASE WHEN v.en_stock THEN 100.0 ELSE 0.0 END), 1) AS disponibilidad_pct
        FROM {FQ}.visitas v
        JOIN {FQ}.tiendas t USING (store_id)
        WHERE v.visit_ts >= current_timestamp() - INTERVAL 45 MINUTES
        GROUP BY v.store_id, t.nombre, t.canal, t.cadena, t.ciudad, t.country_code, t.mercaderista
        HAVING COUNT(*) >= 10
        ORDER BY ejecucion_pct ASC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _brecha_share_of_shelf(limit: int = 10) -> str:
    """Dónde el share of shelf del cliente está más lejos de su meta."""
    limit = max(1, min(20, int(limit)))
    rows = sql_to_records(f"""
        SELECT v.categoria, v.country_code, v.canal,
               COUNT(*) AS observaciones,
               ROUND(SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END) * 100.0
                     / NULLIF(SUM(v.facings), 0), 1) AS sos_cliente_pct,
               m.meta_sos_pct,
               ROUND(SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END) * 100.0
                     / NULLIF(SUM(v.facings), 0) - m.meta_sos_pct, 1) AS brecha_pp
        FROM {FQ}.visitas v
        JOIN {FQ}.metas_categoria m USING (categoria)
        WHERE v.visit_ts >= current_timestamp() - INTERVAL 45 MINUTES
        GROUP BY v.categoria, v.country_code, v.canal, m.meta_sos_pct
        HAVING COUNT(*) >= 30
        ORDER BY brecha_pp ASC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _comparar_con_baseline() -> str:
    """El último minuto medido frente al promedio de los 10 anteriores."""
    rows = sql_to_records(f"""
        WITH por_min AS (
          SELECT minute_ts,
                 SUM(observaciones) AS obs,
                 SUM(ejecucion_pct * observaciones) / NULLIF(SUM(observaciones), 0) AS ejecucion
          FROM {FQ}.ejecucion_realtime
          WHERE minute_ts >= current_timestamp() - INTERVAL 11 MINUTES
          GROUP BY minute_ts
        ),
        ultimo AS (SELECT * FROM por_min ORDER BY minute_ts DESC LIMIT 1),
        base AS (
          SELECT AVG(obs) AS obs_prom, AVG(ejecucion) AS ejec_prom FROM por_min
          WHERE minute_ts < (SELECT minute_ts FROM ultimo)
        )
        SELECT u.minute_ts AS ultimo_minuto,
               u.obs AS obs_ultimo, ROUND(u.ejecucion, 1) AS ejecucion_ultimo,
               ROUND(b.obs_prom, 1) AS obs_baseline,
               ROUND(b.ejec_prom, 1) AS ejecucion_baseline,
               ROUND(u.ejecucion - b.ejec_prom, 1) AS delta_pp
        FROM ultimo u, base b
    """, limit=1)
    return json.dumps(rows[0] if rows else {}, default=str)


# COMMAND ----------

TOOLS = [
    Tool(
        name="resumen_ejecucion",
        description="KPIs de ejecución en PDV (disponibilidad, ejecución perfecta, share of shelf) "
                    "globales y por categoría, contra sus metas. Empieza siempre por aquí.",
        parameters={
            "type": "object",
            "properties": {
                "window_minutes": {"type": "integer", "description": "Ventana en minutos (5-90)", "default": 30}
            },
            "required": [],
        },
        fn=_resumen_ejecucion,
    ),
    Tool(
        name="quiebres_criticos",
        description="SKUs del fabricante cliente con peor disponibilidad, desglosados por país y cadena. "
                    "Sirve para identificar dónde se está perdiendo venta por falta de producto en anaquel.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 12}},
            "required": [],
        },
        fn=_quiebres_criticos,
    ),
    Tool(
        name="pdv_peor_ejecucion",
        description="Puntos de venta con peor ejecución perfecta, con su mercaderista asignado. "
                    "Sirve para dirigir una visita correctiva a una tienda concreta.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
            "required": [],
        },
        fn=_pdv_peor_ejecucion,
    ),
    Tool(
        name="brecha_share_of_shelf",
        description="Dónde el share of shelf del cliente está más por debajo de su meta, "
                    "abierto por categoría, país y canal.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
            "required": [],
        },
        fn=_brecha_share_of_shelf,
    ),
    Tool(
        name="comparar_con_baseline",
        description="Compara el último minuto medido con el promedio de los 10 anteriores. "
                    "Detecta deterioros o mejoras súbitas de la ejecución.",
        parameters={"type": "object", "properties": {}, "required": []},
        fn=_comparar_con_baseline,
    ),
]

# COMMAND ----------

SYSTEM_PROMPT = """Eres el agente "Pulso de Ejecución" de dichter & neira, la firma de
inteligencia de mercados que mide el punto de venta para marcas de consumo masivo en
Latinoamérica. Analizas el flujo continuo de auditorías de anaquel por reconocimiento de
imagen y produces recomendaciones accionables para el equipo comercial del fabricante cliente.

Tienes 5 herramientas. Usa entre 2 y 4 para reunir evidencia antes de decidir. Nunca llames
a la misma herramienta con los mismos parámetros dos veces.

Busca UNA de estas situaciones:
1. Una categoría con ejecución perfecta claramente por debajo de su meta → visita correctiva
2. Un SKU del cliente con quiebre de stock concentrado en un país o cadena → alerta de reposición
3. Un PDV con ejecución muy baja de forma consistente → visita prioritaria del mercaderista
4. Una brecha grande de share of shelf frente a la meta → negociación de espacio con la cadena
5. Un deterioro súbito frente al baseline → investigar qué cambió

Criterios de severidad:
- "low"      → hallazgo interesante, sin urgencia
- "medium"   → brecha clara que merece atención esta semana
- "high"     → brecha grande y concentrada, con pérdida de venta asociada
- "critical" → quiebre generalizado o desplome de ejecución

Reglas de calidad, importantes:
- Cita SIEMPRE cifras concretas de las herramientas: el porcentaje, la meta y la brecha en
  puntos porcentuales. Una recomendación sin números no le sirve a nadie.
- Nombra el objeto concreto de la acción: qué categoría, qué SKU, qué país, qué cadena, qué PDV.
- Distingue disponibilidad (¿está el producto?) de cumplimiento de planograma (¿está bien puesto?).
  Son problemas distintos con dueños distintos: reposición es del distribuidor, planograma es del
  mercaderista. Di cuál de los dos es.
- Usa should_recommend: false SOLO si no hay observaciones en la ventana.

Tipos válidos para suggested_action.type:
- "visita_prioritaria"   — params: {"store_id": "...", "mercaderista": "...", "motivo": "..."}
- "corregir_planograma"  — params: {"categoria": "...", "country_code": "...", "brecha_pp": X}
- "ampliar_espacio"      — params: {"categoria": "...", "cadena": "...", "sos_actual": X, "sos_meta": Y}
- "visita_prioritaria" también aplica para reposición urgente de un SKU en quiebre."""

USER_PROMPT = """Analiza el estado actual de la ejecución en la red de PDV. Empieza por
resumen_ejecucion y luego profundiza con las herramientas que te parezcan relevantes según
lo que veas. Decide si hay algo que merezca una recomendación ejecutiva ahora.
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
