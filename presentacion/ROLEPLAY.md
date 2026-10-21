# Roteiro de role-play — Centro de Inteligencia D&N
### Párrafos exactos para leer · 20–30 min · dos personas en la sala

**Personas:** 🟦 **gerente de anaquel** (dueño del resultado comercial) · 🟧
**operador de la plataforma** (data lead que la mantiene).
**Cómo usar:** lee de corrido los párrafos en **negrita**; lo que está _[entre
corchetes]_ son indicaciones, no se leen.

---

## 1 · Apertura _(≈30 s)_

> _[Mirando a los dos, con calma.]_

**"Gracias por el tiempo. Dichter & Neira mide la ejecución en el punto de venta
—si el producto está en el anaquel, a qué precio, con qué espacio— para marcas como
Nestlé en diez países. El problema de ustedes no es falta de datos; es el tiempo que
tardan en convertirse en acción: hoy auditar, reportar y recién después actuar toma
semanas, y para cuando el reporte llega, la venta que se perdió por un quiebre ya no
vuelve. Lo que les voy a mostrar es cómo cerramos ese tiempo a minutos. Son unos pocos
pasos; voy a ir mostrando y al final quedamos en preguntas."**

---

## 2 · Valor en tres números _(≈30 s, Slide 2)_

> _[Deja caer el 8.2% y haz una pausa corta.]_

**"Pongamos tamaño al problema con la propia red que medimos. Hoy la disponibilidad
en anaquel está en noventa y dos por ciento, el quiebre de stock en ocho por ciento, y
la ejecución perfecta apenas en setenta y ocho. Ese ocho por ciento de quiebre es
venta que simplemente no ocurre y espacio que se le cede a la competencia. Ese es el
dinero que estamos persiguiendo, y es la vara contra la que mido todo lo que sigue."**

---

## 3 · Demo _(≈60 s, mostrando la pantalla, Slide 3)_

> _[Léelo de corrido mientras recorres el app. Cero jerga técnica.]_

**"Miren lo que ve el negocio en un solo lugar. La foto que toma el auditor en la
tienda entra sola al sistema y se limpia: lo que la cámara leyó con poca certeza se
aparta, así que el número en el que ustedes confían es real, no ruido. Con eso, cada
punto de venta arma su propia ficha, y cuando el mercaderista llega a la tienda y la
abre, aparece al instante. Pero no es solo una ficha: el sistema predice dónde se va a
quebrar el producto antes de que pase, y le dice al mercaderista exactamente qué
corregir en ese anaquel. Eso cambia la operación —en vez de recorrer las 140 tiendas
por igual, el equipo ataca primero las 34 que están en riesgo real. Y si usted,
gerente, quiere algo que no está en la pantalla, se lo pregunta en español, como le
hablaría a una persona —'¿cuáles son mis cinco peores tiendas esta semana?'— y le
responde al momento, sin tener que pedirle nada al área de sistemas. Todo esto es una
sola pantalla, funcionando en vivo con los datos de hoy."**

> **Traducción técnica — SOLO si el operador pregunta "¿cómo está hecho?":**
> la foto entra y se valida con **Lakeflow**; todo queda gobernado en **Unity
> Catalog** y se expone en un **Databricks App**; la ficha se sirve desde **Lakebase**
> en ~1 ms; la predicción es un **modelo de ML** y las acciones son **agentes de Gen
> AI**; la pregunta en español la traduce a SQL **Genie**. _[Detalle en `evidence/`.]_

---

## 4 · Aterrizaje _(≈30 s, Slides 4–5)_

> _[Cierra la parte expositiva y abre a preguntas.]_

**"Lo que esto mueve son sus números: la disponibilidad en anaquel del noventa y dos
hacia una meta de noventa y seis, la ejecución perfecta del setenta y ocho hacia
ochenta y ocho, y el ciclo de insight de semanas a minutos. Puesto en plata, con un
supuesto conservador de recuperar la mitad de lo que hoy se pierde por quiebre, en una
red de cien millones de dólares estamos hablando del orden de cuatro millones al año.
Y esto no es una maqueta: toda la prueba de que corrió de verdad está escrita en el
repositorio. Con eso, les abro a preguntas."**

---

## 5 · Objeciones — lee la respuesta exacta según quién pregunte

### 🟦 Si el gerente de anaquel dice…

**"¿Y si la recomendación está mal?"**
> **"El sistema propone, pero usted aprueba; nada se ejecuta solo. Y el dato que vino
> con poca certeza se marca aparte, no se usa a ciegas. Además queda todo registrado,
> así que siempre se puede revisar qué se recomendó y qué se hizo."**

**"Tengo 140 tiendas y poco tiempo de ruta."**
> **"Por eso el sistema prioriza: le dice cuáles son las treinta y cuatro tiendas en
> riesgo real para visitar primero, en vez de tratarlas todas por igual. Su equipo
> rinde más con las mismas horas."**

