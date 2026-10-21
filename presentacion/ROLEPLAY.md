# Roteiro de role-play — Centro de Inteligencia D&N
### Párrafos exactos para leer · 20–30 min · dos personas en la sala

**Personas que preguntan:** 🟦 **gerente de anaquel** (dueño del resultado comercial) ·
🟧 **operador de la plataforma** (perfil técnico).
**Quién responde:** tú lideras con el negocio; **el detalle técnico lo toma Shreya**.
Ante el gerente, responde siempre primero con beneficio operativo y dinero, y si pide
el "cómo" por dentro, pásalo a Shreya.
**Cómo usar:** lee de corrido los párrafos en **negrita**; lo que está _[entre
corchetes]_ son indicaciones, no se leen.

---

## 1 · Apertura _(≈30 s)_

> _[Mirando a los dos, con calma.]_

**"Gracias por el tiempo. Dichter & Neira mide la ejecución en el punto de venta para
marcas como Nestlé en diez países. Su problema no es falta de datos; es el tiempo: hoy
auditar, reportar y recién después actuar toma semanas, y un quiebre que se ve dos
semanas tarde ya es venta perdida. Es como enterarse de que su anaquel estaba vacío
cuando el cliente ya compró la marca de al lado. Lo que les voy a mostrar cierra ese
tiempo de semanas a minutos. Vamos a ver tres cosas: cómo entra la foto del auditor,
cómo se priorizan solas las tiendas en riesgo, y cómo usted consulta en español. Voy
mostrando y al final quedamos en preguntas."**

---

## 2 · Valor en tres números _(≈30 s, Slide 2)_

> _[Deja caer el 8% y haz una pausa corta.]_

**"Pongámosle tamaño al problema con nuestra propia red. Disponibilidad en anaquel
noventa y dos por ciento, quiebre ocho, ejecución perfecta setenta y ocho. Ese ocho por
ciento de quiebre, sobre una red de cien millones de dólares, son unos ocho millones de
venta en riesgo cada año. Esa es la vara contra la que mido todo lo que sigue."**

---

## 3 · Demo _(≈60 s, mostrando la pantalla, Slide 3)_

> _[Léelo de corrido mientras recorres el app. Cero jerga técnica. Tell–Show–Tell:
> anuncia las tres cosas, muéstralas, y recápalas enlazadas al negocio.]_

**"Miren lo que ve el negocio en un solo lugar, en estas tres cosas. Primero, la foto
del auditor entra sola y se limpia: lo que la cámara leyó dudoso se aparta, así que el
número es real, no ruido. Segundo, el sistema predice dónde se va a quebrar el producto
antes de que pase y le dice al mercaderista qué corregir en ese anaquel —en vez de
recorrer las 140 tiendas por igual, ataca primero las 34 que están en riesgo real.
Tercero, usted pregunta en español —'¿cuáles son mis cinco peores tiendas esta
semana?'— y le responde al momento, sin pedirle nada a sistemas. Esas tres cosas, una
sola pantalla, en vivo con los datos de hoy: dato confiable, prioridad automática y
respuesta inmediata. Eso es lo que convierte la auditoría en venta recuperada."**

> **Detalle técnico — lo toma Shreya, solo si el operador pregunta "¿cómo está
> hecho?":** la foto entra y se valida con **Lakeflow**; todo queda gobernado en
> **Unity Catalog** y se expone en un **Databricks App**; la ficha se sirve desde
> **Lakebase** en ~1 ms; la predicción es un **modelo de ML** y las acciones son
> **agentes de Gen AI**; la pregunta en español la traduce a SQL **Genie**. _[Detalle
> en `evidence/`.]_

---

## 4 · Aterrizaje _(≈30 s, Slides 4–5)_

> _[Cierra la parte expositiva, recapitula las tres cosas y abre a preguntas.]_

**"Recapitulando: dato confiable, prioridad automática y respuesta en español. Eso mueve
sus números —disponibilidad del noventa y dos hacia noventa y seis, ejecución perfecta
del setenta y ocho hacia ochenta y ocho, y el ciclo de insight de semanas a minutos. En
plata: de esos ocho millones en riesgo, recuperar la mitad —cuatro puntos de
disponibilidad— son del orden de cuatro millones al año, concentrados en sus categorías
de mayor rotación. Y no es una maqueta: la prueba de que corrió está en el repositorio.
Con eso, les abro a preguntas."**

---

## 5 · Objeciones — lee la respuesta exacta según quién pregunte

### 🟦 Si el gerente de anaquel dice…

**"¿Y si la recomendación está mal?"**
> **"Usted aprueba; nada se ejecuta solo, y el dato dudoso se aparta. Lo peor que puede
> pasar es visitar una tienda que no era la más urgente: no se pierde plata, se pierde
> una visita. Y todo queda registrado para revisarlo."**

