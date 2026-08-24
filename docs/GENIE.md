# Genie — la sala del Centro de Inteligencia

No hay nada que crear a mano. `./instalar.sh` crea la sala de Genie con las 13 tablas del
esquema cargadas, las instrucciones del negocio escritas y las seis preguntas canónicas con su
SQL de referencia. El chat (el botón flotante abajo a la derecha) abre consultando el lakehouse
en vivo.

## Por qué las instrucciones son el 90% del trabajo

Una sala con las tablas cargadas y sin contexto responde plausible y equivocado. El caso más
claro de este modelo de datos es **share of shelf**:

```sql
-- Lo que hace Genie sin instrucciones: filtra por el cliente y arruina el denominador.
SELECT SUM(facings) FROM visitas WHERE es_cliente = true

-- Lo correcto: el denominador es el anaquel completo, competencia incluida.
SELECT SUM(CASE WHEN es_cliente THEN facings ELSE 0 END) / SUM(facings) * 100 FROM visitas
```

El primero devuelve un número, no un error. Nadie lo nota en una demo.

Lo mismo con los filtros: la categoría se llama `'Bebidas Calientes'`, no `'Bebidas'`, y un
`WHERE categoria = 'Bebidas'` devuelve cero filas sin quejarse. Y con la ventana de tiempo: la
operación es en vivo, así que agregar sobre todo el histórico diluye lo que está pasando ahora.

Por eso `scripts/crear_genie.py` carga, además de las tablas:

- **Contexto de negocio** — quién es el cliente del estudio, qué mide cada tabla, que todo lo
  que no es el cliente es competencia.
- **El modelo de datos y sus joins** — qué se une con qué, y cuáles preguntas no necesitan
  ningún join porque `visitas` ya viene desnormalizada.
- **Cómo se calcula cada métrica** del tablero, incluido el detalle del denominador.
- **Los valores literales** de cada filtro: categorías, canales, formatos, países, fabricantes,
  sentimientos, estados.
- **Seis preguntas de ejemplo con su SQL**, que es la forma más directa de fijar todo lo
  anterior.

## Las preguntas que trae cargadas

Son las mismas que ofrece el modo demostración, así que la experiencia es idéntica con sala real
o sin ella:

1. ¿Cuál es la disponibilidad en anaquel por categoría?
2. ¿Qué puntos de venta tienen la peor ejecución esta hora?
3. ¿Cuál es el share of shelf de nuestras marcas por país?
4. ¿Qué SKUs están agotados en más puntos de venta?
5. ¿Cómo se compara nuestro índice de precio con la competencia por cadena?
6. ¿Qué diferencia hay en ejecución entre canal moderno y tradicional?

Pero lo que conviene mostrar es una **pregunta que no esté en la lista**, porque ahí se ve que
las instrucciones sirvieron. Por ejemplo:

> ¿En qué país tenemos el peor share of shelf y cuánto nos falta para la meta?

Genie arma el share of shelf con el denominador correcto, pondera la meta por facings y une con
`metas_categoria`, nada de lo cual está en las preguntas cargadas.

## Detalles de la creación

`scripts/crear_genie.py` es **idempotente**: busca una sala con el mismo título y, si la
encuentra, la actualiza en su lugar en vez de crear otra. Así conserva el `space_id`, que es lo
que el app recibe como variable de entorno y lo que la gente guarda en un enlace.

El título es la clave de esa búsqueda. Cambiarlo con `--var genie_title=...` crea una sala nueva
y deja la anterior en el workspace.

Dos cosas que la API valida y que conviene saber si vas a tocar el script:

- Las tablas tienen que ir **ordenadas por identificador**, y las preguntas de ejemplo
  **ordenadas por id**. Fuera de orden, el payload se rechaza.
- Cada instrucción necesita un `id` de 32 caracteres hexadecimales en minúscula. El script los
  deriva del contenido con un hash, para que una segunda corrida produzca los mismos ids y
  actualice las instrucciones existentes en vez de acumular duplicados.

### Por qué se crea después de sembrar

Genie valida las tablas en el momento de crear la sala. Si el esquema todavía no tiene tablas,
la creación falla con un `Schema '<catálogo>.<esquema>.<tabla>' does not exist` por cada una.

Por eso el paso 8 del instalador va después del paso 7, que es el que aplica el DDL y siembra. Y
por eso el id de la sala se aplica con un segundo `bundle deploy` que solo toca la configuración
del app.

### El permiso del service principal

El app consulta la sala con la identidad de su service principal, no con la de quien instaló. La
sala tiene su propia lista de control de acceso, así que el instalador le otorga `CAN_RUN`:

```bash
databricks api get /api/2.0/permissions/genie/<SPACE_ID>
```

Sin ese permiso la pestaña devuelve 403 aunque la sala funcione perfectamente desde la interfaz.

## Modo demostración

Con `genie_space_id` vacío, las preguntas sugeridas devuelven respuestas y tablas precargadas en
`src/app/server/canned_genie.json`. Sirve para demostrar la capacidad sin costo ni setup, y las
cifras no contradicen al tablero porque se generan del dato real de un workspace.

Ese archivo viaja en el repositorio con las cifras de la instalación donde se generó, así que si
las de tu workspace son distintas, el chat va a decir algo que el tablero no dice. Para
regenerarlo, con la operación andando un rato:

```bash
./scripts/construir_genie_precargado.sh
databricks bundle deploy -t demo        # para que el app se lleve el JSON nuevo
```

Para instalar sin sala real:

```bash
./instalar.sh --sin-genie
```

## Verificar una sala

```bash
./scripts/verificar_genie.sh              # lista las salas del workspace
./scripts/verificar_genie.sh <SPACE_ID>   # comprueba permisos y le manda una pregunta
```

Las salas recién creadas tardan hasta medio minuto en aparecer en el listado. No es un error del
script: el índice del listado es eventualmente consistente, mientras que `get-space` sobre el id
responde de inmediato.
