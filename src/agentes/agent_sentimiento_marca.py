# Databricks notebook source
# MAGIC %md
# MAGIC # Agente — Sentimiento de Marca
# MAGIC
# MAGIC Corre como Job agendado cada 2 minutos mientras la demo está encendida.
# MAGIC
# MAGIC **Misión:** vigilar la conversación social sobre las marcas medidas (Brand & Ad Insight)
# MAGIC y, sobre todo, **cruzarla con lo que está pasando en el anaquel**.
# MAGIC
# MAGIC Ese cruce es el aporte real del agente. Una queja aislada en redes es ruido; una queja
# MAGIC por falta de producto en un país donde la medición confirma quiebre de stock es una
# MAGIC señal accionable con causa identificada.

# COMMAND ----------

# MAGIC %pip install --quiet openai httpx
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./_shared

# COMMAND ----------

AGENT_NAME = "sentimiento_marca"

# COMMAND ----------

def _termometro_marca(window_minutes: int = 20) -> str:
    window_minutes = max(5, min(90, int(window_minutes)))
    general = sql_to_records(f"""
        SELECT COUNT(*) AS posts,
               ROUND(AVG(sentiment_score), 3) AS score_promedio,
               ROUND(AVG(CASE WHEN sentiment = 'negativo' THEN 100.0 ELSE 0.0 END), 1) AS negativo_pct,
               SUM(engagement) AS engagement_total,
               SUM(CASE WHEN is_viral THEN 1 ELSE 0 END) AS virales
        FROM {FQ}.social_posts
        WHERE posted_at >= current_timestamp() - INTERVAL {window_minutes} MINUTES
    """, limit=1)

    por_fabricante = sql_to_records(f"""
        SELECT fabricante,
               COUNT(*) AS posts,
               ROUND(AVG(sentiment_score), 3) AS score_promedio,
               ROUND(AVG(CASE WHEN sentiment = 'negativo' THEN 100.0 ELSE 0.0 END), 1) AS negativo_pct,
               SUM(engagement) AS engagement_total
        FROM {FQ}.social_posts
        WHERE posted_at >= current_timestamp() - INTERVAL {window_minutes} MINUTES
        GROUP BY fabricante
        ORDER BY posts DESC
    """, limit=20)

    return json.dumps({"ventana_min": window_minutes, "general": general[0] if general else {},
                       "por_fabricante": por_fabricante}, default=str)


