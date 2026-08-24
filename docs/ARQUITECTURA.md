# Arquitectura

Cómo encajan las piezas, y por qué están donde están. Para el detalle de instalación,
[INSTALACION.md](INSTALACION.md); para lo que ve el usuario, [RECORRIDO.md](RECORRIDO.md).

## El recorrido del dato

```
   fuentes                       lakehouse                    decisión              servicio
 ─────────────              ───────────────────           ──────────────         ─────────────

 reconocimiento  ─┐
 de imagen        │                                     ┌─ pulso_ejecucion ─┐
 (anaquel)        │      ┌──────────────────────┐       │  price_promo      │
                  ├─────►│  Unity Catalog       │──────►│  sentimiento_marca│
 captura de       │      │  <catálogo>.<esquema>│       │  red_abastecimiento
 precios          │      │                      │       └─────────┬─────────┘
                  │      │  maestros            │                 │
 escucha          ─┘     │   paises, tiendas,   │                 │ recomendaciones
 social                  │   productos, metas   │                 ▼
                         │                      │       ┌───────────────────────┐
                         │  ventana viva        │◄──────│  Databricks App       │
                         │   visitas, precios,  │       │  React + FastAPI      │
                         │   social_posts,      │       │                       │
                         │   traslados,         │       │  decisión humana:     │
                         │   recomendaciones,   │       │  despachar/descartar  │
                         │   action_log         │       └───────────┬───────────┘
                         └──────────┬───────────┘                   │
                                    │                              │ <100 ms
                                    │ publica perfiles              ▼
                                    └────────────────────►┌──────────────────────┐
                                                          │ Lakebase (Postgres)  │
                                                          │  pdv_perfiles        │
                                                          │  sugerencias_log ────┼─┐
                                                          └──────────────────────┘ │
                                                                                   │
                          el ciclo cierra: lo que el mercaderista corrigió ────────┘
                          vuelve al lakehouse y la tasa de ejecución se mide
```

## Las cuatro capas y dónde vive cada una

| Capa | Qué hace | Dónde está |
|---|---|---|
| **Fuentes** | Tres generadores simulan lo que en producción serían tres sistemas distintos: el reconocimiento de imagen del auditor, la captura de precios en cadena y la escucha social. | `src/datos/`, declarados en `resources/02_generadores.yml` |
| **Lakehouse** | Un esquema de Unity Catalog con 15 tablas: maestros que se siembran una vez y una ventana viva que se poda sola. | `src/esquema/uc_schema.sql`, declarado en `resources/01_esquema.yml` |
| **Decisión** | Cuatro agentes con tool-calling sobre el lakehouse. Cada uno levanta como máximo una recomendación por tick. | `src/agentes/`, declarados en `resources/03_agentes.yml` |
| **Servicio** | El app sirve el tablero desde el warehouse, y el copiloto de campo desde Postgres. | `src/app/`, declarado en `resources/04_app.yml` |

## Por qué dos caminos de lectura

El tablero consulta Unity Catalog a través del SQL warehouse. Eso está bien para una pantalla
que se refresca cada pocos segundos y agrega millones de filas.

El copiloto de campo no puede hacer eso. Un mercaderista parado frente al anaquel con el celular
en la mano tiene diez segundos de paciencia, y el plan de su punto de venta es una lectura por
clave, no una agregación. Ese camino va a Lakebase: el perfil del PDV se publica desde la capa
gold a Postgres y se lee en menos de 100 ms.

Es la distinción entre analítica y servicio operacional, y es la razón por la que están
separados. Ver [LAKEBASE.md](LAKEBASE.md).

## Dónde termina el SQL y dónde empieza el modelo

Los agentes no calculan la plata. Toda la economía —qué SKU está en quiebre, qué PDV tiene
sobrestock del mismo SKU, cuánto cuesta el traslado, cuál es la ganancia neta— es SQL
determinista, en las herramientas que el agente puede invocar.

El modelo hace dos cosas: decide qué herramientas consultar, y escribe la explicación. Esa
frontera no es un detalle de implementación: es lo que hace que el número del panel sea
auditable y reproducible. Si el modelo calculara la ganancia, dos corridas sobre el mismo dato
darían dos cifras distintas y el panel no serviría para decidir nada.

Cada agente tiene un tope de vueltas de tool-calling. Sin él, un modelo que se confunde puede
quedarse consultando herramientas hasta agotar el tiempo del job.

## El estado de una recomendación

Una recomendación nace en `recomendaciones` y su decisión queda en `action_log`. Los estados son
cuatro y el tablero los muestra todos: propuesta, despachada, descartada y vencida.

El vencimiento es importante y es fácil de olvidar: una propuesta vale lo que vale la lectura de
anaquel que la originó. Pasada esa ventana el quiebre puede estar resuelto y el sobrestock
vendido. Sin vencimiento la cola deja de ser una cola — en una corrida de una noche llegó a
5.600 filas muertas.

## Tablas persistentes y ventana viva

| Persistentes — sobreviven a la limpieza | Transitorias — se vacían |
|---|---|
| `paises`, `fabricantes`, `productos`, `tiendas`, `metas_categoria` | `visitas`, `ejecucion_realtime`, `precios_competencia`, `social_posts`, `recomendaciones`, `runs`, `action_log`, `acciones_campo`, `campanas`, `traslados` |

Los generadores podan su propia ventana en cada tick, así que las tablas no crecen sin límite
mientras la operación corre. `scripts/limpiar.sh` (y el botón **Limpiar datos** del app) vacían
las transitorias de golpe, para empezar una presentación en cero.

## Identidad y permisos

```
  quien instala  ──► crea el esquema, los jobs, el app y el dashboard
                     (con su propia identidad: run_as del bundle)

  el app         ──► corre con su propio service principal
                     · CAN_USE sobre el warehouse   (recurso adjunto)
                     · USE CATALOG + USE SCHEMA + SELECT + MODIFY sobre el esquema
                     · CAN_MANAGE sobre los jobs    (para el botón "Iniciar demo")

  el usuario     ──► entra al app con su sesión del workspace; el gateway reenvía
                     su identidad en X-Forwarded-Email
```

Los dos primeros grants los otorga `instalar.sh` en su último paso, porque el service principal
no existe hasta que el app existe. Es la única parte de la instalación que no puede ser
declarativa.

## Por qué un bundle y no scripts

Todo lo que se crea en el workspace está declarado en `resources/`, un archivo por dominio. Eso
compra tres cosas concretas:

- **Un inventario legible.** Para saber qué toca la instalación no hay que leer bash: se leen
  cuatro YAML.
- **Desinstalación real.** `bundle destroy` sabe qué creó y lo borra. Un script imperativo
  necesita un segundo script que adivine.
- **Instalaciones paralelas.** El target `pruebas` cambia esquema, app y prefijo de jobs, así que
  se puede probar un cambio del repositorio al lado de una instalación en uso.

Lo que quedó fuera del bundle quedó afuera por una razón, no por olvido: las tablas Delta (el
bundle no las maneja, así que las crea un job con el DDL del repositorio) y el dashboard de
Lakeview (su definición son datasets con el catálogo y el esquema adentro, que hay que resolver
antes de crearlo).
