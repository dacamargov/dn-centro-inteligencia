# Lakebase — el copiloto de campo

La pestaña **Campo** viene apagada. Una instancia de Postgres cuesta aunque nadie la consulte, y
el resto de la aplicación funciona sin ella: mientras esté apagada, esa pestaña muestra un
mensaje de "no configurado" y nada más.

## Qué agrega

El perfil de cada punto de venta vive en Postgres y el app lo lee por clave en menos de 100 ms,
que es el presupuesto real de un mercaderista parado frente al anaquel con el celular en la mano.
Es el contraste con el resto de la aplicación, que corre sobre Delta: mismo dato, dos caminos
distintos, cada uno dimensionado para lo que tiene que hacer.

Y cierra el ciclo, que es lo que la convierte en algo más que un generador de sugerencias: cada
plan servido vuelve con lo que el mercaderista efectivamente corrigió, así que la tasa de
ejecución del panel es una medición del log y no un supuesto.

La jornada simulada corre en un hilo del servidor, no en el navegador, así que el feed sigue
latiendo mientras recorrés las otras pestañas.

## Cómo se enciende

Son tres pasos y **el orden importa**.

### 1. Crear la base de datos

```bash
databricks postgres list-projects -o json          # ¿ya hay uno?
databricks postgres list-endpoints projects/<proyecto>/branches/<rama> -o json
databricks postgres list-roles projects/<proyecto>/branches/<rama> -o json

databricks postgres create-database projects/<proyecto>/branches/<rama> \
  --database-id dncentro \
  --json '{"spec":{"postgres_database":"dncentro",
                   "role":"projects/<proyecto>/branches/<rama>/roles/<tu-rol>"}}'
```

El `role` es tu identidad: la que va a ser dueña de las tablas.

### 2. Adjuntarle la instancia al app

Esto es lo que hace que Databricks le cree al service principal del app su rol de Postgres. Sin
este paso, el paso 3 no tiene a quién otorgarle privilegios.

En `resources/04_app.yml`, descomentá el recurso `database` y volvé a instalar pasando el host:

```yaml
      resources:
        - name: sql-warehouse
          sql_warehouse:
            id: ${var.warehouse_id}
            permission: CAN_USE
        # Descomentar para encender el copiloto de campo:
        - name: lakebase
          database:
            instance_name: ${var.lakebase_instance}
            database_name: ${var.lakebase_db}
            permission: CAN_CONNECT_AND_CREATE
```

```bash
./instalar.sh \
  --var lakebase_host=<host-del-endpoint>.database.cloud.databricks.com \
  --var lakebase_instance=<nombre-corto-de-la-instancia> \
  --var lakebase_db=dncentro
```

`lakebase_instance` es el nombre corto de la instancia, no la ruta completa del endpoint.

### 3. Esquema, perfiles y privilegios

```bash
./scripts/habilitar_lakebase.sh \
  --instancia projects/<proyecto>/branches/<rama>/endpoints/<endpoint>
```

Aplica `src/esquema/lakebase_schema.sql`, siembra `campo.pdv_perfiles` desde Unity Catalog y le
otorga privilegios al rol del service principal.

Si corrés el paso 3 antes del 2 vas a ver `el rol <id> todavía no existe`. El app va a conectar
y va a fallar en el primer `SELECT`. Se arregla repitiendo el paso 3.

Necesitás `psql` 16 en la máquina (`brew install postgresql@16`). Si está en otra ruta, pasala
con `--psql`.

## Qué se conserva y qué se vacía

`campo.pdv_perfiles` es el perfil maestro de los puntos de venta: no se toca al limpiar.
`campo.sugerencias_log` y `public.genie_interactions` sí, porque son la bitácora de la operación.

## Costo

Apagá la instancia cuando no la estés usando. Es lo único de esta aplicación que no baja a cero
por sí solo: el warehouse tiene auto-stop, los jobs quedan pausados y el app se detiene, pero la
instancia de Postgres sigue facturando.
