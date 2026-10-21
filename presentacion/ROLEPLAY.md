# Roteiro de role-play — Centro de Inteligencia D&N
### Guión hablado para presentar a dos personas (negocio + técnico) · 20–30 min

> Cómo usar este guión: lee en voz alta las líneas en **"comillas"**; lo que está
> _[entre corchetes]_ son indicaciones de entrega, no para decir. Ten el deck
> (`DECK.pdf`) y el app abiertos. Lidera siempre con el **outcome**, mantén el demo
> corto, y cambia de altitud según quién pregunte.

**Personas en la sala**
- 🟦 **Negocio** (patrocinador que financia): le importan outcome, KPIs, costo, riesgo, time-to-value.
- 🟧 **Técnico** (arquitecto / data lead que convive con esto): le importan arquitectura, calidad de dato, gobierno, seguridad, integración.

**Presupuesto de tiempo**
| Bloque | Min |
|---|---|
| 1. Setup del demo (encuadre) | 2 |
| 2. El caso de valor (outcome primero) | 2 |
| 3. Recorrido tell-show-tell (6 etapas) | 10–12 |
| 4. Aterrizaje de valor | 2 |
| 5. Preguntas y objeciones | 8–12 |

---

## 1 · Setup del demo — encuadra antes de mostrar _(2 min)_

> "Gracias por el tiempo. Déjenme encuadrar antes de mostrar nada.
>
> Dichter & Neira es una firma de medición de mercado: audita la ejecución en el
> punto de venta —si el producto está en el anaquel, a qué precio, con qué espacio—
> para clientes de consumo masivo como Nestlé, en 10 países de Latinoamérica.
>
> El problema de negocio es de tiempo, no de dato: hoy el ciclo **auditar →
> reportar → accionar** tarda semanas, y para cuando el reporte llega, la venta
> perdida por un quiebre de stock ya no se recupera.
>
> Lo que les voy a mostrar es un prototipo que recorre el camino completo sobre
> Databricks: del dato crudo de la auditoría hasta una acción que el mercaderista
> ejecuta **durante la visita**. Son seis etapas; voy a ir diciendo qué muestro,
> mostrándolo, y qué significa para el negocio. Al final abrimos a preguntas."

_[Mira a la persona de negocio al decir "venta perdida"; a la técnica al decir "sobre Databricks".]_

---

## 2 · El caso de valor — outcome primero _(2 min)_ — Slide 1–2

> "El outcome en una línea: **convertir cada visita de auditoría en una decisión
> accionable en minutos, no semanas**, para recuperar ventas que hoy se pierden por
> quiebre de stock y mala ejecución.
>
> Y no hablo en abstracto. En la red que estoy midiendo —140 tiendas, 10 países—
> la disponibilidad en anaquel del cliente es **91.8%**, la tasa de quiebre **8.2%**
> y la ejecución perfecta **78.3%**. Cada punto de quiebre es venta que no sucede y
> share que se le cede a la competencia. Ese es el dinero que estamos persiguiendo."

_[Deja el número 8.2% en el aire un segundo. Es tu ancla de valor.]_

---

## 3 · Recorrido tell-show-tell _(10–12 min)_

> _[Patrón para cada etapa: **TELL** lo que vas a mostrar → **SHOW** la pantalla/dato
> → **TELL** qué significa para el negocio. No te quedes en features.]_

### Etapa 1 — Lakeflow (el dato crudo entra solo) — Slide 3
- **TELL:** "Primero, de dónde sale el dato. La auditoría llega cruda —una foto del
  anaquel por tienda y SKU."
- **SHOW:** _[app o `evidence/01_lakeflow.md`]_ "Lo ingiere un pipeline declarativo:
  crudo en un volumen, luego bronze, silver y gold. Corrió con 2 700 lecturas y, lo
  importante, con **controles de calidad**: el 9% de lecturas con baja confianza del
  reconocimiento de imagen quedan marcadas, no descartadas en silencio."
- **TELL (negocio):** "Traducción: el dato en el que basamos decisiones es confiable
  y auditable. Nadie acciona sobre basura."

### Etapa 2 — Unity Catalog (gobierno) — Slide 3
- **TELL:** "Todo esto vive gobernado en Unity Catalog."
- **SHOW:** "Claves primarias y foráneas, comentarios de negocio, permisos por rol, y
  un detalle clave: todo el dato está etiquetado como **sintético**. No hay dato real
  de cliente ni información personal en el prototipo."
