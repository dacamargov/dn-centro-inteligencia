# Evidencia — handoff GOLD → Lakebase (cierre del gap de deriva)

> Corrige el gap señalado en la revisión: *"the Lakebase profile store is currently
> populated outside the live Lakeflow-to-Unity-Catalog pipeline."* Ahora el perfil
> servible se **deriva de la capa gold gobernada**, no de un recálculo paralelo.

## Qué cambió

Antes el seed de Lakebase recomputaba el perfil con un agregado ad-hoc sobre
`visitas`. Ahora:

```
ejecucion_pdv_gold (GOLD de Lakeflow)  ┐
predicciones_riesgo (salida del modelo) ├─►  pdv_perfil_gold (UC, gobernada)  ──►  campo.pdv_perfiles (Lakebase)
tiendas / paises (maestros UC)          ┘        (una fila por PDV, PK+CDF)        (UPSERT que LEE la tabla gold)
```

El serving y el entrenamiento ahora leen de la **misma capa gold**, así que sus
features no pueden desalinearse. Código: `src/datos/05_perfil_gold.sql` (origen
único) y `src/lakebase/preparar_lakebase.py` (handoff).

## `pdv_perfil_gold` en Unity Catalog

```
tabla  : dacamargovws_catalog.ditcher.pdv_perfil_gold
filas  : 140   (una por PDV)
PK     : store_id (RELY)
props  : delta.enableChangeDataFeed = true   (listo para synced table)
riesgo : promedio 0.085   (viene de predicciones_riesgo, el modelo)
```

Top riesgo (del modelo, no de un recálculo):

| store_id | riesgo_quiebre | categorias_prioritarias |
|---|---:|---|
| PDV-0125 | 0.168 | Confitería y Snacks, Bebidas Calientes |
| PDV-0042 | 0.164 | Bebidas Calientes, Bebidas No Alcohólicas |
| PDV-0039 | 0.155 | Lácteos, Confitería y Snacks |

## Handoff ejecutado (job `DNCentro lakebase — esquema, semilla y permisos`)

El job `TERMINATED SUCCESS`; el notebook construye `pdv_perfil_gold` desde gold y
luego UPSERT hacia Postgres **leyendo esa tabla gold**. Serving verificado:

```
perfiles servibles : 140
latencia p50       : ~1–3 ms (lectura por clave)
tablas             : campo.pdv_perfiles, campo.sugerencias_log, public.genie_interactions
```

## Synced table gestionada — listo, bloqueado solo por permiso del entorno

`pdv_perfil_gold` ya cumple los dos requisitos de una synced table de Lakebase:
**PK** y **Change Data Feed**. En un workspace con permiso de `CREATE CATALOG`
sobre el metastore, el serving continuo es un solo comando:

```bash
databricks database create-database-catalog dn_lakebase dn-centro-lakebase databricks_postgres
databricks database create-synced-database-table \
  dn_lakebase.campo.pdv_perfil_gold \
  --database-instance-name dn-centro-lakebase \
  --logical-database-name databricks_postgres \
  --json '{"spec":{"source_table_full_name":"dacamargovws_catalog.ditcher.pdv_perfil_gold",
                    "primary_key_columns":["store_id"],"scheduling_policy":"TRIGGERED"}}'
```

En **este** workspace el primer comando devuelve
`User does not have CREATE CATALOG on Metastore` — es una restricción de permisos
del entorno de la demo, no de la solución. El origen gold ya está preparado; por eso
el handoff se hace hoy con un job gobernado que lee la tabla gold (mismo efecto:
cero deriva entre entrenamiento y serving).
