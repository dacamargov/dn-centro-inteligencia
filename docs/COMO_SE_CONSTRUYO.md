# Cómo se construyó — build workflow & AI mindset

> **English TL;DR (build + AI mindset account).** This solution was built in **Cursor**
> using an **AI coding agent (Claude)** as the primary pair-programmer, driving
> **Databricks** through the **Databricks MCP server, the Databricks CLI, and Asset
> Bundles**, plus a set of **domain skills** (Lakeflow/DLT, Unity Catalog, Lakebase,
> MLflow, Genie). AI was the force multiplier in four ways: (1) **scaffolding** the
> whole Asset Bundle, resource YAMLs, DLT pipeline, ML notebook and FastAPI/React app
> from intent; (2) a tight **error-driven debugging loop** where the agent read live
> pipeline event logs and job errors and fixed them; (3) **evidence capture**,
> querying `information_schema` and the live app/Genie/Lakebase APIs and writing the
> results to text; (4) generating the **deck and narrative**. The non-negotiable
> trade-off: **AI writes, but nothing ships unverified** — every artifact was checked
> against live query results, and the money math (haversine transfers, share-of-shelf
> denominator, price index) was kept as **deterministic SQL**, with the LLM only
> choosing which already-computed candidate to escalate. Where AI needed correction is
> documented below (streaming-window violation, ambiguous column, dataset-type change,
> Decimal serialization, UC tag-policy rejection). Full account in Spanish follows.

---

## Herramientas usadas

| Herramienta | Para qué |
|---|---|
| **Cursor** (IDE) + **agente de IA (Claude)** | Pair-programmer principal: escribir pipelines, notebooks, YAML del bundle, backend FastAPI, frontend React, SQL de gobernanza y el deck. |
| **Databricks MCP server** | Ejecutar SQL, inspeccionar catálogo/esquemas, listar endpoints y recursos desde el propio agente, sin salir del loop. |
| **Databricks CLI** | `bundle deploy/run`, `jobs run-now`, `database`, `registered-models`, `serving-endpoints`. |
| **Databricks Asset Bundles (DAB)** | Infra-como-código: todo (esquema, jobs, pipeline, app, Lakebase) declarado en `databricks.yml` + `resources/*.yml`. Reproducible con un comando. |
| **Skills de dominio** | Guías de Lakeflow/DLT, Unity Catalog, Lakebase, MLflow y Genie que el agente consulta para seguir buenas prácticas. |
| **Foundation Model API** | Los 4 agentes de la solución corren sobre `databricks-meta-llama-3-3-70b-instruct`. |

## Cómo la IA aceleró el trabajo (y dónde fue el multiplicador)

1. **Scaffolding desde la intención.** Describí el journey de 6 etapas y el agente
   generó el esqueleto completo: el pipeline DLT bronze→silver→gold, el notebook de
   ML con MLflow + registro en UC, el SQL de gobernanza, y los `resources/*.yml` del
   bundle. Lo que habrían sido días de boilerplate fueron minutos.

2. **Loop de depuración guiado por errores reales.** El mayor acelerador no fue
   escribir código sino **cerrarlo contra el entorno vivo**: el agente desplegaba,
   leía el *event log* del pipeline o el error del job, y corregía. Varias de esas
   correcciones están documentadas abajo.

3. **Captura de evidencia como texto.** El agente consultó `information_schema`, la
   Genie Conversation API, las credenciales y latencias de Lakebase y las rutas del
   app, y escribió los resultados reales a `evidence/` — en vez de capturas de
   pantalla, texto verificable.

4. **Narrativa y deck.** El deck (`presentacion/`) y este relato se redactaron con el
   agente, anclados en las mismas cifras medidas en la red (OSA 91.8%, quiebre 8.2%).

## Trade-offs al construir con IA

