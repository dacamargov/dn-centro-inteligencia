# dichter & neira · Centro de Inteligencia

Aplicación completa sobre Databricks que muestra cómo se ve la medición continua de mercado
cuando deja de entregarse en un PDF mensual y pasa a vivir en una plataforma. El caso es el de
**dichter & neira**, la firma de investigación de mercados de Centroamérica, el Caribe y la
región andina: sus auditores levantan la ejecución en el punto de venta, y esa lectura llega
en vivo a la marca que contrató el estudio.

Todo el dato es **sintético y se genera dentro de tu propio workspace**. No hay información
real de dichter & neira ni de ninguno de sus clientes.

## Instalación

Un comando deja el workspace listo: esquema, tablas, dato sembrado, ocho jobs, el dashboard
AI/BI y el app corriendo.

```bash
git clone https://github.com/dacamargov/dn-centro-inteligencia.git
cd dn-centro-inteligencia
databricks auth login          # una vez, si el CLI todavía no está autenticado
./instalar.sh
```

No hay archivo de configuración que completar. El instalador descubre el SQL Warehouse solo y
usa los valores por defecto del bundle.

### Nada está atado a un workspace

Este repositorio no conoce ningún workspace, catálogo, esquema, warehouse ni dashboard en
particular. Todo eso son parámetros, y el instalador los resuelve al correr.

```bash
# el workspace: por perfil del CLI...
./instalar.sh --profile mi-workspace

# ...o por host, sin perfil
./instalar.sh --host https://mi-workspace.cloud.databricks.com

# el resto de los assets
./instalar.sh --catalog mi_catalogo --schema centro_dn --cliente "Unilever"
```

Los valores ajustables están declarados como variables en
[`databricks.yml`](databricks.yml), cada uno con su descripción. Para ver los que van a
usarse, sin crear nada: `databricks bundle validate`.

Cuando termine, el instalador imprime la URL del app. Desde ahí, el botón **Iniciar demo**
enciende la operación — o `./encender.sh` desde la terminal.

Para desinstalar todo: `./desinstalar.sh`.

El detalle, los prerrequisitos y qué hacer cuando algo falla están en
**[docs/INSTALACION.md](docs/INSTALACION.md)**.

## La historia que cuenta

Un auditor entra a un supermercado en Ciudad de Panamá, levanta el planograma de la góndola de
lácteos y sigue su ruta. Hoy ese dato llega al cliente semanas después. Acá llega en segundos:
el tablero recalcula la disponibilidad del país, un agente detecta que la categoría cayó bajo
su meta, cruza la caída con los precios de la competencia y con lo que la gente está diciendo
en redes, y propone una acción concreta. Cuando el equipo la despacha, el copiloto de campo ya
la tiene esperando en el celular del mercaderista que abre el siguiente punto de venta.

El recorrido pantalla por pantalla está en **[docs/RECORRIDO.md](docs/RECORRIDO.md)**.

## Cómo está organizado el repositorio

Cada carpeta responde una pregunta distinta. Si buscás **qué se crea en el workspace**, mirá
`resources/`. Si buscás **qué hace** una pieza, mirá `src/`.

```
├── instalar.sh              ← el comando único
├── encender.sh / apagar.sh     enciende y pausa la operación
├── desinstalar.sh              borra todo lo que se creó
├── databricks.yml           ← el bundle: variables y targets
│
├── resources/               qué se crea en el workspace, un archivo por dominio
│   ├── 01_esquema.yml          el esquema de UC + el job que crea y siembra las tablas
│   ├── 02_generadores.yml      los 3 jobs que producen el dato
│   ├── 03_agentes.yml          los 4 agentes
│   └── 04_app.yml              el Databricks App y su configuración
│
├── src/
│   ├── esquema/                el modelo de datos (DDL) y el notebook que lo aplica
│   ├── datos/                  los generadores: visitas, precios, social
│   ├── agentes/                un archivo por agente + las herramientas compartidas
│   └── app/                    el Databricks App (FastAPI + React)
│
├── dashboards/                 el dashboard AI/BI que embebe el app
├── scripts/                    operación del día a día: limpiar, consultar, Genie
└── docs/                       instalación, recorrido, arquitectura, Lakebase, Genie
```

### Dónde vive cada feature

| Feature del app | Dato que consume | Agente que la alimenta | Ruta del backend |
|---|---|---|---|
| **Ejecución** — disponibilidad y planograma en vivo | `visitas`, `ejecucion_realtime` | `pulso_ejecucion` | `src/app/server/routes/visitas.py`, `kpis.py` |
| **Puntos de venta** — traslados entre PDV | `tiendas`, `traslados` | `red_abastecimiento` | `src/app/server/routes/pdv.py` |
| **Precios** — simulador de precio y margen | `precios_competencia` | `price_promo` | `src/app/server/routes/precios.py` |
| **Marca** — sentimiento y amplificación | `social_posts`, `campanas` | `sentimiento_marca` | `src/app/server/routes/social.py` |
| **Agentes** — cola de decisiones | `recomendaciones`, `action_log` | los cuatro | `src/app/server/routes/recommendations.py` |
| **Campo** — copiloto del mercaderista | Lakebase (Postgres) | — | `src/app/server/routes/campo.py` |

## Qué se crea en el workspace

| Recurso | Cuántos | Dónde está declarado |
|---|---|---|
| Esquema de Unity Catalog | 1 | `resources/01_esquema.yml` |
| Tablas Delta | 15 | `src/esquema/uc_schema.sql` |
| Jobs de generación de dato | 3 | `resources/02_generadores.yml` |
| Jobs de agentes | 4 | `resources/03_agentes.yml` |
| Job de instalación (a demanda) | 1 | `resources/01_esquema.yml` |
| Databricks App | 1 | `resources/04_app.yml` |
| Dashboard AI/BI | 1 | `dashboards/construir_dashboard.py` |

Nada más. No se crean catálogos, warehouses ni instancias de Postgres: el instalador usa lo
que ya existe en el workspace.

## Prerrequisitos

- **Databricks CLI** v0.240 o superior, autenticado contra un workspace con Unity Catalog.
  El recurso `apps` del bundle no existe en versiones anteriores.
- **Un SQL Warehouse** (serverless recomendado). El instalador descubre uno solo.
- **`CREATE SCHEMA`** sobre el catálogo destino.
- **`python3`** en la máquina que instala. `node`/`npm` solo si vas a tocar el frontend.
- **Foundation Model API** habilitada, para los agentes. Sin ella los agentes caen a sus
  plantillas deterministas y la demo corre igual.

## Costos

Todo es serverless y bajo demanda. Con la operación apagada (`./apagar.sh`), el warehouse en
auto-stop y el app detenido, el costo tiende a cero. Mientras corre consumen el SQL warehouse,
el compute de Apps y los jobs serverless.

**Lakebase viene apagado**, porque una instancia de Postgres cuesta aunque nadie la consulte.
La pestaña Campo muestra "no configurado" hasta que lo habilites — ver
[docs/LAKEBASE.md](docs/LAKEBASE.md).

## Aviso

`dichter & neira` es una firma real y esta aplicación se inspira en su modelo de negocio
público. Las marcas, productos, puntos de venta, precios y publicaciones sociales los inventan
los generadores de este repositorio y no representan dato real de la firma ni de sus clientes.
