# Instalación

```bash
databricks auth login
./instalar.sh
```

Eso es todo. El resto de este documento explica qué pasa adentro, cómo cambiar los valores por
defecto y qué hacer cuando algo falla.

---

## Antes de empezar

| Requisito | Cómo verificarlo |
|---|---|
| CLI de Databricks v0.240+ | `databricks --version` |
| Autenticado | `databricks current-user me` |
| Un SQL Warehouse | `databricks warehouses list` |
| Permiso para crear el esquema | `CREATE SCHEMA` sobre el catálogo destino |
| `python3` | `python3 --version` |

La versión del CLI importa: el recurso `apps` del bundle y los `grants` declarativos sobre
esquemas no existen en versiones anteriores, y el error que devuelven no dice cuál es el
problema. `instalar.sh` avisa si detecta una versión vieja.

## Los siete pasos que corre `instalar.sh`

El instalador es un envoltorio delgado sobre `databricks bundle deploy`. Existe porque hay tres
cosas que un bundle no puede resolver solo, y las tres están marcadas abajo.

| Paso | Qué hace |
|---|---|
| 1 | Verifica el CLI, su versión y la autenticación. |
| 2 | **Descubre el SQL Warehouse** — prefiere uno serverless y encendido. Con `--warehouse <id>` se fija a mano. |
| 3 | Valida el bundle y muestra qué se va a crear, con los nombres ya resueltos. |
| 4 | **Crea el dashboard AI/BI.** Va antes del deploy porque el app recibe el id del dashboard como variable de entorno; hacerlo después obligaría a un segundo deploy. |
| 5 | `bundle deploy`: el esquema, los 8 jobs y el app. |
| 6 | `bundle run instalar`: aplica el DDL, siembra los maestros y corre un primer pulso de cada generador. Un par de minutos. |
| 7 | **Otorga permisos al service principal del app** y lo arranca. El SP recién existe después del paso 5, así que esto no puede ser declarativo. |

Del paso 7 depende que el tablero abra con dato: adjuntar el warehouse le da al app permiso
sobre el warehouse, no sobre las tablas. Sin los `GRANT` todas las rutas devuelven
`INSUFFICIENT_PERMISSIONS`.

## Elegir el workspace

El repositorio no tiene ningún workspace escrito. Hay tres formas de indicarlo, en orden de
preferencia:

```bash
./instalar.sh                                              # el perfil por defecto del CLI
./instalar.sh --profile mi-workspace                       # un perfil concreto
./instalar.sh --host https://mi-ws.cloud.databricks.com    # sin perfil
```

`--host` exporta `DATABRICKS_HOST`, que es la variable que el CLI ya entiende, así que también
sirve tenerla en el entorno junto con `DATABRICKS_TOKEN` — el caso de una máquina de CI.

Los scripts de operación (`encender.sh`, `apagar.sh`, `scripts/*.sh`) aceptan los mismos
`--profile` y `--host`.

## Cambiar los valores por defecto

Todo lo ajustable está declarado como variable en `databricks.yml`, con su descripción. Las
más usadas tienen atajo en el instalador:

```bash
./instalar.sh --catalog mi_catalogo \
              --schema centro_dn \
              --cliente "Unilever" \
              --warehouse 1a2b3c4d5e6f
```

Cualquier otra variable se pasa con `--var`:

```bash
./instalar.sh --var llm_endpoint=databricks-claude-sonnet-4-6
./instalar.sh --var genie_space_id=01ef...      # ver docs/GENIE.md
./instalar.sh --var lakebase_host=...           # ver docs/LAKEBASE.md
```

Para ver los valores resueltos sin crear nada:

```bash
databricks bundle validate -t demo
```

## Instalar dos veces en el mismo workspace

El target `pruebas` cambia el esquema, el nombre del app y el prefijo de los jobs, así que
puede convivir con la instalación normal:

```bash
./instalar.sh -t pruebas          # esquema dn_pruebas, app dn-pruebas
./desinstalar.sh -t pruebas       # se lo lleva completo
```

Sirve para probar un cambio del repositorio sin arriesgar una instalación en uso. El dashboard
también se crea con nombre distinto: sin eso, el generador borraría el dashboard de la otra
instalación al encontrar uno con el mismo nombre.

