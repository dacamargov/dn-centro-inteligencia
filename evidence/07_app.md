# Evidencia de ejecución — Databricks App

> Prerrequisito: **A Databricks app — surface the solution to business users**
> App desplegado y vivo, protegido por OAuth del workspace. URL:
> `https://dn-centro-inteligencia-7474652595969633.aws.databricksapps.com`

## Smoke-test de las rutas (33/33 GET → HTTP 200)

Cada ruta de la API devolvió `200 OK` (medido con bearer token del workspace):

```
200  /                              (frontend React compilado)
200  /api/config                    200  /api/kpis
200  /api/demo/status               200  /api/demo/volumen
200  /api/visitas/recent            200  /api/visitas/timeline
200  /api/visitas/skus-criticos     200  /api/visitas/por-categoria
200  /api/visitas/por-pais          200  /api/targets
200  /api/social/recent             200  /api/social/viral
200  /api/social/termometro         200  /api/social/por-categoria
200  /api/campanas                  200  /api/recommendations
200  /api/precios/brechas           200  /api/precios/por-categoria
200  /api/precios/por-cadena        200  /api/precios/promociones
200  /api/pdv                       200  /api/pdv/traslados
200  /api/pdv/traslados/resumen     200  /api/lakebase/status
200  /api/lakebase/pdv              200  /api/lakebase/recientes
200  /api/lakebase/stats            200  /api/lakebase/flujo
200  /api/lakebase/impacto          200  /api/genie/space-id
200  /api/dashboard/embed-url       200  /api/campo/acciones
200  /api/campo/despachadas

== 33/33 rutas GET -> 200 ==  (latencias ~0.6–2.8 s)
```

## Payloads clave (prueba de que el app está cableado a cada etapa)

**`/api/config`** → `{"cliente": "Nestlé"}`

**`/api/genie/space-id`** → sala de Genie **real** en modo `live`:
```json
{
  "space_id": "01f1ade64422109f89b4df24b4eb6f15",
  "mode": "live",
  "embed_url": "https://fevm-dacamargovws.cloud.databricks.com/embed/genie/rooms/01f1ade64422109f89b4df24b4eb6f15"
}
```

**`/api/lakebase/status`** → conectado a Postgres, sirviendo perfiles:
```json
{
  "configured": true,
  "host": "ep-withered-fog-d8anc639.database.us-east-2.cloud.databricks.com",
  "database": "databricks_postgres", "schema": "campo",
  "tables": ["pdv_perfiles", "sugerencias_log"],
  "connected_as": "55d1405b-3a62-4938-9488-aa88bd1c1bf7",
  "postgres_version": "PostgreSQL 16.15 ...",
  "counts": {"pdv_perfiles": 140, "sugerencias_servidas": 298}
}
```

## Orquestación en vivo (`/api/demo/status`)

El app descubre y controla los 7 jobs (3 generadores de datos + 4 agentes) por el
prefijo `DNCentro`. El botón "Iniciar demo" los enciende:

```
POST /api/demo/start -> {"ok": true, "started": [
   DNCentro datagen — precios, DNCentro datagen — social, DNCentro datagen — visitas,
   DNCentro agent — red_abastecimiento, ... ]}
GET  /api/demo/status -> {"running": true, "found": 7}
```

## Cómo el app cierra el journey

Una sola interfaz para negocio reúne las 6 etapas: KPIs de la capa gold de
**Lakeflow**, exploración con **Genie** (NL→SQL), copiloto de campo servido por
**Lakebase** (lectura por clave), recomendaciones de los agentes de **Gen AI**, y
todo gobernado por **Unity Catalog**. Es la superficie que consume el patrocinador
y el dueño de dominio.
