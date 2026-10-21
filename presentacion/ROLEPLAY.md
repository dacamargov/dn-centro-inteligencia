# Roteiro de role-play — Centro de Inteligencia D&N
### Guión ejecutivo · 20–30 min · dos personas en la sala

**Personas**
- 🟦 **Gerente de anaquel** — dueño del resultado comercial. Le importa: venta
  perdida por quiebre, qué tiendas arreglar primero, productividad del equipo de campo.
- 🟧 **Operador de la plataforma** — data lead que la mantiene. Le importa:
  calidad de dato, gobierno, costo, integración, confiabilidad, seguridad.

**Regla de oro:** lidera con el **outcome**, habla en **números**, frases cortas.
Responde a la altura de quien pregunta; cierra siempre con impacto de negocio.

---

## Apertura — 30 segundos

> "Dichter & Neira mide ejecución en anaquel para marcas como Nestlé en 10 países.
> El problema no es el dato, es el tiempo: **auditar → reportar → accionar tarda
> semanas, y la venta perdida ya no vuelve**.
> Les muestro cómo lo bajamos a **minutos**. Seis etapas, cortas. Al final, preguntas."

---

## Valor en 3 números — 30 segundos _(Slide 2)_

> "En esta red: disponibilidad **91.8%**, quiebre **8.2%**, ejecución perfecta
> **78.3%**. Cada punto de quiebre es venta que no ocurre. Eso es lo que recuperamos."

---

## Demo — en lenguaje de negocio _(3–4 min, Slide 3)_

> _[Habla de lo que el gerente VE y GANA. Cero jerga técnica. Un gerente de tienda
> no sabe —ni le importa— qué es Lakeflow o un catálogo; le importa la venta.
> Los nombres técnicos solo salen si el operador pregunta "¿cómo?" (abajo).]_

1. "La **foto de la auditoría entra sola y se limpia**: lo que la cámara leyó mal se
   marca aparte, así el número en el que confías es real."
2. "Cada tienda tiene su **ficha**, y aparece **al instante** cuando el mercaderista
   la abre en la visita."
3. "El sistema **predice dónde se va a quebrar el producto antes de que pase**, y le
   dice al mercaderista **exactamente qué corregir en ese anaquel**."
4. "Así el equipo ataca primero las **34 tiendas críticas**, no las 140 por igual."
5. "Y si quieres algo que no está en la pantalla, **le preguntas en español** —'¿cuáles
   son mis 5 peores tiendas?'— y te responde al momento, sin pedirle nada a sistemas."
6. "Todo esto en **una sola pantalla**, en vivo."

> **Traducción técnica — SOLO si el operador pregunta "¿cómo está hecho?"**
> (1) Lakeflow con controles de calidad · (2+6) Unity Catalog gobierna todo y el app
> lo expone · (3) perfil servido desde Lakebase en ~1 ms · (3-4) modelo de ML +
> agentes de Gen AI · (5) Genie traduce la pregunta a SQL. _[Ver `evidence/`.]_

---

## Aterrizaje — 30 segundos _(Slides 4–5)_

> "Esto mueve sus KPIs: disponibilidad **91.8% → 96%**, ejecución **78.3% → 88%**,
> ciclo de **semanas a minutos**. En plata: en una red de US$100M, del orden de
> **US$4M al año** recuperables. Y no es maqueta: toda la evidencia de que corrió
> está en texto en el repo."

---

## Banco de objeciones — respuestas cortas, a la altura de quien pregunta

### 🟦 Gerente de anaquel

**"¿Y si la recomendación está mal?"**
> "El agente **propone**, usted **aprueba**. El dato de baja confianza se marca, no se
> acciona a ciegas. Todo queda auditado."

**"Tengo 140 tiendas y poco tiempo de ruta."**
> "Por eso priorizamos: el modelo le da **34 tiendas en riesgo alto** primero. Deja de
> tratar todas por igual."

**"¿Esto me sirve en la visita o es otro reporte?"**
> "En la visita. El mercaderista abre el app y ve **qué corregir en ese anaquel**, al
> instante — no al día siguiente."

**"¿Qué gano en el número?"**
> "Recuperar venta que hoy se pierde por quiebre y proteger su **share of shelf**.
> Cuatro puntos de disponibilidad es dinero directo."

### 🟧 Operador de la plataforma

**"¿Calidad del dato? La visión por imagen falla."**
> "Es explícito: las lecturas de baja confianza —9% en mi corrida— se **marcan y se
> miden**, no se cuelan. Las reglas duras descartan la fila. → El KPI es defendible."

**"¿Arquitectura? ¿No son piezas pegadas?"**
> "Medallón bronze-silver-gold, todo como **Asset Bundle** (infra-como-código),
> reproducible. Un solo catálogo gobierna dato, modelo y permisos."

**"Seguridad y datos de cliente."**
> "Sin dato real ni PII: todo sintético y etiquetado así. En producción, permisos por
> rol en Unity Catalog, el app con service principal acotado, credenciales de vida corta."

**"¿Costo de operar?"**
> "Serverless: se paga por uso. La base operacional es la instancia mínima. Retorno en
> millones contra costo en miles."

**"¿Cómo integro mi feed real de auditorías?"**
> "Por el mismo punto de entrada. Cambiar el generador por tu feed real no toca el
> resto: silver, gold, modelo, Genie y app siguen igual. El perfil servible ya se
> alimenta de la capa gold, sin recálculo paralelo."

**"¿Esto lo construyeron a mano o con IA?"**
> "Con IA como multiplicador —Cursor + agente sobre Databricks— pero **nada se publicó
> sin verificar contra datos en vivo**, y la economía (traslados, índice de precio,
> share of shelf) es **SQL determinista**: el modelo no decide la plata."

---

## Entrega

- Lidera con outcome; la feature es el medio.
- Cambia de altura a media respuesta: detalle al operador, cierre de negocio al gerente.
- Pushback: reconócelo con un dato, no a la defensiva.
- Cierra pidiendo el **piloto de 60 días en un país**, midiendo disponibilidad antes/después.