## Reinstalar y actualizar

| Situación | Comando |
|---|---|
| Cambió código del app o de un notebook | `databricks bundle deploy -t demo` |
| Cambió el DDL, hay tablas nuevas | `databricks bundle run instalar -t demo` |
| Querés volver a sembrar los maestros | `databricks bundle run instalar -t demo --only maestros` |
| Se desconfiguró algo y querés rehacerlo | `./instalar.sh` (es idempotente) |
| Tocaste `src/app/frontend/src` | `cd src/app/frontend && npm install && npm run build`, después `bundle deploy` |

El frontend se despliega compilado: el bundle sube `frontend/dist` y deja las fuentes afuera.
Si editás un `.tsx` y no reconstruís, el app sigue sirviendo la versión anterior.

## Operación del día a día

```bash
./encender.sh              # despausa generadores, espera 75 s, despausa agentes
./encender.sh --sin-espera # los agentes arrancan ya, con el dato que haya
./apagar.sh                # pausa todo; el dato queda
./scripts/limpiar.sh       # vacía las tablas transitorias, conserva los maestros
```

Lo mismo está en el app: el botón **Iniciar demo** del encabezado enciende y apaga, y **Limpiar
datos** vacía las tablas mostrando primero cuántas filas hay en cada una.

Para mirar el dato desde la terminal, sin abrir la interfaz:

```bash
./scripts/consultar.sh "SELECT COUNT(*) FROM {S}.visitas"
./scripts/consultar.sh "SELECT * FROM {S}.recomendaciones ORDER BY creado_en DESC LIMIT 5"
```

`{S}` se expande al catálogo y esquema de la instalación.

## Desinstalar

```bash
./desinstalar.sh
```

Borra el app, los jobs, el dashboard y **el esquema con todas sus tablas y su dato**. Pide
confirmación escribiendo el nombre del esquema. El catálogo y el warehouse no se tocan: no los
creó esta instalación.

Si lo que querés es vaciar el dato y conservar la instalación, es `./scripts/limpiar.sh`.

## Cuando algo falla

**`bundle deploy` falla con un campo desconocido en `apps` o en `grants`.**
CLI viejo. `databricks --version` y actualizalo.

**El tablero abre pero todo marca cero.**
Falta el paso 7, o el job de instalación no llegó a correr. Revisá que el service principal del
app tenga permisos:

```bash
./scripts/consultar.sh "SHOW GRANTS ON SCHEMA {S}"
```

Si no aparece el SP, volvé a correr `./instalar.sh`: repite los grants sin recrear nada.

**El botón "Iniciar demo" dice que no encuentra jobs.**
El app los localiza por prefijo, con la variable de entorno `JOB_PREFIX`. Tiene que ser el mismo
valor con el que se nombran los jobs en `resources/02_generadores.yml` y `03_agentes.yml`, que
es justamente lo que garantiza la variable `job_prefix` del bundle. Si instalaste con un
prefijo y después lo cambiaste, quedaron jobs viejos con el nombre anterior: borralos o volvé
al prefijo original.

**Los agentes corren pero no escriben recomendaciones.**
Suele ser el endpoint del modelo. Mirá el output del run del job: si el import de `openai` o de
`httpx` falla, el entorno serverless no los instaló. Los notebooks los piden explícitamente en
su primera celda por esa razón — `openai` ya viene en serverless, así que pedir solo `openai`
deja al `pip` sin nada que hacer y el import de `httpx` falla en runtime.

**El app queda en `STARTING` mucho tiempo.**
El primer arranque instala dependencias de Python; tarda unos minutos. Después de eso, mirá los
logs en Compute → Apps → tu app → Logs.

**La pestaña Campo dice "no configurado".**
Es lo esperado: Lakebase viene apagado. Ver [LAKEBASE.md](LAKEBASE.md).

**El chat de Genie responde con cifras que no cuadran con el tablero.**
Está en modo demostración, con respuestas precargadas de otra instalación. Regeneralas con la
operación andando un rato: `./scripts/construir_genie_precargado.sh` y volvé a desplegar. O
conectá una sala real — ver [GENIE.md](GENIE.md).