def _posts_negativos(limit: int = 10) -> str:
    limit = max(1, min(20, int(limit)))
    rows = sql_to_records(f"""
        SELECT post_id, platform, author_handle, author_followers, content,
               marca, fabricante, country_code, sentiment_score, engagement, is_viral, posted_at
        FROM {FQ}.social_posts
        WHERE posted_at >= current_timestamp() - INTERVAL 30 MINUTES
          AND sentiment = 'negativo'
        ORDER BY engagement DESC, sentiment_score ASC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _posts_virales(limit: int = 8) -> str:
    limit = max(1, min(15, int(limit)))
    rows = sql_to_records(f"""
        SELECT post_id, platform, author_handle, author_followers, content,
               marca, fabricante, country_code, sentiment, sentiment_score, engagement, posted_at
        FROM {FQ}.social_posts
        WHERE posted_at >= current_timestamp() - INTERVAL 45 MINUTES
          AND is_viral
        ORDER BY engagement DESC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


# Alcance por dólar invertido, por plataforma. Son las mismas constantes que usa
# el diálogo de campaña en la aplicación: si el agente promete un número y la
# pantalla calcula otro, la demo pierde el hilo justo en el momento de actuar.
ALCANCE_POR_USD = {"tiktok": 420, "instagram": 260, "facebook": 310, "x": 190}
PRESUPUESTO_REF_USD = 5000
TASA_ENGAGEMENT = 0.012


def _oportunidades_de_amplificacion(limit: int = 6) -> str:
    """Posts positivos del cliente que rinden si se les pone pauta detrás.

    Devuelve el post_id exacto y la ganancia proyectada de amplificarlo con el
    presupuesto de referencia. Es lo que convierte "hay buena conversación" en
    "amplifica ESTE post y esto es lo que ganas".
    """
    limit = max(1, min(12, int(limit)))
    rows = sql_to_records(f"""
        SELECT s.post_id, s.platform, s.author_handle, s.author_followers, s.content,
               s.marca, s.fabricante, s.country_code, s.sentiment_score,
               s.engagement, s.is_viral, s.posted_at
        FROM {FQ}.social_posts s
        JOIN {FQ}.fabricantes f
          ON f.fabricante = s.fabricante AND f.es_cliente
        LEFT JOIN {FQ}.campanas c ON c.post_id = s.post_id
        WHERE s.posted_at >= current_timestamp() - INTERVAL 45 MINUTES
          AND s.sentiment = 'positivo'
          AND c.post_id IS NULL          -- todavía sin campaña detrás
        ORDER BY s.engagement DESC
        LIMIT {limit}
    """, limit=limit)

    for r in rows:
        factor = ALCANCE_POR_USD.get((r.get("platform") or "").lower(), 240)
        alcance = PRESUPUESTO_REF_USD * factor
        r["presupuesto_referencia_usd"] = PRESUPUESTO_REF_USD
        r["alcance_incremental_estimado"] = alcance
        r["engagement_incremental_estimado"] = int(alcance * TASA_ENGAGEMENT)
        # Cuánto multiplica la pauta lo que el post ya logró solo.
        base = max(1, int(r.get("engagement") or 0))
        r["multiplicador_sobre_organico"] = round(
            (base + alcance * TASA_ENGAGEMENT) / base, 1
        )
    return json.dumps(rows, default=str)


def _sentimiento_por_pais(limit: int = 12) -> str:
    limit = max(1, min(20, int(limit)))
    rows = sql_to_records(f"""
        SELECT s.country_code, p.pais,
               COUNT(*) AS posts,
               ROUND(AVG(s.sentiment_score), 3) AS score_promedio,
               ROUND(AVG(CASE WHEN s.sentiment = 'negativo' THEN 100.0 ELSE 0.0 END), 1) AS negativo_pct
        FROM {FQ}.social_posts s
        LEFT JOIN {FQ}.paises p USING (country_code)
        WHERE s.posted_at >= current_timestamp() - INTERVAL 45 MINUTES
        GROUP BY s.country_code, p.pais
        HAVING COUNT(*) >= 2
        ORDER BY score_promedio ASC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _cruzar_con_anaquel() -> str:
    """Cruza el sentimiento social por país con la disponibilidad medida en anaquel.

    Es la herramienta que convierte una queja en un diagnóstico: si en un país la
    conversación se vuelve negativa Y la medición confirma quiebre de stock, la causa
    de la queja no es la marca, es la reposición.
    """
    rows = sql_to_records(f"""
        WITH social AS (
          SELECT country_code,
                 COUNT(*) AS posts,
                 AVG(sentiment_score) AS score,
                 AVG(CASE WHEN sentiment = 'negativo' THEN 100.0 ELSE 0.0 END) AS negativo_pct
          FROM {FQ}.social_posts
          WHERE posted_at >= current_timestamp() - INTERVAL 45 MINUTES
          GROUP BY country_code
        ),
        anaquel AS (
          SELECT country_code,
                 AVG(CASE WHEN en_stock THEN 100.0 ELSE 0.0 END) AS disponibilidad_pct,
                 AVG(CASE WHEN ejecucion_perfecta THEN 100.0 ELSE 0.0 END) AS ejecucion_pct
          FROM {FQ}.visitas
          WHERE visit_ts >= current_timestamp() - INTERVAL 45 MINUTES
            AND es_cliente
          GROUP BY country_code
        )
        SELECT s.country_code, p.pais, s.posts,
               ROUND(s.score, 3) AS score_social,
               ROUND(s.negativo_pct, 1) AS negativo_pct,
               ROUND(a.disponibilidad_pct, 1) AS disponibilidad_cliente_pct,
               ROUND(a.ejecucion_pct, 1) AS ejecucion_cliente_pct
        FROM social s
        JOIN anaquel a USING (country_code)
        LEFT JOIN {FQ}.paises p USING (country_code)
        ORDER BY s.score ASC
    """, limit=20)
    return json.dumps(rows, default=str)


# COMMAND ----------

TOOLS = [
    Tool(
        name="termometro_marca",
        description="Volumen, sentimiento promedio y engagement de la conversación social, "
                    "global y por fabricante. Empieza siempre por aquí.",
        parameters={
            "type": "object",
            "properties": {
                "window_minutes": {"type": "integer", "description": "Ventana en minutos (5-90)", "default": 20}
            },
            "required": [],
        },
        fn=_termometro_marca,
    ),
    Tool(
        name="posts_negativos",
        description="Menciones negativas recientes ordenadas por engagement. Sirve para saber "
                    "de qué se está quejando la gente exactamente.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
            "required": [],
        },
        fn=_posts_negativos,
    ),
    Tool(
        name="posts_virales",
        description="Publicaciones que superaron el umbral de viralidad en los últimos 45 minutos.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 8}},
            "required": [],
        },
        fn=_posts_virales,
    ),
    Tool(
        name="sentimiento_por_pais",
        description="Sentimiento promedio y porcentaje de menciones negativas por país.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 12}},
            "required": [],
        },
        fn=_sentimiento_por_pais,
    ),
    Tool(
        name="oportunidades_de_amplificacion",
        description="Posts positivos sobre las marcas del cliente que todavía no tienen "
                    "campaña, con la ganancia proyectada de amplificarlos: alcance e "
                    "interacciones incrementales con el presupuesto de referencia. "
                    "Devuelve el post_id exacto, que es lo que necesita la acción.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 6}},
            "required": [],
        },
        fn=_oportunidades_de_amplificacion,
    ),
    Tool(
        name="cruzar_con_anaquel",
        description="Cruza el sentimiento social por país con la disponibilidad y ejecución medidas "
                    "en el anaquel para las marcas del cliente. Revela si una caída de sentimiento "
                    "tiene una causa física en el punto de venta.",
        parameters={"type": "object", "properties": {}, "required": []},
        fn=_cruzar_con_anaquel,
    ),
]

# COMMAND ----------

SYSTEM_PROMPT = """Eres el agente "Sentimiento de Marca" de dichter & neira, dentro de la
solución Brand & Ad Insight. Analizas la conversación social sobre las marcas de consumo
masivo bajo medición y produces recomendaciones para el equipo de marketing del fabricante cliente.

Tu diferencial frente a una herramienta de escucha social cualquiera es que tienes acceso a
la medición del anaquel. Úsalo: la pregunta que solo tú puedes responder no es "¿qué se dice?"
sino "¿qué está pasando en el punto de venta que explica lo que se dice?".

Tienes 6 herramientas. Usa entre 2 y 4 antes de decidir. Nunca repitas una herramienta con
los mismos parámetros.

TU ALCANCE TERMINA EN LA CONVERSACIÓN. Tus acciones son de comunicación: amplificar
contenido o responder una crisis. La reposición de stock, la visita al PDV y el traslado
de mercadería tienen sus propios agentes y NO son tuyos. Si el cruce con anaquel explica
una queja, dilo en el análisis como causa —eso da contexto— pero la acción que propones
sigue siendo de comunicación.

Busca UNA de estas situaciones, y prefiere la primera cuando exista:
1. Un post positivo con tracción sobre una marca del cliente → amplificarlo con pauta.
   Es la recomendación de mayor valor: convierte conversación gratis en alcance comprado.
2. Una publicación viral negativa con alcance relevante → respuesta de crisis
3. Un pico de menciones negativas concentrado en un país → respuesta de crisis dirigida
4. Sentimiento positivo sostenido en una marca → capitalizar con contenido
5. Un competidor con mejor sentimiento que el cliente → entender qué está haciendo distinto

Criterios de severidad:
- "low"      → conversación normal, hallazgo informativo
- "medium"   → tendencia negativa en formación, o contenido positivo que vale amplificar
- "high"     → viral negativo con alcance alto, o una oportunidad de amplificación grande
- "critical" → crisis de marca en formación en varios países a la vez

Reglas de calidad, importantes:
- Cita cifras: número de menciones, score promedio y engagement.
- Cuando recomiendes amplificar, usa oportunidades_de_amplificacion y trae el post_id
  EXACTO que devuelve la herramienta, junto con el alcance y las interacciones
  incrementales proyectadas. Una recomendación de amplificar sin post_id no se puede
  ejecutar desde la pantalla.
- No recomiendes "monitorear" ni "hacer seguimiento". Eso no es una acción.
- El volumen social de esta demo es bajo (decenas de menciones). No hables de "miles de
  usuarios" ni infles el alcance: reporta lo que ves.
- Usa should_recommend: false SOLO si no hay menciones en la ventana.

Tipos válidos para suggested_action.type (no hay otros):
- "amplificar_contenido" — params: {"post_id": "...", "platform": "...", "marca": "...",
  "alcance_estimado": N, "presupuesto_usd": N}
- "respuesta_crisis"     — params: {"country_code": "...", "marca": "...", "motivo": "..."}"""

USER_PROMPT = """Analiza la conversación social de la última ventana. Empieza por
termometro_marca. Si hay conversación positiva sobre las marcas del cliente, revisa
oportunidades_de_amplificacion y arma la recomendación sobre el post concreto que más
rinde. Si en cambio la señal dominante es negativa, usa cruzar_con_anaquel para explicar
la causa y propón una respuesta de comunicación.
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