**"Tengo 140 tiendas y poco tiempo de ruta."**
> **"Por eso prioriza: las 34 en riesgo real primero, no las 140 por igual. Su equipo
> rinde más con las mismas horas."**

**"¿Esto me sirve en la visita o es otro reporte más?"**
> **"En la visita. El mercaderista abre la tienda en el celular y ve qué corregir en ese
> anaquel en el momento, no al día siguiente cuando ya se fue."**

**"¿Qué gano yo en el número?"**
> **"Recupera venta que hoy se pierde por quiebre y protege su espacio frente a la
> competencia. Cuatro puntos de disponibilidad sobre su red son del orden de cuatro
> millones al año, en sus categorías de mayor rotación."**

**"Si actuamos en minutos en vez de semanas, ¿cuánto de ese ocho por ciento recuperamos?"**
> **"No el ocho completo: cuando el producto se agota, parte de esa venta ya se perdió.
> Lo que cambia es el tiempo con el anaquel vacío, que pasa de días a horas, y además el
> modelo anticipa el quiebre antes de que ocurra. De forma conservadora eso recorta el
> quiebre a la mitad —cuatro puntos—, que sobre ocho millones en riesgo son unos cuatro
> millones al año. Y lo medimos con su propio número en el piloto, no de fe."**

**"¿Cuánto tiempo necesito para ver el retorno?"**
> **"Semanas, no meses. Lo que vieron ya corre, así que arrancamos un piloto de sesenta
> días en un país. Apenas el equipo visita primero las tiendas en riesgo, la
> disponibilidad sube y eso es venta recuperada casi inmediata. A los sesenta días tiene
> el retorno medido con su propio número; con ese impacto, la inversión se paga en el
> primer trimestre."**

**"¿Y cómo hacemos para saber el stock de todas las tiendas?"**
> **"De la propia auditoría: en cada visita se registra, producto por producto, si está
> en el anaquel, cuántas caras tiene y a qué precio. No dependemos de que el retailer
> abra su inventario; lo medimos en el piso de venta."**

**"Si lo implemento hoy, ¿cuántos meses hasta que mi equipo esté funcional y produzca valor real?"**
> **"Semanas para el primer valor, no meses. La plataforma ya está construida;
> implementar es conectar su feed y ajustar los umbrales a su realidad. El entrenamiento
> es de una sesión: la pantalla le dice al gerente qué priorizar, no le exige saber de
> tecnología. Los diez países se completan por olas en un trimestre, pero el valor
> empieza en el piloto, no al final."**

**"Si funciona tan bien, ¿por qué no lo veo ya en el mercado? ¿Quién más confía en esto?"**
> **"La tecnología de base la usan miles de empresas grandes en producción; lo nuevo es
> aplicarla al anaquel en tiempo real. Y el problema está medido: en retail los quiebres
> cuestan del orden del cuatro por ciento de las ventas, justo lo que atacamos. La
> mayoría todavía usa la auditoría como una foto para mirar hacia atrás; el que la usa
> para decidir hacia adelante captura esa ventaja primero. No le vendo logos ajenos: le
> doy su propio número en un piloto de sesenta días, que es la mejor referencia que
> puede llevar a su mesa."**

**"Llevo esto a mi junta. ¿Cuál es mi riesgo si algo sale mal y perdemos más dinero? ¿Qué garantía me das?"**
> **"Nadie serio le garantiza que un modelo nunca se equivoque; lo que le garantizo es
> que el riesgo está acotado. El sistema sugiere, el humano aprueba, nada se ejecuta
> solo. El peor caso de un error es una visita subóptima, no capital perdido, porque la
> acción es poner producto en el anaquel. Y la garantía para su junta es el piloto: si
> en sesenta días no mueve su número, no escalamos; lo que arriesga es el costo del
> piloto, no la compañía. El riesgo más caro hoy es no hacer nada: esos ocho millones en
> quiebre se pierden cada año."**

**"Si todo sale bien en el piloto, ¿cuál es el siguiente paso y el timeline para ir de un país a los diez?"**
> **"Si el piloto mueve el número, escalamos por olas de dos o tres países. Lo pesado ya
> está hecho: cada país es conectar su feed y calibrar, no reconstruir. Los diez
> completos en dos a tres trimestres, y el valor suma ola tras ola, no al final. Le
> propongo fijar hoy, junto con el piloto, los dos países de la siguiente ola."**