- **La IA escribe; nada se publica sin verificar.** Cada artefacto generado se validó
  contra resultados de consulta en vivo. Ejemplos: el modelo se confirmó leyendo las
  métricas reales del run de MLflow (`mae=0.0551`), y las respuestas de Genie se
  comprobaron ejecutando el SQL generado.
- **La IA no decide la plata.** La economía (distancia *haversine* entre PDV para
  traslados, umbral de facings para "sobrestock", ventana de decaimiento de la
  propuesta, índice de precio normalizado por 100 g/ml dentro de subcategoría, y el
  denominador de *share of shelf* que incluye **todo** el anaquel, no solo el cliente)
  se mantuvo como **SQL determinista**. El LLM solo elige cuál de los candidatos ya
  calculados vale la pena escalar. Separar lo que debe y no debe quedar en manos de un
  modelo fue una decisión deliberada, reforzada al construir con IA.
- **Dónde la IA necesitó corrección** (iteración real de esta construcción):
  - **Silver en streaming con ventana no temporal** (`NON_TIME_WINDOW_NOT_SUPPORTED_IN_STREAMING`):
    el agente primero escribió el *share of shelf* con una `Window` en una tabla de
    streaming. Se corrigió haciendo silver una vista materializada (`dlt.read`).
  - **Referencia ambigua** (`AMBIGUOUS_REFERENCE: es_cliente`): el join traía la
    columna desde dos maestros. Se resolvió seleccionando columnas explícitas y
    eliminando el join redundante.
  - **Cambio de tipo de dataset** (`CANNOT_CHANGE_DATASET_TYPE`): al pasar silver de
    streaming a MV hubo que `DROP` + *full refresh*.
  - **`Decimal` no serializable** en MLflow: los agregados `ROUND(...)` volvían como
    `Decimal` y rompían el `input_example`. Se casteó a `float` nativo.
  - **Política de tags de UC** (`UC_TAG_POLICY_VALUE_NOT_ALLOWED`): un valor de tag
    propuesto por la IA no estaba permitido; se ajustó al vocabulario gobernado.

## Iteración de ingeniería previa (en los comentarios del propio código)

Estas historias viven comentadas en el código y muestran iteración real, no un
resumen pulido a posteriori:

- **Cola de propuestas que se desbordó de noche** → se agregó una **ventana de
  decaimiento (20 min)** para expirar propuestas viejas (`src/agentes/agent_red_abastecimiento.py`).
- **Bug del denominador de *share of shelf*** → se documentó explícitamente que el
  denominador debe incluir todo el anaquel; filtrar por cliente ahí da el número mal.
- **Bug de *threading* del feed en vivo** → la rotación de visitas se movió del
  navegador a un único hilo del servidor, porque el feed se congelaba al cambiar de
  pestaña y múltiples espectadores inflaban el log (`src/app/server/campo_flujo.py`).
- **Presupuesto de latencia de Lakebase** → *token caching* para evitar el costo de
  150–300 ms de emitir credencial en cada request; se rechazó un pool de conexiones.

## Datos sintéticos (de dónde sale "el dato")

La curaduría de los volúmenes sintéticos es código versionado y revisable, no una
caja negra. Vive en `src/datos/`:

- `01_seed_maestros.py` — tiendas, productos (con `es_cliente`, marca, fabricante,
  contenido normalizado), países y FX.
- `02_visitas_generator.py` — lecturas de anaquel con correlaciones realistas
  (disponibilidad, facings, promo, planograma, confianza de visión).
- `03_precios_competencia.py` — precios con ruido por cadena/país para el índice.
- `04_social_generator.py` — conversación social por marca/país.

Y `src/lakeflow/00_generar_crudo.py` produce el **crudo** NDJSON que aterriza en el
Volume y entra por Auto Loader al pipeline de Lakeflow.

## Reproducir

```bash
./instalar.sh            # despliega el bundle completo
# o por partes:
databricks bundle deploy -t demo
databricks bundle run <job>   # p.ej. entrenar_riesgo, lakebase, ingesta_auditorias
```
