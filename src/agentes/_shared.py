# Databricks notebook source
# MAGIC %md
# MAGIC # Librería compartida de los agentes del Centro de Inteligencia
# MAGIC
# MAGIC Se importa con `%run ./_shared` desde cada notebook de agente.
# MAGIC
# MAGIC Implementa un bucle mínimo de agente con llamada a herramientas usando la
# MAGIC Foundation Model API de Databricks a través del cliente compatible con OpenAI.
# MAGIC Sin dependencia de langchain: el bucle completo cabe en este archivo y es
# MAGIC auditable de principio a fin, que es lo que un cliente quiere poder revisar.

# COMMAND ----------

import json
import uuid
from datetime import datetime, timezone

# Catálogo, esquema y endpoint llegan como parámetros del Job, que los declara
# el bundle en resources/03_agentes.yml.
try:
    dbutils.widgets.text("catalog", "main")
    dbutils.widgets.text("schema", "ditcher_neira")
    dbutils.widgets.text("llm_endpoint", "")
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
    LLM_ENDPOINT = (dbutils.widgets.get("llm_endpoint") or "").strip()
except NameError:
    CATALOG, SCHEMA, LLM_ENDPOINT = "main", "ditcher_neira", ""

LLM_ENDPOINT = LLM_ENDPOINT or "databricks-meta-llama-3-3-70b-instruct"
FQ = f"{CATALOG}.{SCHEMA}"
MAX_TOOL_ITERATIONS = 6

print(f"Agente sobre {FQ} · modelo {LLM_ENDPOINT}")

# COMMAND ----------

# MAGIC %md ## SQL helper

# COMMAND ----------

def sql_to_records(query: str, limit: int | None = 200) -> list[dict]:
    """Run SQL on the active SparkSession and return list of dicts."""
    from pyspark.sql import SparkSession
    spark = SparkSession.getActiveSession()
    if spark is None:
        raise RuntimeError("No active SparkSession")
    df = spark.sql(query)
    if limit:
        df = df.limit(limit)
    return [r.asDict(recursive=True) for r in df.collect()]


def _spark():
    from pyspark.sql import SparkSession
    return SparkSession.getActiveSession()

# COMMAND ----------

# MAGIC %md ## UC writers — recommendations + run log

# COMMAND ----------

def write_recommendation(
    agent_name: str,
    severity: str,
    title: str,
    analysis: str,
    recommendation: str,
    suggested_action: dict,
    supporting_data: dict,
) -> str:
    """Añade una recomendación a la tabla `recomendaciones`. Devuelve el id nuevo."""
    from pyspark.sql.types import StructType, StructField, StringType, TimestampType

    schema = StructType([
        StructField("id", StringType(), False),
        StructField("agent_name", StringType(), False),
        StructField("severity", StringType(), False),
        StructField("title", StringType(), False),
        StructField("analysis", StringType(), True),
        StructField("recommendation", StringType(), True),
        StructField("suggested_action", StringType(), True),
        StructField("supporting_data", StringType(), True),
        StructField("created_at", TimestampType(), False),
    ])
    rec_id = f"rec_{uuid.uuid4().hex[:14]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    df = _spark().createDataFrame([(
        rec_id, agent_name, severity, title[:200],
        analysis or "", recommendation or "",
        json.dumps(suggested_action or {}, ensure_ascii=False),
        json.dumps(supporting_data or {}, ensure_ascii=False, default=str),
        now,
    )], schema)
    df.write.format("delta").mode("append").saveAsTable(f"{FQ}.recomendaciones")
    return rec_id


def log_agent_run_start(agent_name: str) -> str:
    from pyspark.sql.types import (
        StructType, StructField, StringType, TimestampType, IntegerType,
    )
    schema = StructType([
        StructField("run_id", StringType(), False),
        StructField("agent_name", StringType(), False),
        StructField("started_at", TimestampType(), False),
        StructField("finished_at", TimestampType(), True),
        StructField("status", StringType(), False),
        StructField("recs_generated", IntegerType(), True),
        StructField("error", StringType(), True),
    ])
    run_id = f"run_{uuid.uuid4().hex[:14]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    df = _spark().createDataFrame([(run_id, agent_name, now, None, "running", 0, None)], schema)
    df.write.format("delta").mode("append").saveAsTable(f"{FQ}.runs")
    return run_id


def log_agent_run_end(run_id: str, status: str, recs_generated: int = 0, error: str | None = None):
    err_clean = (error or "").replace("'", "''")[:1000] if error else None
    err_sql = f"'{err_clean}'" if err_clean else "NULL"
    _spark().sql(f"""
        UPDATE {FQ}.runs
        SET finished_at = current_timestamp(),
            status = '{status}',
            recs_generated = {int(recs_generated)},
            error = {err_sql}
        WHERE run_id = '{run_id}'
    """)