- **TELL (técnico):** "Un solo plano de gobierno y linaje para dato, modelo y app;
  no hay silos ni copias sin control."

### Etapa 3 — Lakebase (servir en tiempo de visita) — Slide 3
- **TELL:** "Para accionar en la tienda necesito velocidad operacional, no analítica."
- **SHOW:** "El perfil de cada punto de venta se sirve desde Lakebase, Postgres
  gestionado, en **~1.2 milisegundos** por lectura de clave."
- **TELL (negocio):** "Eso es lo que permite que el mercaderista reciba la sugerencia
  mientras está parado frente al anaquel, no al día siguiente."

### Etapa 4 — Inteligencia: ML + Gen AI — Slide 3
- **TELL:** "Ahora lo hacemos inteligente, de dos maneras que se refuerzan."
- **SHOW (ML):** "Un modelo de machine learning predice **dónde se va a quebrar** el
  stock. Registrado y versionado en el catálogo, con un error 19% menor que el
  baseline, y ya puntuó la red entera: de 553 combinaciones tienda-categoría,
  marca **34 en riesgo ALTO**."
- **SHOW (Gen AI):** "Y cuatro agentes de IA generativa leen los datos y proponen la
  acción concreta: una visita correctiva, un ajuste de precio, un traslado de
  mercancía con su ganancia neta. No texto genérico: acción tipada que el app ejecuta."
- **TELL (negocio):** "El modelo dice dónde, los agentes dicen qué hacer. El equipo
  de campo deja de visitar 140 tiendas por igual y ataca primero las 34 que duelen."

### Etapa 5 — Genie (preguntar en español) — Slide 3
- **TELL:** "¿Y si el gerente quiere preguntar algo que no está en el tablero?"
- **SHOW:** _[Genie en vivo o `evidence/06_genie.md`]_ "Le pregunto en español:
  '¿cuáles son las 5 tiendas con peor disponibilidad?' — y Genie genera el SQL sobre
  las tablas gobernadas y responde con los números. Sin tiquete al área de datos."
- **TELL:** "Autoservicio real para negocio, sobre el mismo dato gobernado."

### Etapa 6 — El app (todo en una pantalla) — Slide 3
- **TELL:** "Y todo esto se junta en una sola app para el usuario de negocio."
- **SHOW:** "KPIs de ejecución, recomendaciones de los agentes, el copiloto de campo,
  Genie. Está vivo, con datos fluyendo ahora mismo."
- **TELL:** "Una superficie para el patrocinador y el dueño de dominio; nadie tiene
  que entender la plomería de abajo."

---

## 4 · Aterrizaje de valor _(2 min)_ — Slides 4–5

> "Entonces, ¿qué significa esto en los números que a ustedes les importan?
>
> Disponibilidad del 91.8% hacia una meta de **96%**. Ejecución perfecta del 78.3%
> hacia **88%**. Y el ciclo de insight de **semanas a minutos**.
>
> Puesto en dinero, con un supuesto explícito: si la mitad de la venta que hoy se
> pierde por quiebre es recuperable con reposición oportuna, en una red de **US$100
> millones** eso son del orden de **US$4 millones al año** recuperables —antes de
> contar la productividad del equipo de campo. Es un modelo ilustrativo sobre datos
> sintéticos; con sus ventas reales lo afinamos en cinco minutos.
>
> Y no es una maqueta: toda la evidencia de que esto corrió —el pipeline, el modelo,
> las latencias, las respuestas de Genie— está en el repositorio como texto."

---

## 5 · Preguntas y objeciones — banco de respuestas

> _[Regla de oro de "reading the room": primero responde a la altitud de quien
> pregunta, luego, si hace falta, baja o sube. Si el técnico pide detalle, dáselo
> sin perder al de negocio: cierra con una frase de impacto. Si el de negocio
> pregunta, no lo ahogues en arquitectura.]_

### 🟦 Objeciones de NEGOCIO

