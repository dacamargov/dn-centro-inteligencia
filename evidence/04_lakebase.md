# Evidencia de ejecución — Lakebase (serving operacional)

> Prerrequisito: **Lakebase — serve the data operationally**
> Lakebase (Postgres gestionado) sirve el **camino caliente** del copiloto de
> campo: una lectura por clave del perfil del punto de venta, con latencia de
> milisegundos. Instancia `dn-centro-lakebase` (CU_1), base `databricks_postgres`.

> Toda la evidencia es la salida JSON real del job
> `DNCentro lakebase — evidencia de serving`
> (`src/lakebase/evidencia_serving.py`), exportada por `dbutils.notebook.exit`.

## Instancia

```
instancia : dn-centro-lakebase
host      : ep-withered-fog-d8anc639.database.us-east-2.cloud.databricks.com
base      : databricks_postgres
estado    : AVAILABLE
```

## Tablas operacionales (esquema aplicado desde `src/esquema/lakebase_schema.sql`)

```
campo.pdv_perfiles        -- perfil servible por tienda (sembrado desde Unity Catalog)
campo.sugerencias_log     -- log de sugerencias servidas al mercaderista
public.genie_interactions -- bitácora de interacciones de Genie
```

## Perfiles servibles

```
perfiles sembrados : 140   (una fila por punto de venta, UPSERT desde UC)
```

El perfil de cada PDV es un agregado del histórico de `visitas` en Unity Catalog
(categorías que peor ejecutan, SKUs foco, disponibilidad histórica, riesgo de
quiebre). En producción sería una *synced table* alimentada desde la capa gold.

## Latencia de lectura por clave primaria (camino caliente, 50 iteraciones)

| métrica | ms |
|---|---:|
| p50 | **1.22** |
| p95 | **1.58** |
| min | 1.06 |
| max | 3.06 |

> El copiloto de campo resuelve el perfil del PDV en ~1 ms — latencia operacional
> (OLTP), no analítica. Es lo que permite que el mercaderista reciba la sugerencia
> en el momento de la visita, no en un batch nocturno.

## Payload de ejemplo servido (clave `PDV-0001`)

```json
{
  "store_id": "PDV-0001",
  "nombre": "Super 99 Ciudad de Panamá #1",
  "cadena": "Super 99",
  "pais": "Panamá",
  "disponibilidad_hist": "95.83",
  "riesgo_quiebre": "0.042",
  "categorias_prioritarias": ["Culinarios", "Bebidas No Alcohólicas"]
}
```
*(nombre de tienda sintético — ver aviso de datos sintéticos)*

## Gobierno de acceso (privilegios del service principal del app en Postgres)

Service principal del app: `55d1405b-3a62-4938-9488-aa88bd1c1bf7`

```
campo  : SELECT, INSERT, UPDATE, DELETE, TRUNCATE
public : SELECT, INSERT, UPDATE, DELETE, TRUNCATE
```

> El rol de Postgres del service principal lo crea Databricks al adjuntar el
> recurso `database` al app; el job de preparación le otorga los privilegios para
> que el copiloto lea y escriba el log sin fricción.

## Nota de costo

Lakebase (Postgres gestionado) genera costo mientras la instancia está
`AVAILABLE`. Para la demo se usa la capacidad mínima **CU_1** (140 filas, lecturas
por clave). Al terminar la evaluación se puede detener/eliminar la instancia con
`databricks database delete-database-instance dn-centro-lakebase` o desde la UI.
