# Databricks notebook source
# MAGIC %md
# MAGIC # Agente — Red de Abastecimiento
# MAGIC
# MAGIC Corre como Job agendado cada 2 minutos mientras la demo está encendida.
# MAGIC
# MAGIC **Misión:** cerrar quiebres de anaquel moviendo producto que ya está en la calle.
# MAGIC Cuando una tienda se queda sin un SKU, la respuesta por defecto es esperar el
# MAGIC siguiente despacho de fábrica. Pero muchas veces el producto está a doce
# MAGIC kilómetros, sobrando en el anaquel de otra tienda de la misma plaza. Este agente
# MAGIC cruza las dos puntas sobre la malla de distribución y propone el traslado.
# MAGIC
# MAGIC **Dos mitades, a propósito.** El emparejamiento y la economía son SQL
# MAGIC determinista: qué tienda, con cuál, cuántos kilómetros, cuánta plata. Eso no
# MAGIC puede depender de un modelo. El LLM entra después, sobre los candidatos ya
# MAGIC calculados, para decidir cuál merece subir a la cola de aprobación y explicarlo
# MAGIC en el lenguaje del que va a firmar.
# MAGIC
# MAGIC Ningún traslado se ejecuta solo: la fila nace en `propuesto` y un humano la mueve.

# COMMAND ----------

# MAGIC %pip install --quiet openai httpx
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./_shared

# COMMAND ----------

AGENT_NAME = "red_abastecimiento"

# Economía del traslado. Están acá arriba y no enterrados en el SQL porque son
# justo los supuestos que un cliente va a querer discutir en la demo.
UNIDADES_POR_CAJA = 24      # se mueve por caja cerrada, no por unidad suelta
MAX_CAJAS = 4               # tope por traslado: el mercaderista va en carro, no en camión
MARGEN_BRUTO = 0.32         # margen del fabricante sobre PVP
COSTO_FIJO_USD = 6.0        # manipuleo y papeleo de la transferencia
COSTO_POR_KM_USD = 0.45     # el mercaderista ya está en ruta; esto es el incremental
RADIO_MAX_KM = 60.0         # más lejos que esto ya no es la misma plaza
VENTANA_MIN = 45            # ventana de lectura de anaquel

# Una propuesta vale lo que vale la lectura de anaquel que la originó. Pasada esa
# ventana el quiebre puede estar resuelto y el sobrestock vendido, así que la
# propuesta vence sola. Sin esto el agente apila miles de filas muertas y la cola
# deja de ser una cola: en una corrida de una noche llegó a 5.600.
VIGENCIA_MIN = 20
COLA_MAXIMA = 15            # cuántas propuestas abiertas tiene sentido mirar a la vez

# COMMAND ----------

# MAGIC %md ## Emparejamiento sobre la malla de distribución
# MAGIC
# MAGIC Una tienda es **destino** si su última lectura del SKU dice que no hay producto.
# MAGIC Es **origen** si tiene el SKU en anaquel con más caras que la mediana de la red
# MAGIC para ese SKU: ese excedente es lo que se puede ceder sin abrir un hueco nuevo.
# MAGIC
# MAGIC A cada destino se le asigna el origen más cercano por distancia real
# MAGIC (haversine sobre las coordenadas del PDV), y cada origen cede una sola vez por
# MAGIC SKU para no prometer dos veces la misma caja.

# COMMAND ----------

