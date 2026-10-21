# Evidencia de ejecución — Gen AI (agentes de dato a decisión)

> Prerrequisito: **ML or Gen AI — make the solution intelligent**
> Cuatro agentes de Gen AI con **tool-calling** sobre la **Foundation Model API**
> de Databricks (`databricks-meta-llama-3-3-70b-instruct`). Cada agente recibe
> herramientas (no datos masticados), decide qué consultar en Unity Catalog y
> escribe a lo sumo una recomendación accionable por tick a la tabla
> `recomendaciones`. Bucle de agente auditable en `src/agentes/_shared.py`.

## Corridas de esta sesión (log real `runs`, zona America/Panama en UTC)

| agente | status | recs | started_at |
|---|---|---:|---|
| red_abastecimiento | success | 1 | 2026-10-21T13:51:45Z |
| price_promo | success | 1 | 2026-10-21T13:51:07Z |
| pulso_ejecucion | success | 1 | 2026-10-21T13:51:01Z |
| sentimiento_marca | success | 0 | 2026-10-21T13:50:59Z |
| red_abastecimiento | success | 1 | 2026-10-21T13:49:44Z |
| price_promo | success | 1 | 2026-10-21T13:49:42Z |
| pulso_ejecucion | success | 1 | 2026-10-21T13:49:39Z |

> `sentimiento_marca` devolvió 0 en un tick: el agente evaluó los datos y decidió
> que no había nada digno de recomendar (devuelve `{"should_recommend": false}`).
> Eso es señal de criterio, no de falla — no inventa recomendaciones.

## Inventario de recomendaciones acumuladas por agente × severidad

| agente | severidad | n |
|---|---|---:|
| price_promo | high / medium | 14 / 1 |
| pulso_ejecucion | high / medium | 7 / 8 |
| red_abastecimiento | high / medium / low | 11 / 3 / 1 |
| sentimiento_marca | high / medium | 7 / 6 |

## Salidas reales del modelo (última recomendación de cada agente)

### `price_promo` — severity: high — "Brecha de precio en Culinarios"
> **Análisis:** El cliente tiene un índice de precio de 119.4 en la categoría de
> Culinarios en la cadena Bravo de República Dominicana, lo que supone una brecha
> de 30.6 puntos con respecto a la competencia. Esto sugiere que el cliente está
> muy por encima de la competencia en términos de precio en esta categoría y plaza.
>
> **Recomendación:** Ajustar el precio del cliente en la categoría de Culinarios
> en la cadena Bravo de República Dominicana para reducir la brecha con la competencia.
>
> **Acción sugerida (JSON estructurado):**
> `{"type":"ajustar_precio","params":{"categoria":"Culinarios","country_code":"DO","cadena":"Bravo","indice_actual":119.4,"indice_objetivo":100}}`

### `pulso_ejecucion` — severity: high — "Ejecución deficiente en PDV-0111"
> **Análisis:** La tienda PDV-0111 presenta una ejecución del 41.7% y una
> disponibilidad del 66.7%, lo que indica un desempeño deficiente en comparación
> con los estándares de la empresa.
>
> **Recomendación:** Realizar una visita correctiva a la tienda PDV-0111 para
> identificar y abordar los problemas que están afectando su ejecución y disponibilidad.
>
> **Acción:** `{"type":"visita_prioritaria","params":{"store_id":"PDV-0111","mercaderista":"S. Herrera","motivo":"Ejecución deficiente y baja disponibilidad"}}`

> Nota de consistencia entre etapas: PDV-0111 también aparece en el **top-10 de
> riesgo del modelo de ML** (`02_ml.md`). Dos técnicas independientes —modelo
> supervisado y agente LLM— coinciden en la misma tienda crítica.

### `red_abastecimiento` — severity: medium — "Traslado de Svelty Deslactosada"
> **Análisis:** Se identificó un traslado de Svelty Deslactosada desde Plaza Vea
> Trujillo #129 hasta Bodega Lima #139, con una ganancia neta de $139.53, el más
> alto de la lista.
>
> **Recomendación:** Aprobar el traslado para maximizar la ganancia neta.
>
> **Acción:** `{"type":"traslado_mercaderia","params":{"sku":"SKU-0014","origen":"Plaza Vea Trujillo #129","destino":"Bodega Lima #139","unidades":48,"distancia_km":36.5,"ganancia_neta_usd":139.53}}`

### `sentimiento_marca` — severity: medium — "Amplificar post de Nescafé"
> **Análisis:** La conversación social muestra sentimiento positivo. El post con
> mayor alcance incremental estimado es el de Nescafé Tradición en Jumbo de El
> Salvador (alcance incremental ~950 000, engagement ~11 400).
>
> **Recomendación:** Amplificar el post para aumentar alcance y engagement.
>
> **Acción:** `{"type":"amplificar_contenido","params":{"post_id":"post_7f1545f2f18f41","platform":"x","marca":"Nescafé","alcance_estimado":950000,"presupuesto_usd":5000}}`

## Por qué esto es Gen AI de verdad (no plantillas)

- Llama real vía Foundation Model API con bucle de **tool-calling** (`run_agent`
  en `_shared.py`): el modelo pide herramientas, lee datos de UC y razona.
- La salida es JSON estructurado y validado (`parse_agent_output`), con acción
  tipada que el app puede ejecutar.
- Todas las marcas/tiendas/SKU son **sintéticas** (Nescafé Tradición, Svelty,
  Plaza Vea #129, etc. son datos generados para la demo).
