# Evidencia de ejecución — Lakeflow (ingesta del dato crudo)

> Prerrequisito: **Lakeflow — ingest the raw data (synthetic or publicly available)**
> Esta evidencia es la salida real de una corrida en el workspace `fevm-dacamargovws`,
> catálogo `dacamargovws_catalog`, esquema `ditcher`.

## Qué se ejecutó

1. **Aterrizaje de dato crudo** (`src/lakeflow/00_generar_crudo.py`): StoreConnect AI
   deja 6 archivos NDJSON de auditorías de anaquel en un **Volume de Unity Catalog**
   `dacamargovws_catalog.ditcher.landing/auditorias/`. El crudo trae sólo lo observado
   por el dispositivo (tienda, SKU, caras, precio local, flags, confianza de visión),
   **sin** nada derivado.
2. **Lakeflow Declarative Pipeline** (`src/lakeflow/pipeline_auditorias.py`):
   Auto Loader ingiere los archivos → **bronze** (crudo + linaje) → **silver**
   (tipado, deduplicado, validado con expectativas, enriquecido con los maestros
   gobernados) → **gold** (`ejecucion_pdv_gold`, KPIs por tienda × categoría).

```
Volume (JSON crudo)  →  auditorias_bronze  →  auditorias_silver  →  ejecucion_pdv_gold
   Auto Loader            + linaje archivo      + expectativas DQ      KPIs de consumo
```

## Corrida del pipeline

```
pipeline_id : 1278f7fa-c607-4562-b48a-a15de61d01ee
update_id   : 0c930b35-6bd0-464a-ad92-63b5f517c61b
estado      : COMPLETED
```

## Volumen procesado por capa

```
capa    filas
------  -----
bronze  2700
silver  2700
gold     691
```

## Linaje en bronze (Auto Loader conserva el archivo de origen y el instante de ingesta)

| archivo de origen | _ingesta_ts | dispositivo | filas |
|---|---|---|---:|
| …auditoria_20261021T130954_004_7b66b8b2.json | 2026-10-21T13:27:29Z | SCAI-mobile-v4 | 156 |
| …auditoria_20261021T130954_004_7b66b8b2.json | 2026-10-21T13:27:29Z | SCAI-mobile-v5 | 161 |
| …auditoria_20261021T130954_000_fc09c702.json | 2026-10-21T13:27:29Z | SCAI-mobile-v4 | 152 |
| …auditoria_20261021T130954_000_fc09c702.json | 2026-10-21T13:27:29Z | SCAI-mobile-v5 | 170 |
| …auditoria_20261021T130954_000_fc09c702.json | 2026-10-21T13:27:29Z | SCAI-kiosk-v2  | 128 |
| …auditoria_20261021T130954_004_7b66b8b2.json | 2026-10-21T13:27:29Z | SCAI-kiosk-v2  | 133 |

## Control de calidad declarativo — expectativas del pipeline (del event log)

Cada `@dlt.expect*` queda registrada con cuántas filas pasaron. Las críticas
(`expect_or_drop`) descartan la fila; las informativas (`expect`) sólo miden.

| Expectativa | Filas OK | Filas descartadas | % que pasa |
|---|---:|---:|---:|
| `confianza_alta_ir` (informativa) | 2454 | 246 | 90.89% |
| `confianza_valida` (crítica) | 2700 | 0 | 100.00% |
| `facings_no_negativo` (crítica) | 2700 | 0 | 100.00% |
| `sku_presente` (crítica) | 2700 | 0 | 100.00% |
| `stock_con_precio` (informativa) | 2700 | 0 | 100.00% |
| `store_id_presente` (crítica) | 2700 | 0 | 100.00% |
| `tiene_observaciones` (gold) | 691 | 0 | 100.00% |
| `visit_ts_presente` (crítica) | 2700 | 0 | 100.00% |

> Lectura de negocio: 246 lecturas (9.1%) llegaron con baja confianza del modelo de
> visión; el pipeline las marca sin romper el flujo, para que calidad del dato se
> **mida** y se pueda vigilar, no se asuma.

## Muestra de la capa gold — KPIs de ejecución por tienda × categoría

Las celdas con disponibilidad 0% son justamente las que el resto del journey debe
accionar (reposición prioritaria):

```
store_id  categoria               cadena        país  obs  disp%  ejec%  sos%
PDV-0093  Culinarios              Jumbo         DO     1    0.0    0.0    0.0
PDV-0092  Bebidas No Alcohólicas  Bravo         DO     1    0.0    0.0    0.0
PDV-0075  Confitería y Snacks     Walmart       NI     1    0.0    0.0    0.0
PDV-0127  Bebidas Calientes       Tottus        PE     5    0.0    0.0    0.0
PDV-0121  Culinarios              Tía           EC     2    0.0    0.0    0.0
```

## Disponibilidad promedio por país (desde gold)

| país | celdas | disponibilidad % | ejecución % |
|---|---:|---:|---:|
| PE | 69 | 83.3 | 71.0 |
| NI | 69 | 84.5 | 63.7 |
| SV | 70 | 84.7 | 70.6 |
| EC | 68 | 84.8 | 66.9 |
| HN | 69 | 85.1 | 66.9 |
| PA | 68 | 85.8 | 71.4 |
| GT | 68 | 85.9 | 70.0 |
| DO | 70 | 86.3 | 70.2 |
| CR | 70 | 88.4 | 77.7 |
| CO | 70 | 89.4 | 72.9 |

## Integración con el resto del journey

`ejecucion_pdv_gold` vive en el **mismo esquema de Unity Catalog** que consume el
dashboard, la sala de Genie y los agentes, así que la ingesta de Lakeflow no es un
silo: es la capa gobernada de consumo que alimenta la analítica aguas abajo.