SQL_CANDIDATOS = f"""
WITH lectura AS (
  SELECT v.store_id, v.sku, v.categoria, v.marca,
         MAX_BY(v.en_stock,   v.visit_ts) AS en_stock,
         MAX_BY(v.facings,    v.visit_ts) AS facings,
         MAX_BY(v.precio_usd, v.visit_ts) AS precio_usd,
         MAX(v.visit_ts)                  AS ultima_lectura
  FROM {FQ}.visitas v
  WHERE v.es_cliente
    AND v.visit_ts >= current_timestamp() - INTERVAL {VENTANA_MIN} MINUTES
  GROUP BY v.store_id, v.sku, v.categoria, v.marca
),
norma AS (
  -- La mediana de caras del SKU en las tiendas donde sí hay producto: la vara
  -- contra la que se mide si una tienda tiene de más.
  SELECT sku,
         PERCENTILE_APPROX(facings, 0.5) AS facings_tipico,
         AVG(precio_usd)                 AS precio_ref
  FROM lectura
  WHERE en_stock
  GROUP BY sku
),
quiebre AS (
  SELECT l.sku, l.categoria, l.marca, l.ultima_lectura,
         t.store_id, t.nombre, t.ciudad, t.country_code, t.latitude, t.longitude
  FROM lectura l
  JOIN {FQ}.tiendas t ON t.store_id = l.store_id
  WHERE NOT l.en_stock
),
excedente AS (
  SELECT l.sku, n.precio_ref,
         (l.facings - n.facings_tipico) AS sobrante_facings,
         t.store_id, t.nombre, t.ciudad, t.country_code, t.latitude, t.longitude
  FROM lectura l
  JOIN norma n           ON n.sku = l.sku
  JOIN {FQ}.tiendas t    ON t.store_id = l.store_id
  WHERE l.en_stock AND l.facings > n.facings_tipico
),
par AS (
  SELECT q.sku, q.categoria, q.marca, q.country_code, q.ultima_lectura,
         q.store_id AS destino_id, q.nombre AS destino_nombre,
         q.ciudad   AS destino_ciudad,
         q.latitude AS destino_lat, q.longitude AS destino_lon,
         e.store_id AS origen_id, e.nombre AS origen_nombre,
         e.ciudad   AS origen_ciudad,
         e.latitude AS origen_lat, e.longitude AS origen_lon,
         e.sobrante_facings, e.precio_ref,
         6371.0 * ACOS(LEAST(1.0, GREATEST(-1.0,
             COS(RADIANS(q.latitude)) * COS(RADIANS(e.latitude))
               * COS(RADIANS(e.longitude) - RADIANS(q.longitude))
           + SIN(RADIANS(q.latitude)) * SIN(RADIANS(e.latitude))
         ))) AS km
  FROM quiebre q
  JOIN excedente e
    ON e.sku          = q.sku
   AND e.country_code = q.country_code
   AND e.store_id    <> q.store_id
),
economia AS (
  SELECT p.*,
         LEAST(p.sobrante_facings, {MAX_CAJAS}) * {UNIDADES_POR_CAJA}        AS unidades,
         LEAST(p.sobrante_facings, {MAX_CAJAS}) * {UNIDADES_POR_CAJA}
           * p.precio_ref                                                    AS venta_usd,
         {COSTO_FIJO_USD} + p.km * {COSTO_POR_KM_USD}                        AS costo_usd
  FROM par p
  WHERE p.km <= {RADIO_MAX_KM}
),
puntuado AS (
  SELECT e.*,
         e.venta_usd * {MARGEN_BRUTO} - e.costo_usd AS ganancia_usd
  FROM economia e
),
-- Un destino se atiende desde el origen más cercano...
mejor_origen AS (
  SELECT *, ROW_NUMBER() OVER (
             PARTITION BY destino_id, sku ORDER BY km ASC
           ) AS rn
  FROM puntuado
  WHERE ganancia_usd > 0
),
-- ...y cada origen cede su excedente una sola vez por SKU.
unico AS (
  SELECT *, ROW_NUMBER() OVER (
             PARTITION BY origen_id, sku ORDER BY ganancia_usd DESC
           ) AS rn2
  FROM mejor_origen
  WHERE rn = 1
),
-- Un mismo SKU con quiebre en media red generaba una cola donde siete de
-- quince tarjetas eran el mismo producto. Se conservan los dos traslados que
-- más rinden por SKU: la cola se lee y sigue mostrando lo que de verdad pesa.
variado AS (
  SELECT *, ROW_NUMBER() OVER (
             PARTITION BY sku ORDER BY ganancia_usd DESC
           ) AS rn3
  FROM unico
  WHERE rn2 = 1
)
SELECT u.sku, pr.nombre AS producto, u.marca, u.categoria, u.country_code,
       u.origen_id, u.origen_nombre, u.origen_ciudad, u.origen_lat, u.origen_lon,
       u.destino_id, u.destino_nombre, u.destino_ciudad, u.destino_lat, u.destino_lon,
       ROUND(u.km, 1)           AS distancia_km,
       CAST(u.unidades AS INT)  AS unidades,
       ROUND(u.venta_usd, 2)    AS venta_recuperada_usd,
       ROUND(u.costo_usd, 2)    AS costo_logistico_usd,
       ROUND(u.ganancia_usd, 2) AS ganancia_neta_usd
FROM variado u
LEFT JOIN {FQ}.productos pr ON pr.sku = u.sku
WHERE u.rn3 <= 2
ORDER BY ganancia_neta_usd DESC
LIMIT 40
"""

# COMMAND ----------