**"Esto suena caro. ¿Cuánto cuesta operarlo?"**
> "A la altura correcta: el costo es bajo y controlado porque todo es serverless
> —se paga por uso, no por infraestructura prendida— y la base operacional es la
> instancia más chica. El verdadero marco no es el costo, es el retorno: estamos
> persiguiendo millones en venta recuperable contra un costo de operación de orden
> de miles al mes. La relación no está cerca."
> _[Si el técnico quiere, añade:]_ "Y puedo apagar Lakebase cuando no se usa; el
> gasto no corre 24/7 si no hace falta."

**"¿Cuánto tardo en ver valor? No quiero un proyecto de un año."**
> "Lo que vieron ya corre. El camino a producción es un piloto de **60 días** en un
> país: conectamos el feed real de auditorías a la misma ingesta, medimos OSA antes
> y después, y el valor se demuestra con datos, no con promesas. No hay reconstrucción."

**"¿Qué riesgo corro si esto falla o da una recomendación mala?"**
> "Tres capas de control. Uno, calidad de dato gobernada: lo de baja confianza se
> marca, no se acciona a ciegas. Dos, el humano decide: el agente **propone**, el
> mercaderista o el gerente **aprueban**. Tres, todo queda auditado. El sistema
> acelera la decisión, no la quita."

**"¿Por qué Databricks y no lo que ya tengo?"**
> "Porque el valor está en que las seis piezas vivan en **una plataforma gobernada**:
> el mismo dato que entrena el modelo lo consulta Genie y lo sirve el copiloto, sin
> copias ni integraciones frágiles. Armar esto con cinco herramientas distintas es
> donde los proyectos mueren."

### 🟧 Objeciones TÉCNICAS

**"¿Qué pasa con la calidad del dato? La visión por imagen se equivoca."**
> "Exacto, por eso es explícito. El pipeline aplica expectativas declarativas: las
> lecturas con confianza baja —en mi corrida, 9%— se etiquetan y se miden, no se
> cuelan. Las reglas duras, como que falte el identificador de tienda, descartan la
> fila. La calidad es un control del pipeline, no un supuesto."
> _[Sube la altitud para cerrar:]_ "Para el negocio eso significa que el KPI que ve
> en pantalla es defendible."

**"¿Cómo está la arquitectura? ¿No es un montón de piezas pegadas?"**
> "Es un medallón clásico —bronze, silver, gold— con Auto Loader para ingesta
> incremental, todo declarado como Asset Bundle, así que es reproducible e
> infra-como-código. El modelo se registra en el catálogo con alias de campeón; el
> serving operacional sale a Postgres gestionado. Un solo catálogo gobierna dato,
> modelo y permisos."

**"Seguridad y datos de cliente. ¿Qué me garantizas?"**
> "Primero, en el prototipo **no hay dato real de cliente ni información personal**:
> todo es sintético y está etiquetado así en el catálogo. En producción, el gobierno
> es el mismo mecanismo: permisos por rol en Unity Catalog, el app corre con su
> propio service principal con privilegios acotados, y las credenciales de la base
> son de vida corta, no quedan en el código."

**"¿Cómo integro mi feed real de auditorías?"**
> "Por el mismo punto de entrada: hoy aterriza en un volumen de Unity Catalog y el
> Auto Loader lo toma incremental. Cambiar el generador sintético por tu feed real
> —archivos, cola, o API— no toca el resto del pipeline. Silver, gold, modelo, Genie
> y app siguen igual."

**"El modelo tiene un R² bajo. ¿Confío en eso?"**
> "Buena observación. El modelo no pretende predecir el valor exacto del quiebre,
> sino **ordenar** el riesgo para priorizar la ruta —y ahí bate al baseline en 19%.
> Además no es la única señal: Genie y los agentes coinciden en las mismas tiendas
> críticas, como PDV-0111. Tres técnicas independientes apuntando al mismo lugar dan
> más confianza que un solo número."

---

## 6 · Recordatorios de entrega

- **Lidera con el outcome** en cada bloque; la feature es el medio, no el mensaje.
- **Cambia de altitud a media respuesta**: detalle para el técnico, cierre de
  impacto para el negocio. Practica la frase puente: _"…y lo que eso significa para
  el negocio es…"_.
- **Maneja el pushback con calma**: reconoce la pregunta ("buena observación"),
  responde con un dato, no a la defensiva.
- **Demo corto**: si algo tarda en cargar, narra el valor mientras tanto; no te
  quedes en silencio mirando la pantalla.
- **Cierra pidiendo el siguiente paso**: el piloto de 60 días en un país.
