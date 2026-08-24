#!/usr/bin/env python3
"""Crea (o actualiza) el Genie Space real del Centro de Inteligencia.

Genie no adivina el negocio a partir de los nombres de las columnas. Sin
instrucciones responde plausible y equivocado: promedia disponibilidad sobre
toda la competencia cuando la pregunta era sobre nuestras marcas, o filtra por
'Bebidas' cuando la categoría se llama 'Bebidas Calientes'. Este archivo carga
las tablas y, sobre todo, el contexto: qué mide cada tabla, cómo se unen y qué
valores literales existen de verdad.

Es idempotente. Si ya hay una sala con este título la actualiza en su lugar, así
que conserva su id y no rompe los enlaces que alguien haya guardado.

Variables de entorno:
  PROFILE          perfil del CLI
  WAREHOUSE_ID     warehouse que va a ejecutar el SQL de la sala
  CATALOG, SCHEMA  dónde viven las tablas
  CLIENTE          fabricante que contrata el estudio
  GENIE_TITLE      título de la sala
  GENIE_ID_FILE    archivo donde escribir el space_id
  PARENT_PATH      carpeta del workspace donde registrarla (opcional)
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

PROFILE = os.environ.get("PROFILE", "DEFAULT")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")
CATALOG = os.environ.get("CATALOG", "main")
SCHEMA = os.environ.get("SCHEMA", "ditcher_neira")
CLIENTE = os.environ.get("CLIENTE", "Nestlé")
TITLE = os.environ.get("GENIE_TITLE", "dichter & neira · Centro de Inteligencia")
ID_FILE = os.environ.get("GENIE_ID_FILE", "")
PARENT_PATH = os.environ.get("PARENT_PATH", "")

FQ = f"{CATALOG}.{SCHEMA}"

# Solo las tablas que alguien va a querer preguntar. Las de bitácora interna
# (runs, action_log) se dejan afuera a propósito: agregarlas no suma respuestas y
# sí aumenta la chance de que Genie se vaya por una tabla equivocada.
TABLAS = [
    "visitas",
    "ejecucion_realtime",
    "precios_competencia",
    "social_posts",
    "tiendas",
    "productos",
    "paises",
    "fabricantes",
    "metas_categoria",
    "recomendaciones",
    "traslados",
    "acciones_campo",
    "campanas",
]

INSTRUCCIONES = f"""## CONTEXTO DE NEGOCIO
Este espacio analiza la medición continua de ejecución en punto de venta que
dichter & neira realiza para {CLIENTE} en 10 mercados de Latinoamérica. Un
auditor visita un PDV, fotografía el anaquel y el reconocimiento de imagen
devuelve una observación por SKU: si estaba en stock, cuántos facings tenía, si
el planograma se respetó y a qué precio se exhibía.

{CLIENTE} es el fabricante que contrata el estudio. TODO el resto del catálogo es
competencia. Esta distinción es la más importante del modelo: cuando alguien
pregunta por "nuestra" disponibilidad, ejecución, share of shelf o precio, se
refiere únicamente a {CLIENTE}, y hay que filtrar por es_cliente = true. Sin ese
filtro el número sale promediado con la competencia y es incorrecto.

Los importes están normalizados a USD en las columnas precio_usd; precio_local
está en la moneda del país y no es comparable entre mercados.

## MODELO DE DATOS Y JOINS
- visitas es la tabla central de hechos: una fila por SKU observado en una
  visita. Ya viene desnormalizada con canal, cadena, ciudad, country_code,
  marca, fabricante, categoria y es_cliente, así que la mayoría de las preguntas
  se responden sin ningún join.
  - Para atributos del PDV que no están ahí (latitude, longitude, formato,
    mercaderista, visitas_mes_meta): unir con tiendas ON visitas.store_id =
    tiendas.store_id
  - Para atributos del producto (subcategoria, presentacion, precio_sugerido_usd):
    unir con productos ON visitas.sku = productos.sku
  - Para el nombre del país y su región: unir con paises ON visitas.country_code
    = paises.country_code