import uuid as _uuid
from datetime import datetime as _dt, timezone as _tz


def _vencer_propuestas_viejas() -> int:
    """Cierra las propuestas cuya lectura de anaquel ya caducó.

    Vencen solas y no se descartan: 'descartado' es la palabra de un humano que
    miró el traslado y dijo que no. Mezclarlas arruinaría el marcador del agente.
    """
    spark = _spark()
    antes = spark.sql(
        f"SELECT COUNT(*) AS n FROM {FQ}.traslados WHERE estado = 'propuesto'"
    ).collect()[0]["n"]
    spark.sql(f"""
        UPDATE {FQ}.traslados
        SET estado = 'vencido', decidido_en = current_timestamp()
        WHERE estado = 'propuesto'
          AND propuesto_en < current_timestamp() - INTERVAL {VIGENCIA_MIN} MINUTES
    """)
    despues = spark.sql(
        f"SELECT COUNT(*) AS n FROM {FQ}.traslados WHERE estado = 'propuesto'"
    ).collect()[0]["n"]
    return int(antes - despues)


def _proponer_traslados(maximo: int = 12) -> list[dict]:
    """Calcula candidatos y deja en `traslados` los que aún no están propuestos.

    Devuelve las filas efectivamente escritas. Es idempotente por par
    (sku, origen, destino) mientras la propuesta siga abierta: el agente corre
    cada dos minutos y no puede ir apilando la misma sugerencia.
    """
    vencidas = _vencer_propuestas_viejas()
    if vencidas:
        print(f"⏳ {vencidas} propuestas vencidas por lectura caduca")

    candidatos = sql_to_records(SQL_CANDIDATOS, limit=40)
    if not candidatos:
        return []

    abiertas = sql_to_records(
        f"SELECT sku, origen_id, destino_id FROM {FQ}.traslados "
        f"WHERE estado = 'propuesto'",
        limit=500,
    )
    abiertos = {(r["sku"], r["origen_id"], r["destino_id"]) for r in abiertas}

    # La cola es para decidir, no para archivar: si ya hay quince traslados
    # esperando a alguien, sumar más no ayuda a nadie.
    cupo = max(0, COLA_MAXIMA - len(abiertas))
    nuevos = [
        c for c in candidatos
        if (c["sku"], c["origen_id"], c["destino_id"]) not in abiertos
    ][: min(max(1, int(maximo)), cupo)]
    if not nuevos:
        return []

    from decimal import Decimal
    from pyspark.sql.types import (
        DoubleType, IntegerType, StringType, StructField, StructType, TimestampType,
    )
    from pyspark.sql.types import DecimalType

    schema = StructType([
        StructField("traslado_id", StringType(), False),
        StructField("sku", StringType(), False),
        StructField("producto", StringType(), True),
        StructField("marca", StringType(), True),
        StructField("categoria", StringType(), True),
        StructField("country_code", StringType(), True),
        StructField("origen_id", StringType(), False),
        StructField("origen_nombre", StringType(), True),
        StructField("origen_ciudad", StringType(), True),
        StructField("origen_lat", DoubleType(), True),
        StructField("origen_lon", DoubleType(), True),
        StructField("destino_id", StringType(), False),
        StructField("destino_nombre", StringType(), True),
        StructField("destino_ciudad", StringType(), True),
        StructField("destino_lat", DoubleType(), True),
        StructField("destino_lon", DoubleType(), True),
        StructField("distancia_km", DoubleType(), False),
        StructField("unidades", IntegerType(), False),
        StructField("venta_recuperada_usd", DecimalType(12, 2), False),
        StructField("costo_logistico_usd", DecimalType(12, 2), False),
        StructField("ganancia_neta_usd", DecimalType(12, 2), False),
        StructField("estado", StringType(), False),
        StructField("decidido_por", StringType(), True),
        StructField("decidido_en", TimestampType(), True),
        StructField("propuesto_en", TimestampType(), False),
    ])

    ahora = _dt.now(_tz.utc).replace(tzinfo=None)
    filas = []
    for c in nuevos:
        tid = f"tr_{_uuid.uuid4().hex[:12]}"
        c["traslado_id"] = tid
        filas.append((
            tid, c["sku"], c.get("producto"), c.get("marca"), c.get("categoria"),
            c.get("country_code"),
            c["origen_id"], c.get("origen_nombre"), c.get("origen_ciudad"),
            float(c["origen_lat"]), float(c["origen_lon"]),
            c["destino_id"], c.get("destino_nombre"), c.get("destino_ciudad"),
            float(c["destino_lat"]), float(c["destino_lon"]),
            float(c["distancia_km"]), int(c["unidades"]),
            Decimal(str(c["venta_recuperada_usd"])),
            Decimal(str(c["costo_logistico_usd"])),
            Decimal(str(c["ganancia_neta_usd"])),
            "propuesto", None, None, ahora,
        ))

    _spark().createDataFrame(filas, schema) \
        .write.format("delta").mode("append").saveAsTable(f"{FQ}.traslados")
    return nuevos