**"¿Cuál es el compromiso de ustedes para escalar? ¿Qué recursos dedican, cuál es el costo y mi timeline real?"**
> **"Tres cosas concretas. Recursos: un equipo dedicado —ingeniería de datos, ciencia de
> datos y un líder de solución— que acompaña cada ola; no le dejamos un software y adiós.
> Costo: el piloto corre en el orden de unos pocos miles de dólares al mes de
> plataforma, y el número cerrado se lo mando por escrito en cuarenta y ocho horas.
> Timeline: sesenta días el piloto, olas de dos o tres países, los diez completos en dos
> a tres trimestres. A cambio necesito acceso al feed, un dueño de negocio de su lado y
> el equipo de campo listo para actuar."**

**"¿Quién de mi equipo se involucra, cuántas personas, cuánto tiempo, y quién es mi contacto si algo falla?"**
> **"Le pido poco: tres personas, ninguna a tiempo completo. Un dueño de negocio, un par
> de horas por semana; un contacto de sistemas que dé acceso al feed, sobre todo al
> inicio; y un referente de campo. Los mercaderistas no cargan trabajo extra: siguen sus
> visitas, ahora guiadas. El peso lo lleva mi equipo. Su contacto de nuestro lado es una
> persona con nombre, un líder de solución, con respuesta en quince minutos para
> incidentes críticos, veinticuatro siete. Un número que responde, no una cola de
> tickets."**

### 🟧 Si el operador de la plataforma dice… _(lo toma Shreya)_

**"¿Cómo hacen que todos esos agentes respondan rápido?"**
> **"No corren cuando el usuario abre la app —ahí sí sería lento—. Corren en segundo
> plano cada par de minutos y dejan las recomendaciones ya escritas en una tabla; la app
> solo lee algo pre-calculado, por eso sale en milisegundos. Y la parte de números la
> resuelve SQL determinista; el modelo solo elige cuál vale la pena escalar."**

**"¿Y la calidad del dato? La visión por imagen se equivoca."**
> **"Las lecturas de baja confianza —un nueve por ciento en mi corrida— se marcan y se
> miden, no se cuelan; las reglas duras descartan la fila. El KPI que ve el negocio en
> pantalla es defendible."**

**"Si solo sugiere y el humano aprueba, ¿cómo garantizas que las recomendaciones son consistentes y confiables?"**
> **"La confianza está diseñada. El número que mueve la decisión es determinista
> —aritmética sobre el dato auditado—, no lo inventa el modelo; el modelo solo ordena y
> explica. El dato cruza controles de calidad antes de entrar, el modelo se evalúa
> contra datos que no vio y solo una versión aprobada llega a producción, y cada
> recomendación queda con su linaje. Misma situación, misma recomendación."**
>
> _[Si pide el "cómo": expectativas de calidad en la ingesta; modelo evaluado con
> held-out y promovido vía alias 'campeón' en el UC Model Registry; economía en SQL
> determinístico; linaje de Unity Catalog; monitoreo de drift en producción.]_

**"¿La arquitectura no son piezas pegadas?"**
> **"Es un medallón bronce-plata-oro declarado como infraestructura-como-código,
> reproducible con un comando. Un solo catálogo gobierna dato, modelo y permisos; no hay
> copias sueltas."**

**"¿Seguridad y datos de cliente?"**
> **"En el prototipo no hay dato real ni información personal: todo es sintético y está
> etiquetado así. En producción el gobierno es el mismo: permisos por rol, la app con
> identidad acotada y credenciales de vida corta."**

**"¿Cuánto cuesta operarlo?"**
> **"Es serverless: se paga por uso, no por infraestructura prendida. El retorno está en
> millones contra un costo de operación en miles; la relación no está cerca."**

**"Si mis datos crecen cincuenta por ciento, o tengo más tiendas o SKUs, ¿cómo escala el costo? ¿Hay un cap mensual?"**
> **"Lineal, no exponencial, y con techo. El procesamiento es incremental: solo se
> procesa lo nuevo, no se reprocesa todo, así que el costo sigue al volumen en
> proporción, no en saltos. Y usted fija un presupuesto mensual con alertas y límites que
> frenan antes de pasarse, con el gasto etiquetado por país: sin factura sorpresa."**
>
> _[Si pide el "cómo": serverless pay-per-use; ingesta incremental con Auto Loader;
> serving por clave casi plano frente a más tiendas; budget policies con alertas y
> límites; atribución de costo por tags y system tables de billing.]_

**"Esos datos crudos de auditoría, ¿cómo llegan? ¿App móvil, cámaras, qué fuente?"**
> **"En producción, la app de campo en el celular del auditor: toma la foto del anaquel,
> un reconocimiento de imagen lee cuántas caras tiene cada producto, el precio y si está
> en stock, más lo que el auditor confirma. Cada lectura trae su nivel de confianza. El
> punto de entrada es agnóstico a la fuente —app móvil, kiosco o feed del retailer por
> API—: entra por el mismo lugar y el resto del flujo no cambia."**
>
> _[Si pide el "cómo": los archivos (NDJSON) caen en un Volume de Unity Catalog y Auto
> Loader los ingiere incremental al pipeline. En la evidencia se ve el dispositivo real
> —SCAI-mobile, SCAI-kiosk— y su `confianza_ir`.]_