- ejecucion_realtime está pre-agregada por minuto, país y categoría. Usarla para
  preguntas de tendencia o de "ahora mismo": es mucho más rápida que agregar
  visitas. No tiene el corte por marca ni por PDV.
- precios_competencia es un snapshot del estado actual de precios, no una serie
  histórica: se reemplaza completa en cada actualización. indice_precio compara
  el precio del SKU contra el promedio de su categoría en ese mismo anaquel;
  100 = está en el promedio, 110 = está 10% más caro.
- metas_categoria tiene el objetivo por categoría. Unir por categoria para
  responder "¿estamos cumpliendo la meta?".
- social_posts, recomendaciones, traslados, acciones_campo y campanas son
  independientes: no se unen con visitas.

## CÓMO SE CALCULAN LAS MÉTRICAS DEL NEGOCIO
Estas definiciones no son negociables, son las que usa el tablero:
- Disponibilidad en anaquel (%):
  AVG(CAST(en_stock AS INT)) * 100 WHERE es_cliente = true
- Ejecución perfecta (%): AVG(CAST(ejecucion_perfecta AS INT)) * 100
  WHERE es_cliente = true. Un SKU ejecuta perfecto cuando está en stock, el
  planograma se respeta y tiene los facings acordados.
- Share of shelf (%): facings de {CLIENTE} sobre facings totales del anaquel:
  SUM(CASE WHEN es_cliente THEN facings ELSE 0 END) / SUM(facings) * 100.
  Ojo: acá NO va un WHERE es_cliente, porque el denominador necesita todo el
  anaquel. Es el error más común.
- Quiebre de stock: en_stock = false AND es_cliente = true. Contar filas, no
  promediar.
- Cumplimiento de meta: métrica observada / meta de metas_categoria * 100.

## VALORES EXACTOS PARA FILTROS
Usar siempre estos literales; no existen otros.
- categoria: 'Bebidas Calientes', 'Lácteos', 'Culinarios',
  'Confitería y Snacks', 'Bebidas No Alcohólicas'
- canal: 'Moderno', 'Tradicional'
- formato (canal moderno): 'Hipermercado', 'Supermercado', 'Club de precio',
  'Conveniencia'
- country_code: 'PA' Panamá, 'GT' Guatemala, 'CR' Costa Rica, 'HN' Honduras,
  'SV' El Salvador, 'NI' Nicaragua, 'DO' República Dominicana, 'CO' Colombia,
  'EC' Ecuador, 'PE' Perú
- fabricante: '{CLIENTE}' es el cliente. Competencia: 'Unilever', 'P&G',
  'Coca-Cola', 'PepsiCo', 'Colgate-Palmolive', 'Alpina', 'Dos Pinos', 'Gloria',
  'Pozuelo', 'Grupo Bimbo'
- sentiment (social_posts): 'positivo', 'neutral', 'negativo'
- severity (recomendaciones): 'high', 'medium', 'low'
- estado (traslados): 'propuesto', 'aprobado', 'rechazado'

## CONVENCIONES DE RESPUESTA
- Redondear los porcentajes a un decimal.
- Cuando la pregunta no fija una ventana de tiempo, usar los últimos 60 minutos
  de visit_ts: la operación es en vivo y el histórico completo diluye lo que está
  pasando ahora.
- Al comparar contra la competencia, mostrar {CLIENTE} y el competidor en filas
  separadas, no la diferencia sola.
- Todas las cifras son sintéticas: sirven para demostrar el modelo analítico, no
  para tomar decisiones comerciales reales.