# COMMAND ----------

# MAGIC %md ## Herramientas del agente

# COMMAND ----------

def _malla_de_distribucion(maximo: int = 12) -> str:
    """Calcula y persiste los traslados candidatos, y se los muestra al modelo."""
    nuevos = _proponer_traslados(maximo)
    if not nuevos:
        abiertos = sql_to_records(f"""
            SELECT traslado_id, sku, producto, origen_nombre, destino_nombre,
                   distancia_km, unidades, ganancia_neta_usd
            FROM {FQ}.traslados
            WHERE estado = 'propuesto'
            ORDER BY ganancia_neta_usd DESC
            LIMIT 10
        """, limit=10)
        return json.dumps({
            "traslados_nuevos": [],
            "ya_en_cola": abiertos,
            "nota": "no hay pares nuevos que rindan o la cola está llena; "
                    "argumenta sobre lo que ya está esperando decisión",
        }, default=str)
    return json.dumps({"traslados_nuevos": nuevos}, default=str)


def _mapa_de_quiebres(limit: int = 12) -> str:
    """Dónde se está perdiendo venta por falta de producto, por plaza y cadena."""
    limit = max(1, min(25, int(limit)))
    rows = sql_to_records(f"""
        SELECT t.country_code, t.ciudad, t.cadena,
               COUNT(*)                                          AS observaciones,
               SUM(CASE WHEN NOT v.en_stock THEN 1 ELSE 0 END)    AS quiebres,
               ROUND(AVG(CASE WHEN v.en_stock THEN 100.0 ELSE 0.0 END), 1)
                                                                  AS disponibilidad_pct,
               COUNT(DISTINCT CASE WHEN NOT v.en_stock THEN v.store_id END)
                                                                  AS pdv_afectados
        FROM {FQ}.visitas v
        JOIN {FQ}.tiendas t USING (store_id)
        WHERE v.es_cliente
          AND v.visit_ts >= current_timestamp() - INTERVAL {VENTANA_MIN} MINUTES
        GROUP BY t.country_code, t.ciudad, t.cadena
        HAVING COUNT(*) >= 6
        ORDER BY disponibilidad_pct ASC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)


def _cola_de_traslados() -> str:
    """Qué hay ya propuesto y qué aprobó el humano: evita repetir la sugerencia."""
    rows = sql_to_records(f"""
        SELECT estado,
               COUNT(*)                        AS traslados,
               ROUND(SUM(ganancia_neta_usd), 2) AS ganancia_usd,
               ROUND(AVG(distancia_km), 1)      AS km_promedio
        FROM {FQ}.traslados
        GROUP BY estado
    """, limit=10)
    return json.dumps(rows, default=str)


def _cobertura_por_sku(limit: int = 10) -> str:
    """Qué SKU del cliente está peor repartido en la red: muchos quiebres y mucho sobrante."""
    limit = max(1, min(20, int(limit)))
    rows = sql_to_records(f"""
        WITH lectura AS (
          SELECT store_id, sku, MAX_BY(en_stock, visit_ts) AS en_stock,
                 MAX_BY(facings, visit_ts) AS facings
          FROM {FQ}.visitas
          WHERE es_cliente
            AND visit_ts >= current_timestamp() - INTERVAL {VENTANA_MIN} MINUTES
          GROUP BY store_id, sku
        )
        SELECT l.sku, p.nombre AS producto, p.marca, p.categoria,
               COUNT(*)                                            AS pdv_medidos,
               SUM(CASE WHEN NOT l.en_stock THEN 1 ELSE 0 END)      AS pdv_en_quiebre,
               ROUND(AVG(CASE WHEN l.en_stock THEN l.facings END), 1) AS caras_promedio,
               MAX(l.facings)                                       AS caras_maximo
        FROM lectura l
        LEFT JOIN {FQ}.productos p ON p.sku = l.sku
        GROUP BY l.sku, p.nombre, p.marca, p.categoria
        HAVING SUM(CASE WHEN NOT l.en_stock THEN 1 ELSE 0 END) > 0
        ORDER BY pdv_en_quiebre DESC
        LIMIT {limit}
    """, limit=limit)
    return json.dumps(rows, default=str)

# COMMAND ----------

TOOLS = [
    Tool(
        name="malla_de_distribucion",
        description="Calcula los traslados que rinden entre tiendas de la misma plaza: "
                    "empareja cada tienda en quiebre con la tienda con sobrestock más "
                    "cercana, y devuelve distancia, unidades, venta recuperada, costo "
                    "logístico y ganancia neta. Los deja en la cola de aprobación. "
                    "Empieza siempre por aquí.",
        parameters={
            "type": "object",
            "properties": {
                "maximo": {"type": "integer", "description": "Cuántos proponer (1-12)", "default": 12}
            },
            "required": [],
        },
        fn=_malla_de_distribucion,
    ),
    Tool(
        name="mapa_de_quiebres",
        description="Dónde se concentran los quiebres de anaquel del cliente, por país, "
                    "ciudad y cadena. Sirve para decir si el problema es puntual o de plaza.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 12}},
            "required": [],
        },
        fn=_mapa_de_quiebres,
    ),
    Tool(
        name="cobertura_por_sku",
        description="Qué SKU está peor repartido: en cuántos PDV falta y cuántas caras "
                    "tiene donde sí está. Un SKU con muchos quiebres y mucho sobrante es "
                    "un problema de distribución, no de producción.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
            "required": [],
        },
        fn=_cobertura_por_sku,
    ),
    Tool(
        name="cola_de_traslados",
        description="Estado de la cola: cuántos traslados hay propuestos, aprobados o "
                    "descartados y cuánta plata representan.",
        parameters={"type": "object", "properties": {}, "required": []},
        fn=_cola_de_traslados,
    ),
]

# COMMAND ----------

SYSTEM_PROMPT = """Eres el agente "Red de Abastecimiento" de dichter & neira, la firma de
inteligencia de mercados que mide el punto de venta para marcas de consumo masivo en
Latinoamérica.

Tu trabajo es distinto al del resto de los agentes: ellos reportan lo que está mal, tú
propones mover producto. Cuando una tienda se queda sin un SKU, la reacción normal es
esperar el próximo despacho de fábrica. Tú buscas primero si ese mismo producto está
sobrando en otra tienda de la misma plaza, y propones el traslado.

Tienes 4 herramientas. Llama SIEMPRE a malla_de_distribucion primero: es la que calcula
los pares y los deja en la cola de aprobación. Después usa 1 o 2 más para poner el
traslado en contexto. Nunca llames dos veces a la misma herramienta con los mismos
parámetros.

Redacta la recomendación sobre EL MEJOR traslado de la lista — el de mayor ganancia neta.
Los demás quedan en la cola y el humano los ve en pantalla; tú argumentas uno.

Criterios de severidad:
- "low"      → ganancia neta menor a 30 USD: se puede esperar al despacho
- "medium"   → ganancia neta entre 30 y 80 USD
- "high"     → ganancia neta sobre 80 USD, o un SKU en quiebre en varios PDV de la plaza
- "critical" → quiebre extendido de un SKU en una cadena entera con producto disponible cerca

Reglas de calidad, importantes:
- Nombra las dos tiendas por su nombre y ciudad, no por su id.
- Cita SIEMPRE los cuatro números del traslado: kilómetros, unidades, ganancia neta en USD
  y costo logístico. El que aprueba tiene que poder discutir la cuenta.
- Di explícitamente que el traslado NO se ejecuta hasta que alguien lo apruebe.
- Si el mismo SKU aparece en quiebre en varias tiendas de la plaza, dilo: eso ya no es un
  traslado, es una señal de que el despacho a esa plaza quedó corto.
- Usa should_recommend: false solo si no hay ningún traslado con ganancia neta positiva.

Tipo válido para suggested_action.type:
- "traslado_mercaderia" — params: {"traslado_id": "...", "sku": "...", "origen": "<nombre>",
  "destino": "<nombre>", "unidades": N, "distancia_km": X, "ganancia_neta_usd": Y}"""

USER_PROMPT = """Revisa la red de puntos de venta y busca producto en quiebre que se pueda
cubrir moviendo mercadería desde una tienda cercana con sobrestock. Empieza por
malla_de_distribucion. Arma la recomendación sobre el traslado de mayor ganancia neta.
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