**"¿Cómo integro mi feed real de auditorías?"**
> **"Por el mismo punto de entrada. Cambiar el generador por su feed real no toca el
> resto: el procesamiento, el modelo, la pregunta en español y la app siguen igual."**

**"Al escalar a diez países con distinta nube y distintas políticas de datos, ¿cómo evitas que se rompa el modelo en producción?"**
> **"La heterogeneidad se absorbe en la entrada, no en el modelo: cada país aterriza la
> auditoría en un mismo contrato de datos y de ahí para arriba todo ve lo mismo. Un solo
> sistema que corre igual en cualquier nube, gobierno central con residencia por país
> donde la ley lo exige, y monitoreo de calidad y drift que avisa si un país se desvía
> antes de que llegue a una mala recomendación."**
>
> _[Si pide el "cómo": contrato de datos en bronze, Unity Catalog como gobierno único
> multi-región, pipeline declarativo idéntico en cualquier nube, expectativas de calidad
> + monitoreo de drift como red de seguridad.]_

**"Eso funciona si todos los países tuvieran la misma estructura; en retail Brasil no es México. ¿Cómo adaptas el modelo sin terminar con nueve pilotos?"**
> **"Tiene razón en que Brasil no es México. Pero los nueve pilotos aparecen cuando lo
> que cambia entre países es el código; aquí lo que cambia es la configuración. El motor
> —medir, priorizar, recomendar— es universal y compartido; la realidad local, qué
> tiendas, qué surtido, qué umbrales, se parametriza, no se reescribe. Una sola receta de
> entrenamiento produce un modelo calibrado por país. Sí, cada país toma unas semanas de
> puesta a punto, pero es configuración sobre un activo único: el mantenimiento sigue
> siendo uno, no nueve."**
>
> _[Si pide el "cómo": modelo de datos canónico con mapeo por país como config; pipeline
> de entrenamiento parametrizada (umbrales como config); Asset Bundles que estampan una
> instancia gobernada por país; gobierno central de Unity Catalog heredado por todas.]_

**"En producción con diez países, ¿cuánto tarda desde que la foto entra hasta que el gerente ve la predicción?"**
> **"Son dos cosas distintas. La pantalla responde siempre instantáneo, porque lee una
> ficha ya calculada. La frescura del dato —de la foto a la predicción disponible— es de
> minutos, no de horas: la foto entra, se procesa de forma incremental y el modelo corre
> en ciclos de un par de minutos. Los diez países no lo rompen: al ser incremental y
> serverless, más volumen escala en paralelo y la latencia por lectura se mantiene
> plana."**
>
> _[Si pide el "cómo": Auto Loader por micro-batch (trigger ajustable), pipeline y
> scoring en serverless que autoescala, y serving por clave en Lakebase (~1 ms)
> desacoplado de todo eso.]_

**"Si algo se rompe, ¿quién está disponible, cuál es el SLA, y qué pasa a las tres de la mañana en un país donde no tienen presencia?"**
> **"Dos capas. Gran parte de los fallos de infraestructura los cubre el proveedor de
> nube, veinticuatro siete, sin depender de que haya alguien despierto. Y el diseño
> degrada con elegancia: la pantalla sigue mostrando la última predicción buena aunque
> la ingesta tropiece, y el proceso se reintenta solo. Nuestro soporte es por niveles y
> sigue al sol: las tres de la mañana en un país son horario de oficina en otro.
> Compromiso concreto: incidente crítico, respuesta en quince minutos, y un líder de
> solución con nombre como su escalamiento directo."**
>
> _[Si pide el "cómo": SLA del proveedor + Databricks sobre serverless; serving
> desacoplado; reintento automático de micro-batches; soporte L1/L2/L3 follow-the-sun
> con runbooks y linaje de Unity Catalog.]_

**"¿Esto lo construyeron a mano o con IA?"**
> **"Con IA como multiplicador, pero nada se publicó sin verificar contra datos reales, y
> la parte que toca plata —traslados, precios, espacio— es lógica determinista, no la
> decide el modelo. El proceso está documentado en el repo."**

---

## Cierre _(≈15 s)_

> **"Mi propuesta concreta: pilotamos esto en un país con un equipo de campo durante
> sesenta días y medimos la disponibilidad en anaquel antes y después. Si mueve el
> número, lo escalamos por olas. ¿Fijamos el país y arrancamos?"**

---

_Recordatorios de entrega: lidera con el resultado y el dinero, deja el detalle técnico
a Shreya, usa Tell–Show–Tell (anuncia, muestra, recapitula enlazando al negocio), y
maneja el pushback con un dato, no a la defensiva._
