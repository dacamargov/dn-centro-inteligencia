# Evidencia de ejecución — Centro de Inteligencia D&N

Prototipo **end-to-end** que resuelve un problema real de la industria de medición
de mercado (CPG/retail): **anticipar y cerrar quiebres de stock y fallas de
ejecución en el punto de venta**, desde el dato crudo hasta la acción en una sola
app de negocio.

> **Aviso de datos:** todo el dato es **100% SINTÉTICO**, generado para la demo.
> No contiene datos reales de clientes ni PII. La marca del cliente ("Nestlé") y el
> estudio ("Dichter & Neira") se usan solo como contexto narrativo; ningún registro
> proviene de un sistema real. La marca de dato sintético está gobernada en Unity
> Catalog (tag `dato = sintetico` a nivel esquema y tabla — ver `03_unity_catalog.md`).

## El journey de datos (6 etapas) y dónde está la prueba

| # | Etapa requerida | Qué se construyó | Evidencia (texto) |
|---|---|---|---|
| 1 | **Lakeflow** — ingestar el dato crudo | Pipeline declarativo Auto Loader → bronze → silver → gold desde un Volume de UC, con expectativas de calidad | [`01_lakeflow.md`](01_lakeflow.md) |
| 2 | **Unity Catalog** — gobernar | PK/FK (RELY), comentarios, tags de clasificación, GRANTs, linaje | [`03_unity_catalog.md`](03_unity_catalog.md) |
| 3 | **Lakebase** — servir operacionalmente | Postgres gestionado sirviendo perfiles de PDV por clave, p50 ~1.2 ms | [`04_lakebase.md`](04_lakebase.md) |
| 4 | **ML o Gen AI** — hacerlo inteligente | (a) Modelo de ML de riesgo de quiebre en MLflow + UC + inferencia batch; (b) 4 agentes Gen AI con tool-calling | [`02_ml.md`](02_ml.md) · [`05_genai.md`](05_genai.md) |
| 5 | **Genie Agent** — consultar en lenguaje natural | Sala real NL→SQL sobre el esquema gobernado | [`06_genie.md`](06_genie.md) |
| 6 | **Databricks App** — exponer a negocio | App vivo, 33/33 rutas 200, cableado a todas las etapas | [`07_app.md`](07_app.md) |
| + | **Handoff gold → Lakebase** (cierre de deriva) | Perfil servible derivado de gold+modelo (`pdv_perfil_gold`), no recálculo ad-hoc | [`08_gold_serving_handoff.md`](08_gold_serving_handoff.md) |

**Cómo se construyó (build + AI mindset):** relato del workflow con IA, herramientas
y trade-offs → [`../docs/COMO_SE_CONSTRUYO.md`](../docs/COMO_SE_CONSTRUYO.md).

## Resumen de resultados verificados

- **Lakeflow:** pipeline `COMPLETED` — bronze 2 700, silver 2 700, gold 691 filas;
  8 expectativas de calidad medidas (100% en las críticas).
- **Unity Catalog:** 4 PK + 3 FK (RELY), comentarios en tablas/columnas, tags
  `capa`/`dato` y `dato=sintetico` a nivel esquema, GRANTs a `account users`.
- **Lakebase:** instancia `AVAILABLE`, 140 perfiles, lectura por clave p50 1.22 ms /
  p95 1.58 ms.
- **ML:** modelo `modelo_riesgo_quiebre` v1 `@campeon` en UC; MAE 0.0551 (−19% vs
  baseline); 553 predicciones servidas (34 ALTO / 180 MEDIO / 339 BAJO).
- **Gen AI:** 4 agentes `success`, recomendaciones reales con acción tipada.
- **Genie:** 3 preguntas en español → SQL correcto sobre UC → respuestas con cifras.
- **App:** `https://dn-centro-inteligencia-7474652595969633.aws.databricksapps.com`,
  todas las rutas 200, Genie en modo `live`, Lakebase conectado, demo en marcha.

## Cómo reproducir

Todo está declarado como **Databricks Asset Bundle** (`databricks.yml` +
`resources/*.yml`). Pasos y código fuente:

- Ingesta/Lakeflow: `src/lakeflow/` · `resources/06_lakeflow.yml`
- Gobernanza UC: `src/uc/00_gobernanza.sql`
- Lakebase: `src/lakebase/` · `src/esquema/lakebase_schema.sql` · `resources/05_lakebase.yml`
- ML: `src/ml/entrenar_riesgo_quiebre.py` · `resources/07_ml.yml`
- Agentes Gen AI: `src/agentes/` · `resources/03_agentes.yml`
- App: `src/app/` · `resources/04_app.yml`