**"¿Esto me sirve en la visita o es otro reporte más?"**
> **"En la visita. El mercaderista abre la tienda en el celular y ve qué corregir en
> ese anaquel en el momento, no al día siguiente cuando ya se fue."**

**"¿Qué gano yo en el número?"**
> **"Recupera venta que hoy se pierde por quiebre y protege su espacio en el anaquel
> frente a la competencia. Cuatro puntos de disponibilidad es dinero directo a su
> categoría."**

**"Si actuamos en minutos en vez de semanas, ¿cuánto de ese ocho por ciento realmente recuperamos?"**
> **"Buena pregunta, y la respuesta honesta es que no recuperamos el ocho por ciento
> completo: cuando el producto se agota, una parte de esa venta ya se perdió antes de
> que alguien lo vea. Lo que cambia drásticamente es cuánto tiempo dura el anaquel
> vacío. Hoy, con un ciclo de semanas, la tienda se queda sin producto varios días
> entre que se detecta y se corrige, y esa es la venta que se escapa. Al actuar en la
> propia visita ese tiempo colapsa a horas; y además el modelo anticipa el quiebre
> antes de que ocurra, así que una parte ni siquiera llega a pasar. De forma
> conservadora eso recorta el quiebre a la mitad —de ocho a alrededor de cuatro por
> ciento, que son los cuatro puntos de disponibilidad que les mostré. Esa mitad es
> exactamente la que modelamos como recuperable: en una red de cien millones de
> dólares, del orden de cuatro millones al año. Y no se los pido de fe: el piloto de
> sesenta días lo mide con su propio número, antes y después."**

**"¿Cuánto tiempo necesito para ver el retorno?"**
> **"Rápido, y por etapas. Lo que vieron ya corre, así que no hay meses de
> construcción por delante: arrancamos un piloto de sesenta días en un país. Las
> primeras ganancias se ven en semanas, porque apenas el equipo empieza a visitar
> primero las tiendas en riesgo, la disponibilidad en anaquel sube, y cada punto de
> disponibilidad es venta recuperada casi de inmediato. A los sesenta días medimos la
> disponibilidad antes y después, y ahí tienen el retorno demostrado con su propio
> número, no con una proyección. Con ese impacto, la inversión se paga en el primer
> trimestre; de ahí en adelante es ganancia."**

**"¿Y cómo hacemos para saber el stock de todas las tiendas?"**
> **"Lo sabemos de la propia auditoría, que es justo lo que Dichter & Neira ya hace:
> en cada visita se registra, producto por producto, si está en el anaquel, cuántas
> caras tiene y a qué precio. Esa lectura es el dato crudo que alimenta todo; no
> dependemos de que el retailer nos abra su sistema de inventario, lo medimos en el
> piso de venta. Y si mañana quieren sumar el stock de trastienda del retailer, entra
> por el mismo camino sin rehacer nada."**

**"Si lo implemento hoy, ¿cuántos meses hasta que mi equipo esté funcional y esto produzca valor real? Entrenamiento, configuración, ajustes."**
> **"La respuesta corta es: semanas para el primer valor, no meses para arrancar. Esto
> no es un proyecto de instalar servidores ni de meses de montaje; la plataforma ya
> está construida, y lo que hacemos al implementar es conectar su feed real de
> auditorías y afinar los umbrales a su realidad. Con eso, un piloto en un país o un
> grupo de tiendas ya está dando recomendaciones accionables en cuestión de semanas. El
> entrenamiento del equipo es mínimo: la pantalla no le exige a nadie saber de datos ni
> de tecnología, le dice al gerente qué tienda priorizar y qué hacer en la visita, así
> que la curva es de una sesión, no de un curso. De ahí escalamos por olas —más países,
> más tiendas— de forma progresiva, y en un trimestre tienen la operación completa de
> los diez países corriendo. Pero lo importante es que no esperan el trimestre para ver
> valor: desde el piloto, en las primeras semanas, ya están recuperando quiebres que
> antes veían tarde."**

### 🟧 Si el operador de la plataforma dice…

**"¿Cómo hacen que todos esos agentes respondan rápido?"**
> **"La clave es que los agentes no corren cuando el mercaderista abre la app —ahí sí
> se sentiría lento. Corren en segundo plano cada par de minutos, revisan los datos y
> dejan las recomendaciones ya escritas en una tabla. Cuando el usuario abre la
> pantalla solo lee algo que ya está calculado, por eso sale en milisegundos. El
> razonamiento pesado lo hace el agente una vez, no en cada consulta; y la parte de
> números la resuelve una consulta directa, el modelo solo elige cuál vale la pena
> escalar."**

**"¿Y la calidad del dato? La visión por imagen se equivoca."**
> **"Es explícito: las lecturas de baja confianza —en mi corrida, un nueve por ciento—
> se marcan y se miden, no se cuelan; y las reglas duras descartan la fila. Para el
> negocio eso significa que el KPI que ve en pantalla es defendible."**

