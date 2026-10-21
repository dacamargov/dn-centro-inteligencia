# Evidencia de ejecución — Unity Catalog (gobernar el dato)

> Prerrequisito: **Unity Catalog — govern the data**
> Script aplicado: `src/uc/00_gobernanza.sql` (30/30 sentencias efectivas). Toda la
> evidencia se lee de `information_schema` del catálogo `dacamargovws_catalog`,
> esquema `ditcher`.

## 1 · Claves primarias y foráneas (modelo semántico gobernado)

Leído de `information_schema.table_constraints` + `key_column_usage`:

| tipo | constraint | tabla | columna(s) |
|---|---|---|---|
| PRIMARY KEY | `pk_tiendas` | tiendas | store_id |
| PRIMARY KEY | `pk_productos` | productos | sku |
| PRIMARY KEY | `pk_paises` | paises | country_code |
| PRIMARY KEY | `pk_visitas` | visitas | visita_id |
| FOREIGN KEY | `fk_visitas_tienda` | visitas | store_id → tiendas.store_id |
| FOREIGN KEY | `fk_visitas_producto` | visitas | sku → productos.sku |
| FOREIGN KEY | `fk_tiendas_pais` | tiendas | country_code → paises.country_code |

> Las PK/FK se declaran `RELY`: el optimizador las usa y, sobre todo, **Genie y el
> catálogo las leen como relaciones** para resolver joins correctamente.

## 2 · Comentarios de negocio (documentación gobernada)

Tablas (de `information_schema.tables.comment`):

```
visitas             → Hecho de auditoría de anaquel: una fila por lectura tienda×SKU
                      (stock, facings, precio, promo, planograma, share of shelf,
                      confianza del reconocimiento de imagen).
ejecucion_pdv_gold  → Capa GOLD de Lakeflow: KPIs de ejecución por tienda×categoría
                      (disponibilidad, ejecución perfecta, promo, share of shelf cliente).
predicciones_riesgo → Inferencia batch del modelo UC modelo_riesgo_quiebre@campeon:
                      riesgo de quiebre por tienda×categoría con tier ALTO/MEDIO/BAJO.
```

Columnas clave de `visitas` (de `information_schema.columns.comment`):

```
en_stock        → TRUE si el SKU estaba disponible en anaquel en la visita (base del quiebre).
share_of_shelf  → Participación de caras del SKU sobre el total de la categoría (0-1).
confianza_ir    → Confianza del reconocimiento de imagen de la lectura (0-1).
es_cliente      → TRUE si el SKU pertenece al cliente (Nestlé), FALSE si es competencia.
```

## 3 · Tags de clasificación (incluida la marca de dato sintético)

Esquema (`information_schema.schema_tags`): `ditcher → dato = sintetico`.

Tablas (`information_schema.table_tags`):

| tabla | tag | valor |
|---|---|---|
| auditorias_bronze | capa / dato | bronze / sintetico |
| auditorias_silver | capa / dato | silver / sintetico |
| ejecucion_pdv_gold | capa / dato | gold / sintetico |
| predicciones_riesgo | capa / dato | ml_serving / sintetico |

> **Cumplimiento del requisito de datos:** la etiqueta `dato = sintetico` queda
> gobernada a nivel esquema y por tabla. No hay datos reales de clientes ni PII en
> el esquema; todo es generado para la demo.

## 4 · GRANTs de acceso (gobierno de permisos)

De `information_schema.schema_privileges`:

| grantee | privilegios |
|---|---|
| `account users` | USE_SCHEMA, SELECT |
| service principal del app (`55d1405b-…`) | USE_SCHEMA, SELECT, MODIFY |
| owner (`daniel.vargas@…`) | ALL_PRIVILEGES, MANAGE |

Además: `GRANT EXECUTE ON FUNCTION …modelo_riesgo_quiebre TO account users` (acceso
gobernado al modelo de ML registrado en UC). ✅ aplicado.

## 5 · Linaje

Todo el journey vive bajo el mismo catálogo UC, de modo que el linaje encadena:
`Volume (landing) → auditorias_bronze → auditorias_silver → ejecucion_pdv_gold`,
y `visitas → modelo_riesgo_quiebre → predicciones_riesgo`. Unity Catalog captura
este linaje automáticamente al correr el pipeline y el job de ML.