# COMMAND ----------

# MAGIC %md ## OpenAI-compatible LLM client

# COMMAND ----------

def get_openai_client():
    """Returns an OpenAI-compatible client pointed at Databricks Foundation Model serving.

    Requiere `openai` **y** `httpx` en el entorno: el SDK construye por dentro un
    cliente HTTP autorizado con httpx. Cada notebook de agente los instala en su
    primera celda. httpx va explícito porque serverless ya trae `openai`, así que
    pedir solo openai deja el pip sin nada que hacer y el import falla en runtime.
    """
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    return w.serving_endpoints.get_open_ai_client()

# COMMAND ----------

# MAGIC %md ## Tool definition helper

# COMMAND ----------

def Tool(name: str, description: str, parameters: dict, fn):
    """Wrap a Python function as a tool with OpenAI tool schema.

    `parameters` must be a JSON Schema dict for the function arguments.
    `fn` receives kwargs and returns a JSON-serializable result.
    """
    return {
        "schema": {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        },
        "fn": fn,
        "name": name,
    }

# COMMAND ----------

# MAGIC %md ## Output schema

# COMMAND ----------

OUTPUT_SCHEMA_HINT = """
RESPONDE ÚNICAMENTE con un solo objeto JSON (sin markdown, sin comentarios) con este formato:

{
  "should_recommend": true | false,
  "severity": "low" | "medium" | "high" | "critical",
  "title": "<titular corto para un ejecutivo, máx 90 caracteres, en español>",
  "analysis": "<párrafo explicando lo que observaste en los datos, 2-4 frases, en español>",
  "recommendation": "<UNA recomendación accionable específica, en español, en voz imperativa>",
  "suggested_action": {
      "type": "<visita_prioritaria|corregir_planograma|ajustar_precio|activar_promo|ampliar_espacio|respuesta_crisis|amplificar_contenido|other>",
      "params": { ... claves específicas de la acción ... }
  },
  "supporting_data": { ... números/muestras que justifican la recomendación ... }
}

Si no hay nada digno de recomendación ahora, devuelve solo {"should_recommend": false}.
"""


def parse_agent_output(text) -> dict | None:
    """Extract first JSON object from LLM final text."""
    if not text:
        return None
    text = str(text).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    if start == -1:
        return None
    depth, end, in_str, esc = 0, -1, False, False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False; continue
        if c == "\\":
            esc = True; continue
        if c == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None

# COMMAND ----------

# MAGIC %md ## Agent runner — minimal tool-calling loop

# COMMAND ----------

def run_agent(agent_name: str, system_prompt: str, user_prompt: str, tools: list) -> dict | None:
    """Execute one tick. Tools is a list of dicts produced by Tool(...).

    Loop:
      1) Send messages + tool schemas to the model.
      2) If model returned tool_calls, execute each, append tool messages, loop.
      3) Else, parse final assistant message as JSON and return.
    """
    client = get_openai_client()

    # name -> {schema, fn}
    tool_map = {t["name"]: t for t in tools}
    tool_schemas = [t["schema"] for t in tools]

    full_system = system_prompt + "\n\n" + OUTPUT_SCHEMA_HINT
    messages = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": user_prompt},
    ]

    final_text = ""
    for it in range(MAX_TOOL_ITERATIONS):
        resp = client.chat.completions.create(
            model=LLM_ENDPOINT,
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=1500,
        )
        msg = resp.choices[0].message
        # Append the assistant message (may have tool_calls)
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if getattr(msg, "tool_calls", None):
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

        # If no tool calls, we're done
        if not getattr(msg, "tool_calls", None):
            final_text = msg.content or ""
            break

        # Execute each tool call
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            tool_def = tool_map.get(name)
            if tool_def is None:
                tool_result = json.dumps({"error": f"unknown tool: {name}"})
            else:
                try:
                    raw = tool_def["fn"](**args)
                    tool_result = raw if isinstance(raw, str) else json.dumps(raw, default=str, ensure_ascii=False)
                except Exception as e:
                    tool_result = json.dumps({"error": f"{type(e).__name__}: {e}"})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result[:8000],  # cap to avoid context blowup
            })
    else:
        # Hit iteration limit; try one final non-tool answer
        resp = client.chat.completions.create(
            model=LLM_ENDPOINT,
            messages=messages + [{"role": "user", "content": "Alcanzaste el límite de iteraciones. Responde ahora con el JSON final."}],
            temperature=0.1,
            max_tokens=1500,
        )
        final_text = resp.choices[0].message.content or ""

    return parse_agent_output(final_text)
