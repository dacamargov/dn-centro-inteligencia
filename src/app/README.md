# El app (FastAPI + React)

El Databricks App del Centro de Inteligencia. Para instalar todo desde la raíz del repositorio
es `./instalar.sh`; este documento cubre el desarrollo del app.

## Stack

- **Backend**: FastAPI + uvicorn (Python 3.11+)
- **Consultas a Unity Catalog**: `databricks-sql-connector` contra un SQL Warehouse
- **Estado operacional**: Lakebase (Postgres), apagado por defecto — ver `../../docs/LAKEBASE.md`
- **Frontend**: React 18 + Vite + TypeScript + Tailwind
- **Auth**: doble modo — perfil del CLI en local, service principal dentro de Databricks Apps

No hay ningún id incrustado. Toda la configuración llega por variables de entorno, que declara
el bundle en `resources/04_app.yml`.

## Estructura

```
src/app/
├── app.py                   entrada FastAPI: monta los routers y sirve frontend/dist
├── requirements.txt         lo que instala Databricks Apps al desplegar
├── pyproject.toml           proyecto uv, para el desarrollo local
├── server/
│   ├── config.py            auth doble modo y lectura de variables de entorno
│   ├── uc.py                helper del SQL warehouse
│   ├── lakebase.py          helper de Postgres
│   ├── llm.py               llamadas al Foundation Model
│   ├── campo_flujo.py       la jornada simulada, en un hilo del servidor
│   ├── canned_genie.json    respuestas del modo demostración de Genie
│   └── routes/              una ruta por feature (ver la tabla de abajo)
└── frontend/
    ├── src/pages/           una página por pestaña
    ├── src/components/      componentes compartidos
    ├── src/lib/             cliente de la API, formato, cálculo de precio y rutas
    └── dist/                el compilado — esto es lo que se despliega
```

### Rutas por feature

| Ruta | Sirve a |
|---|---|
| `routes/kpis.py` | los KPIs del encabezado de Ejecución |
| `routes/visitas.py` | el ticker de lecturas de anaquel |
| `routes/targets.py`, `targets_drill.py` | Meta vs Realizado y su drill-down |
| `routes/pdv.py` | el mapa de puntos de venta y los traslados |
| `routes/precios.py` | el simulador de precio |
| `routes/social.py` | sentimiento de marca y campañas |
| `routes/recommendations.py` | la cola de recomendaciones de los agentes |
| `routes/campo.py` | el copiloto de campo (Lakebase) |
| `routes/lakebase_studio.py` | el panel de latencia y el flujo continuo |
| `routes/demo.py` | el botón "Iniciar demo" y "Limpiar datos" |
| `routes/genie.py` | el chat, real o precargado |
| `routes/dashboard.py` | el dashboard AI/BI embebido |

## Desarrollo local

```bash
cd src/app
uv sync
export CATALOG=main SCHEMA=ditcher_neira WAREHOUSE_ID=<id> CLIENTE="Nestlé"
export DATABRICKS_PROFILE=<tu-perfil>
uv run uvicorn app:app --reload --port 8000

# en otra terminal, con hot reload del frontend
cd src/app/frontend && npm install && npm run dev
```

Fuera de Databricks Apps, el backend usa tu perfil del CLI. Adentro, el SDK detecta solo las
credenciales del service principal.

## Desplegar un cambio

```bash
cd src/app/frontend && npm run build && cd ../../..
databricks bundle deploy -t demo
```

El bundle sube `frontend/dist` y deja las fuentes afuera: si editás un `.tsx` y no reconstruís,
el app sigue sirviendo la versión anterior.
