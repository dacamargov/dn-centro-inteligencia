# Centro de Inteligencia D&N
### De la auditoría de anaquel a la acción, el mismo día

**Outcome de negocio en una línea:** convertir cada visita de auditoría en una
decisión accionable en **minutos** —no semanas— para recuperar ventas perdidas por
quiebre de stock y mala ejecución en el punto de venta.

> Datos 100% sintéticos para la demo. "Nestlé" y "Dichter & Neira" se usan como
> contexto narrativo; ningún dato proviene de un sistema real.

---

## 1 · El problema (medido en la propia red)

Dichter & Neira audita la ejecución en el punto de venta para sus clientes CPG. Hoy
el dato existe, pero el ciclo **auditar → reportar → accionar** tarda semanas, y para
entonces la venta ya se perdió.

En la red medida (cifras reales del prototipo):

| Señal | Hoy |
|---|---|
| Tiendas / países / SKUs del cliente | 140 / 10 / 57 |
| **Disponibilidad en anaquel (OSA)** | **91.8 %** |
| **Tasa de quiebre** | **8.2 %** |
| **Ejecución perfecta** | **78.3 %** |

Cada punto de quiebre es venta que no ocurre y share que se cede a la competencia.

---

## 2 · El outcome: de dato crudo a acción, en una sola plataforma

El prototipo recorre el journey completo sobre Databricks:

```
Auditoría cruda  →  Lakeflow  →  Unity Catalog  →  Lakebase        →  App de negocio
(foto de anaquel)   (ingesta)   (gobierno)         (copiloto PDV)       (una pantalla)
                                      │
                                      ├─ ML: predice dónde se va a quebrar
                                      ├─ Gen AI: 4 agentes proponen la acción
                                      └─ Genie: pregúntale en español
```

El mercaderista recibe la sugerencia **durante la visita** (lectura por clave en ~1 ms
desde Lakebase); el gerente ve el tablero y los agentes ya priorizaron qué atacar.

---

## 3 · Impacto en los KPIs del comprador

| KPI del comprador | Hoy | Con el Centro de Inteligencia | Palanca |
|---|---|---|---|
| Disponibilidad en anaquel (OSA) | 91.8 % | **96 %** (meta) | ML prioriza las 34 combinaciones tienda×categoría en riesgo ALTO |
| Ejecución perfecta | 78.3 % | **88 %** | Agente de pulso de ejecución → visita correctiva dirigida |
| Tiempo auditoría → acción | semanas | **minutos** | Agentes + copiloto en tiempo de visita |
| Productividad de la visita | ruta plana | **ruta por riesgo** | Perfil de PDV servido por Lakebase |
| Share of shelf del cliente | 27–30 % | **+2–3 pts** | Agente de precio/promo y de abastecimiento |

---

## 4 · Modelo de valor (ilustrativo, supuestos explícitos)

Regla del sector: aproximadamente la mitad de la venta que se pierde por quiebre es
**recuperable** con reposición oportuna.

```
Ventas perdidas por quiebre ≈ Ventas_red_anual × tasa_quiebre(8.2%)
Recuperable                 ≈ Ventas perdidas × 50%
```

| Supuesto: ventas anuales del cliente en la red medida | Venta recuperable / año |
|---|---|
| US$ 50 M | ~US$ 2.0 M |
| US$ 100 M | ~US$ 4.1 M |
| US$ 250 M | ~US$ 10.3 M |

A esto se suma el ahorro de llevar el ciclo de insight de semanas a minutos y la
mayor productividad del equipo de campo. *(Cifras ilustrativas sobre datos sintéticos.)*

---

## 5 · Para quién

**Patrocinador ejecutivo** — Director Comercial / VP de Retail Execution (cliente CPG)
y Dirección General de D&N:
- Recupera venta hoy perdida por quiebre y protege el share of shelf.
- Diferencia el servicio de medición: de "reporte" a "plataforma de acción".
- Un solo tablero gobernado, con costo bajo control (serverless + Lakebase CU_1).

**Dueño de dominio** — Jefe de Trade Marketing / Field Operations / Category Manager:
- Lista de acción priorizada por riesgo, no 140 tiendas por igual.
- El mercaderista sabe qué hacer **en la tienda**, no al día siguiente.
- Pregunta en lenguaje natural (Genie) sin depender de analítica.

---

## 6 · Prueba de que corre (no es un mockup)

Toda la evidencia de ejecución está en el repositorio, como texto legible:

- **Lakeflow:** pipeline `COMPLETED` — bronze 2 700 → silver 2 700 → gold 691, con
  controles de calidad medidos.
- **Unity Catalog:** PK/FK (RELY), comentarios, tags (`dato=sintetico`), GRANTs.
- **Lakebase:** 140 perfiles, lectura por clave p50 **1.22 ms**.
- **ML:** modelo `@campeon` en UC, MAE 0.0551 (−19 % vs baseline), 553 predicciones.
- **Gen AI:** 4 agentes `success` con recomendaciones reales y acción tipada.
- **Genie:** 3 preguntas en español → SQL correcto → cifras.
- **App:** 33/33 rutas `200`, Genie `live`, Lakebase conectado.

→ Ver `evidence/00_INDEX.md`. App vivo:
`https://dn-centro-inteligencia-7474652595969633.aws.databricksapps.com`

---

## 7 · Cómo se construyó — IA como multiplicador

Construido en **Cursor** con un **agente de IA (Claude)** como pair-programmer,
manejando Databricks por el **MCP server, el CLI y Asset Bundles** (infra-como-código).

**Dónde la IA fue el multiplicador:**
- **Scaffolding** del journey completo (pipeline DLT, notebook de ML, gobernanza,
  backend/frontend) desde la intención — minutos, no días.
- **Loop de depuración contra el entorno vivo:** el agente desplegaba, leía el event
  log del pipeline y corregía (streaming vs. MV, referencia ambigua, cambio de tipo
  de dataset, `Decimal` en MLflow, política de tags de UC).
- **Evidencia como texto:** consultó `information_schema`, Genie, Lakebase y las rutas
  del app y escribió los resultados reales a `evidence/`.

**Trade-offs deliberados al construir con IA:**
- **La IA escribe; nada se publica sin verificar** — cada artefacto se validó contra
  resultados en vivo.
- **La IA no decide la plata:** la economía (haversine, umbrales, ventana de
  decaimiento, índice de precio por 100 g/ml, denominador de share of shelf) es **SQL
  determinista**; el LLM solo elige qué candidato ya calculado escalar.

> Detalle completo en `docs/COMO_SE_CONSTRUYO.md` (incluye las historias de iteración
> real: cola desbordada → ventana de decaimiento; bug del denominador de SoS; fix de
> threading del feed en vivo; presupuesto de latencia de Lakebase).

---

## 8 · Próximos pasos

1. Conectar el feed real de auditorías (reemplazar el generador sintético) vía la
   misma ingesta de Lakeflow.
2. **Ya cerrado:** el perfil servible se deriva de la capa gold (`pdv_perfil_gold`,
   con PK + Change Data Feed), no de un recálculo paralelo — cero deriva entre
   entrenamiento y serving. El paso a *synced table* continua gestionada es un solo
   comando donde el metastore lo permita (ver `evidence/08_gold_serving_handoff.md`).
3. Pilotar en un país con un equipo de campo y medir OSA antes/después a 60 días.