"""

# Las mismas seis preguntas que ofrece el modo demostración del app, para que la
# experiencia sea idéntica con sala real o sin ella. Van con su SQL: no es
# decoración, es la forma de fijar las definiciones del negocio. La de share of
# shelf es el mejor ejemplo — sin el SQL de referencia, Genie mete un
# `WHERE es_cliente` que arruina el denominador.
PREGUNTAS_SQL = [
    (
        "¿Cuál es la disponibilidad en anaquel por categoría?",
        f"""SELECT v.categoria,
       ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1)           AS disponibilidad_pct,
       m.meta_disponibilidad_pct                              AS meta_pct,
       COUNT(*)                                               AS observaciones
FROM {FQ}.visitas v
JOIN {FQ}.metas_categoria m ON v.categoria = m.categoria
WHERE v.es_cliente = true
  AND v.visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
GROUP BY v.categoria, m.meta_disponibilidad_pct
ORDER BY disponibilidad_pct ASC""",
    ),
    (
        "¿Qué puntos de venta tienen la peor ejecución esta hora?",
        f"""SELECT t.nombre AS punto_de_venta, t.cadena, t.ciudad, v.country_code,
       ROUND(AVG(CAST(v.ejecucion_perfecta AS INT)) * 100, 1) AS ejecucion_pct,
       COUNT(*)                                               AS skus_auditados
FROM {FQ}.visitas v
JOIN {FQ}.tiendas t ON v.store_id = t.store_id
WHERE v.es_cliente = true
  AND v.visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
GROUP BY t.nombre, t.cadena, t.ciudad, v.country_code
HAVING COUNT(*) >= 5
ORDER BY ejecucion_pct ASC
LIMIT 15""",
    ),
    (
        "¿Cuál es el share of shelf de nuestras marcas por país?",
        f"""-- El denominador es el anaquel completo, así que NO va WHERE es_cliente.
SELECT p.pais,
       ROUND(SUM(CASE WHEN v.es_cliente THEN v.facings ELSE 0 END)
             / NULLIF(SUM(v.facings), 0) * 100, 1)            AS share_of_shelf_pct,
       SUM(v.facings)                                         AS facings_anaquel
FROM {FQ}.visitas v
JOIN {FQ}.paises p ON v.country_code = p.country_code
WHERE v.visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
GROUP BY p.pais
ORDER BY share_of_shelf_pct DESC""",
    ),
    (
        "¿Qué SKUs están agotados en más puntos de venta?",
        f"""SELECT v.sku, pr.nombre AS producto, v.marca, v.categoria,
       COUNT(DISTINCT v.store_id)                             AS pdv_con_quiebre
FROM {FQ}.visitas v
JOIN {FQ}.productos pr ON v.sku = pr.sku
WHERE v.es_cliente = true
  AND v.en_stock = false
  AND v.visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
GROUP BY v.sku, pr.nombre, v.marca, v.categoria
ORDER BY pdv_con_quiebre DESC
LIMIT 15""",
    ),
    (
        "¿Cómo se compara nuestro índice de precio con la competencia por cadena?",
        f"""SELECT pc.cadena,
       ROUND(AVG(CASE WHEN pc.es_cliente THEN pc.indice_precio END), 1)     AS indice_cliente,
       ROUND(AVG(CASE WHEN NOT pc.es_cliente THEN pc.indice_precio END), 1) AS indice_competencia,
       COUNT(*)                                                             AS skus
FROM {FQ}.precios_competencia pc
GROUP BY pc.cadena
ORDER BY indice_cliente DESC""",
    ),
    (
        "¿Qué diferencia hay en ejecución entre canal moderno y tradicional?",
        f"""SELECT v.canal,
       ROUND(AVG(CAST(v.en_stock AS INT)) * 100, 1)           AS disponibilidad_pct,
       ROUND(AVG(CAST(v.ejecucion_perfecta AS INT)) * 100, 1) AS ejecucion_pct,
       COUNT(DISTINCT v.store_id)                             AS pdv,
       COUNT(*)                                               AS observaciones
FROM {FQ}.visitas v
WHERE v.es_cliente = true
  AND v.visit_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTES
GROUP BY v.canal
ORDER BY ejecucion_pct DESC""",
    ),
]


def cli(*args, entrada=None):
    return subprocess.run(
        ["databricks", *args, "-p", PROFILE],
        capture_output=True, text=True, input=entrada,
    )


def ident(texto):
    """Id estable de 32 hex, que es el formato que exige la API.

    Se deriva del contenido en vez de sortearse al azar para que una segunda
    corrida produzca los mismos ids: así actualizar la sala modifica las
    instrucciones que ya están en vez de acumular duplicados.
    """
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def serializado():
    return json.dumps({
        "version": 2,
        # Ordenadas: la API rechaza el payload si no vienen así.
        "data_sources": {
            "tables": [{"identifier": f"{FQ}.{t}"} for t in sorted(TABLAS)],
        },
        # La API espera el texto partido en líneas, no como una sola cadena.
        "instructions": {
            "text_instructions": [
                {
                    "id": ident("contexto"),
                    "content": INSTRUCCIONES.splitlines(keepends=True),
                },
            ],
            # Ordenadas por id, que es otra cosa que la API valida. Como el id
            # sale del hash de la pregunta, el orden no tiene relación con el
            # que se lee arriba; da igual, la sala las presenta por su cuenta.
            "example_question_sqls": sorted(
                (
                    {
                        "id": ident(pregunta),
                        "question": [pregunta],
                        "sql": sql.splitlines(keepends=True),
                    }
                    for pregunta, sql in PREGUNTAS_SQL
                ),
                key=lambda e: e["id"],
            ),
        },
    }, ensure_ascii=False)


def sala_existente():
    salida = cli("api", "get", "/api/2.0/genie/spaces")
    try:
        salas = json.loads(salida.stdout).get("spaces", [])
    except Exception:
        return None
    for s in salas:
        if s.get("title") == TITLE:
            return s.get("space_id")
    return None


def guardar_id(space_id):
    if ID_FILE:
        with open(ID_FILE, "w") as f:
            f.write((space_id or "") + "\n")


def main():
    if not WAREHOUSE_ID:
        print("❌ falta WAREHOUSE_ID")
        return 1

    cuerpo = {
        "title": TITLE,
        "description": (
            "Exploración en lenguaje natural de la medición de ejecución en "
            f"punto de venta de {CLIENTE} en Latinoamérica. Datos sintéticos."
        ),
        "warehouse_id": WAREHOUSE_ID,
        "serialized_space": serializado(),
    }
    if PARENT_PATH:
        cuerpo["parent_path"] = PARENT_PATH

    previo = sala_existente()
    if previo:
        # Se actualiza en lugar de recrear para conservar el id: el app lo recibe
        # como variable de entorno y la gente guarda el enlace de la sala.
        out = cli("api", "patch", f"/api/2.0/genie/spaces/{previo}",
                  "--json", json.dumps(cuerpo, ensure_ascii=False))
        if out.returncode == 0:
            print("✅ Genie Space actualizado")
            print(f"  space_id : {previo}")
            print(f"  título   : {TITLE}")
            print(f"  tablas   : {len(TABLAS)}")
            guardar_id(previo)
            return 0
        print(f"  no pude actualizar la sala {previo}: {out.stderr.strip()[:300]}")
        print("  intento crear una nueva")

    out = cli("api", "post", "/api/2.0/genie/spaces",
              "--json", json.dumps(cuerpo, ensure_ascii=False))
    if out.returncode != 0:
        print("❌ falló la creación del Genie Space")
        print(out.stderr[:800])
        return 1

    try:
        d = json.loads(out.stdout)
    except json.JSONDecodeError:
        print("No pude interpretar la respuesta como JSON:")
        print(out.stdout[:500])
        return 1

    print("✅ Genie Space creado")
    print(f"  space_id : {d.get('space_id')}")
    print(f"  título   : {d.get('title')}")
    print(f"  tablas   : {len(TABLAS)}")
    guardar_id(d.get("space_id"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