**"¿La arquitectura no son piezas pegadas?"**
> **"Es un medallón bronce-plata-oro declarado como infraestructura-como-código, así
> que es reproducible con un comando. Un solo catálogo gobierna dato, modelo y
> permisos; no hay copias sueltas."**

**"¿Seguridad y datos de cliente?"**
> **"En el prototipo no hay dato real ni información personal: todo es sintético y está
> etiquetado así. En producción el gobierno es el mismo —permisos por rol, la app con
> una identidad acotada y credenciales de vida corta."**

**"¿Cuánto cuesta operarlo?"**
> **"Es serverless: se paga por uso, no por infraestructura prendida, y la base
> operacional es la instancia más chica. El retorno está en millones contra un costo
> de operación en miles; la relación no está cerca."**

**"Esos datos crudos de auditoría, ¿cómo llegan? ¿App móvil, cámaras, qué fuente?"**
> **"En el mundo real la fuente es la app de campo en el celular del auditor: toma la
> foto del anaquel y un reconocimiento de imagen lee cuántas caras tiene cada
> producto, el precio y si está en stock, más lo que el auditor confirma a mano. Cada
> visita genera una lectura —un registro por tienda y por producto— con su marca de
> tiempo, el dispositivo que la tomó y un nivel de confianza del reconocimiento. Esa
> lectura aterriza como archivo en un volumen de almacenamiento gobernado, y el sistema
> la toma de ahí de forma incremental apenas llega, sin que nadie dispare un proceso a
> mano. Lo importante para la integración es que el punto de entrada es agnóstico a la
> fuente: hoy en la demo un generador deja esos archivos, pero igual puede ser la app
> móvil, un kiosco en tienda o un feed del retailer por API o cola; entra por el mismo
> lugar y el resto del flujo no cambia. Y como cada lectura trae su confianza, lo que
> la cámara leyó dudoso se marca en vez de ensuciar el número."**
>
> _[Si pide el "cómo" exacto: los archivos (NDJSON) caen en un Volume de Unity Catalog
> y **Auto Loader** los ingiere incremental al pipeline de Lakeflow. En la evidencia se
> ve el dispositivo real de cada lectura —SCAI-mobile, SCAI-kiosk— y su `confianza_ir`.]_

**"¿Cómo integro mi feed real de auditorías?"**
> **"Por el mismo punto de entrada. Cambiar el generador de datos por su feed real no
> toca el resto: el procesamiento, el modelo, la pregunta en español y la app siguen
> igual. Y la ficha que sirve el copiloto ya se alimenta de la capa gobernada, sin
> recálculo paralelo."**

**"En producción, con diez países, ¿cuánto tarda el pipeline desde que la foto entra hasta que el gerente ve la predicción?"**
> **"Primero separemos dos cosas que suelen confundirse. Una es qué tan rápido
> responde la pantalla cuando el gerente la abre: eso es siempre instantáneo, un
> milisegundo, porque lee una ficha ya calculada, no espera a ningún procesamiento. La
> otra es qué tan fresco es el dato detrás de esa ficha, y ahí el recorrido completo
> —desde que la foto entra hasta que la predicción está disponible— es de minutos, no
> de horas. La foto sube como archivo en segundos; el sistema la toma apenas llega, de
> forma incremental, no en una corrida nocturna; el procesamiento con sus controles de
> calidad y el scoring del modelo corren en ciclos de un par de minutos. Así que una
> lectura que entra ahora queda accionable en cuestión de minutos. Y lo de los diez
> países no lo rompe, al contrario: como la ingesta es incremental y el cómputo es
> serverless, más volumen simplemente escala en paralelo; la latencia por lectura se
> mantiene plana, no crece porque haya más tiendas. Si el negocio pidiera
> near-real-time de verdad podemos acercarlo subiendo la frecuencia, pero para
> ejecución en anaquel los minutos sobran: la ventana de acción es la visita del
> mercaderista, no los segundos."**
>
> _[Si pide el "cómo": Auto Loader ingiere por micro-batch (trigger ajustable), el
> pipeline y el scoring corren en serverless que autoescala por volumen, y el serving
> por clave en Lakebase (~1 ms) está desacoplado de todo eso.]_

**"¿Esto lo construyeron a mano o con IA?"**
> **"Con IA como multiplicador, pero nada se publicó sin verificar contra datos reales,
> y la parte que toca plata —traslados, precios, espacio en anaquel— es lógica
> determinista, no la decide el modelo. El detalle del proceso está documentado."**

---

## Cierre _(≈15 s)_

> **"Mi propuesta concreta: pilotar esto en un país con un equipo de campo durante
> sesenta días y medir la disponibilidad en anaquel antes y después. Si mueve el
> número, lo escalamos."**

---

_Recordatorios de entrega: lidera con el resultado, cambia de altura a media respuesta
(detalle al operador, negocio al gerente), y maneja el pushback con un dato, no a la
defensiva._
