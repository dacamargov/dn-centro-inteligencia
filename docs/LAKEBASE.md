# Lakebase — el copiloto de campo

No hay nada que encender. `./instalar.sh` crea la instancia de Postgres, aplica el esquema,
siembra los perfiles de punto de venta y le otorga privilegios al service principal del app. La
pestaña **Campo** abre funcionando.

Este documento explica qué agrega, cómo está armado y qué hacer si algo queda a medias.

## Qué agrega

El perfil de cada punto de venta vive en Postgres y el app lo lee por clave en menos de 100 ms,
que es el presupuesto real de un mercaderista parado frente al anaquel con el celular en la mano.
En una instalación recién hecha esa lectura tarda menos de 0.1 ms del lado de la base.

Es el contraste con el resto de la aplicación, que corre sobre Delta: mismo dato, dos caminos
distintos, cada uno dimensionado para lo que tiene que hacer. Delta responde preguntas sobre
millones de observaciones; Postgres responde una pregunta sobre una fila, muchas veces por
segundo.

Y cierra el ciclo, que es lo que la convierte en algo más que un generador de sugerencias: cada
plan servido vuelve con lo que el mercaderista efectivamente corrigió, así que la tasa de
ejecución del panel es una medición del log y no un supuesto.

La jornada simulada corre en un hilo del servidor, no en el navegador, así que el feed sigue
latiendo mientras recorrés las otras pestañas.

## Cómo está armado

| Pieza | Dónde |
|---|---|
| Instancia de Postgres | la crea `instalar.sh` (paso 4) |
| Esquema (`campo`, `public.genie_interactions`) | `src/esquema/lakebase_schema.sql` |
| Job que lo aplica, siembra y da permisos | `resources/05_lakebase.yml` |
| Notebook que hace el trabajo | `src/lakebase/preparar_lakebase.py` |
| Cliente de Postgres del app | `src/app/server/lakebase.py` |

Se usa la variante **provisioned** de Lakebase, con la base `databricks_postgres` que viene
creada de fábrica. Usar esa base y no una propia evita un `CREATE DATABASE` en la instalación,
que necesitaría una conexión aparte; el aislamiento lo da el esquema `campo` y el hecho de que
la instancia sea exclusiva de la demo.

El notebook corre **dentro** de Databricks, no en la máquina de quien instala. Es la razón por
la que existe como notebook y no como script de shell: la versión anterior canalizaba SQL a
`psql`, lo que obligaba a tener PostgreSQL instalado localmente para poder instalar la demo.
Ahora el único requisito es el CLI de Databricks.

### El orden de los tres pasos

El notebook hace esquema, semilla y privilegios en ese orden, y corre después de desplegar el
app. Eso no es casual:

1. El **rol de Postgres del service principal** lo crea Databricks al desplegar el app con la
   instancia adjunta como recurso (`resources/04_app.yml`). Antes de ese momento el rol no
   existe.
2. Las tablas las crea el usuario que instala, así que son **suyas**. El rol del service
   principal nace sin privilegios sobre ellas.
3. Sin el `GRANT` del paso 3, el app conecta bien y falla en el primer `SELECT` — un síntoma
   bastante desorientador, porque la conexión parece sana.

Si el notebook avisa `el rol <id> todavía no existe`, corrió antes de que el app existiera.
Se arregla repitiéndolo:

```bash
databricks bundle run lakebase -t demo
```

## Qué se conserva y qué se vacía

`campo.pdv_perfiles` es el perfil maestro de los puntos de venta: no se toca al limpiar.
`campo.sugerencias_log` y `public.genie_interactions` sí, porque son la bitácora de la operación.

Volver a correr el job refresca los perfiles con un UPSERT y no pierde el log.

## Costo

Es lo único de esta aplicación que **no baja a cero por sí solo**. El warehouse tiene auto-stop,
los jobs quedan pausados con `./apagar.sh` y el app se detiene, pero una instancia de Postgres
factura mientras exista, la consulte alguien o no.

Se crea en tamaño `CU_1`, el más chico, que le sobra: el copiloto sirve lecturas por clave sobre
140 filas. Si vas a dejar la demo sin usar por un tiempo, conviene desinstalar en vez de solo
apagar.

```bash
./desinstalar.sh              # se lleva la instancia junto con todo lo demás
```

Para verificar que no quedó ninguna instancia colgada:

```bash
databricks database list-database-instances -o json
```

## Instalar sin Lakebase

No hay un flag `--sin-lakebase`, y la razón es concreta: el app lleva la instancia adjunta como
recurso, y Databricks rechaza el deploy de un app que apunta a una instancia inexistente. No
alcanza con saltear el paso.

Para instalar sin ella, comentá el recurso en `resources/04_app.yml`:

```yaml
      resources:
        - name: sql-warehouse
          sql_warehouse:
            id: ${var.warehouse_id}
            permission: CAN_USE
        # - name: lakebase
        #   database:
        #     instance_name: ${var.lakebase_instance}
        #     database_name: ${var.lakebase_db}
        #     permission: CAN_CONNECT_AND_CREATE
```

El resto de la aplicación funciona igual y la pestaña **Campo** muestra "no configurado".

## Ajustes

```bash
./instalar.sh --var lakebase_capacity=CU_2         # instancia más grande
./instalar.sh --var lakebase_instance=mi-postgres  # otro nombre
./instalar.sh --var lakebase_db=mi_base            # otra base dentro de la instancia
```

Ojo con `lakebase_db`: si apuntás a una base que no existe, el deploy del app falla. La de
fábrica es `databricks_postgres`.

`lakebase_host` también es una variable, pero no hay que configurarla: `instalar.sh` la resuelve
de la instancia en cada corrida. Si desplegás con `databricks bundle deploy` a mano, el host se
pierde —los `--var` no se guardan— y la pestaña Campo vuelve a decir "no configurado". La
solución es correr `./instalar.sh`, que es idempotente.

## Autenticación, y por qué `LAKEBASE_INSTANCE_NAME` va vacío

Hay dos modelos de credencial según cómo esté provisionado Lakebase, y el app los distingue por
esa variable de entorno (`src/app/server/lakebase.py`):

- **Vacía** — el token OAuth del service principal autentica directo contra Postgres, porque el
  recurso `database` del app ya lo federó dentro de la instancia. Es el caso de esta demo.
- **Con un nombre** — el app emite una credencial acotada al endpoint vía
  `/api/2.0/postgres/credentials`. Es el modelo de los endpoints *autoscaling*.

Por eso `resources/04_app.yml` la fija en blanco a propósito. Si le pusieras el nombre de la
instancia, el app tomaría el segundo camino e intentaría emitir una credencial de endpoint, que
es justo lo que el service principal no puede hacer.
