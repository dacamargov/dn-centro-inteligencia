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

**"Si funciona tan bien, ¿por qué no lo veo ya en el mercado? ¿Qué otras marcas grandes lo usan, quién más confía en esto?"**
> **"Es la pregunta correcta, y le doy la respuesta honesta. Lo que todavía no se ve en
> todas partes no es la tecnología, es esta combinación aplicada al anaquel en tiempo
> real. Las piezas de abajo no son experimentales: la plataforma de datos sobre la que
> corre esto la usan miles de empresas grandes en producción, y la medición en el punto
> de venta es justo lo que Dichter & Neira ya hace hoy para marcas líderes en diez
> países. Lo nuevo —y por eso no está en el estante de todos sus competidores— es unir
> esas dos cosas: tomar esa medición que ya existe y convertirla en una acción
> priorizada que llega a la mano del gerente en el momento de la visita, no en un
> reporte dos semanas después. La mayoría sigue usando esa medición como una foto para
> mirar hacia atrás; usarla para decidir hacia adelante es donde está la ventaja, y hoy
> el que la adopta primero es el que la captura. No le voy a vender logos; le voy a
> mostrar su propio número en un piloto de sesenta días, y ese es el mejor caso de
> referencia que puede tener: el suyo."**

**"Llevo esto a mi junta directiva. Van a preguntar cuál es mi riesgo. Si algo sale mal, si las recomendaciones son incorrectas y perdemos más dinero en vez de ganarlo, ¿cuál es la garantía que me das?"**
> **"Lléveles esa pregunta a su junta, porque tiene buena respuesta. Primero, seamos
> honestos: nadie serio le va a garantizar que un modelo nunca se equivoque. Lo que sí
> le garantizo es que el riesgo está acotado por diseño, y se lo explico en los términos
> de su junta. Uno: el sistema nunca actúa solo. Sugiere, y una persona aprueba; una
> recomendación equivocada la filtra el mercaderista antes de hacer nada, no se ejecuta
> a ciegas. Dos: pensemos cuál es realmente el peor caso de una recomendación mala. No
> es perder capital; es haber priorizado una visita a una tienda que no era la más
> urgente. La acción que el sistema propone es poner producto en el anaquel; eso no
> quema dinero, en el peor de los casos es una visita menos óptima. Tres: el número que
> prioriza no es una corazonada del modelo, es un cálculo sobre su propia auditoría, y
> queda registrado, así que si algo sale raro se rastrea y se corrige, no se esconde. Y
> cuatro, la garantía más importante para su junta: no les estoy pidiendo que apuesten
> la operación. Les estoy proponiendo un piloto de sesenta días donde medimos la
> disponibilidad antes y después con su propio dato; si no mueve el número, no
> escalamos, y lo que se arriesgó fue el costo del piloto, no la compañía. Dicho eso,
> voltee la pregunta: el riesgo más caro hoy no es implementar esto, es quedarse con el
> ocho por ciento de quiebre que ya tiene y seguir viéndolo dos semanas tarde. Eso sí es
> dinero que se pierde todos los días."**

**"Si todo sale bien en el piloto, ¿cuál es el siguiente paso? ¿Cómo pasamos de un país a los otros nueve, y cuál es el timeline?"**
> **"Perfecto, ese es justo el camino que quiero recorrer con usted. Si el piloto mueve
> el número, no arrancamos de cero en cada país, porque lo pesado ya está hecho: la
> plataforma es una sola, y cada país nuevo es conectar su feed de auditoría y calibrar
> los umbrales a su realidad, no volver a construir. Así que escalamos por olas.
> Terminado el piloto, tomamos dos o tres países por ola; la primera ola toma unas pocas
> semanas, porque el libreto quedó hecho en el piloto, y cada ola siguiente es más
> rápida que la anterior porque ya está el camino andado. Con ese ritmo, pasar del
> primer país a los diez completos es cosa de dos a tres trimestres, no de años. Y lo
> importante para su bolsillo: no espera a tener los diez para ver retorno; cada país
> empieza a recuperar quiebre apenas entra, así que el valor se va sumando ola tras ola
> mientras escalamos, no al final. Le propongo que fijemos desde ya, junto con el
> piloto, cuáles son los dos países de la siguiente ola, para arrancar con impulso en
> cuanto tengamos el número."**

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

**"Si la plataforma solo sugiere y el humano aprueba, ¿cómo garantizas que las sugerencias del modelo son consistentes y confiables? ¿Qué validación tiene antes de mostrarle una recomendación al mercaderista?"**
> **"Es la pregunta que yo querría que me hicieran, porque aquí la confianza está
> diseñada, no es un acto de fe. Lo primero y más importante: el número que mueve la
> decisión —qué tienda priorizar y cuánta venta está en juego— no lo inventa el modelo
> de lenguaje; se calcula de forma determinística, con reglas claras, sobre el dato
> auditado. El modelo no adivina cuánto dinero hay en riesgo; eso es aritmética sobre la
> medición. Lo que el modelo aporta es ordenar y explicar, y aun eso pasa por filtros.
> Antes de que una recomendación llegue al mercaderista, el dato cruza controles de
> calidad en la entrada, así que una lectura corrupta o incompleta nunca alimenta una
> sugerencia. El modelo de predicción se entrena y se evalúa contra datos que no vio, se
> mide, y solo una versión que pasa esa evaluación se promueve a producción con una
> etiqueta de 'campeón'; ninguna versión llega a la calle sin ese sello. En producción
> seguimos vigilando que no se desvíe. Y la recomendación nunca es una caja negra: queda
> registrada, con su linaje, así que siempre puedo rastrear de qué dato y de qué versión
> salió. Por eso la misma situación produce la misma recomendación: la prioridad es
> determinística, el modelo explica, y el humano aprueba. Tres capas, no una."**
>
> _[Si pide el "cómo": expectativas de calidad (@dlt.expect) en la ingesta; modelo
> entrenado y evaluado con datos held-out, versionado en el UC Model Registry y
> promovido solo vía alias 'campeón'; economía/priorización calculada en SQL
> determinístico (el LLM solo ordena y redacta, no inventa el número); linaje de Unity
> Catalog para auditar cada recomendación; y monitoreo de drift en producción.]_

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

**"Al escalar a diez países, cada uno con infraestructura distinta, distinta nube, distintas políticas de datos, ¿cómo manejas esa complejidad sin que se me quiebre el modelo en producción?"**
> **"Justo ahí es donde la arquitectura se gana su lugar. La clave es que la
> heterogeneidad se absorbe en la entrada, no en el modelo. Cada país puede tener su
> nube, su proveedor y sus políticas, pero todos aterrizan la auditoría en un mismo
> contrato de datos —el mismo formato, las mismas columnas—, así que de ahí para arriba
> el pipeline y el modelo ven exactamente lo mismo sin importar de dónde vino. Eso
> significa que no mantengo diez sistemas distintos: mantengo uno solo, con una
> definición que corre igual sobre cualquier nube, porque la plataforma es la misma en
> AWS, Azure o Google. El gobierno vive en una sola capa: permisos, linaje y políticas
> por país se administran en un único lugar, y donde una regulación exige que el dato se
> quede en el país, se queda en el país, pero se sigue gobernando centralmente. Y para
> que no se quiebre en silencio, el sistema vigila la calidad del dato en cada ingesta y
> vigila que el modelo no se desvíe; si un país empieza a comportarse distinto, salta la
> alarma antes de que eso llegue a una recomendación mala. Así, escalar a diez países es
> sumar fuentes al mismo motor, no reconstruir diez veces."**
>
> _[Si pide el "cómo": contrato de datos en la capa bronze, Unity Catalog como gobierno
> único multi-región (residencia por país, linaje, permisos), pipeline declarativo que
> corre idéntico en cualquier nube, y expectativas de calidad + monitoreo de drift del
> modelo como red de seguridad.]_

**"Asset bundles, infra como código, reproducible, bien. Pero sea honesto: eso funciona si todos los países tienen la misma estructura de datos, las mismas tiendas, los mismos proveedores. En retail no es así —Brasil no es México ni Colombia—. ¿Cómo adaptas el modelo sin terminar con nueve pilotos distintos en vez de uno escalado?"**
> **"Me gusta que sea honesto, porque tiene toda la razón: en retail Brasil no es México
> ni es Colombia, y si mi respuesta fuera 'el mismo modelo para todos', usted tendría
> razón en desconfiar. Pero la trampa que describe —terminar con nueve pilotos— aparece
> cuando lo que cambia entre países es el código. Aquí lo que cambia entre países no es
> el código, es la configuración. Déjeme separar dos cosas. Una es el motor: la lógica
> de medir disponibilidad, priorizar y recomendar es universal —una tienda es una tienda
> y un quiebre es un quiebre en cualquier país—; eso es un solo sistema, compartido. La
> otra es la realidad local: qué tiendas, qué surtido, qué proveedores, qué cuenta como
> quiebre crítico en Brasil frente a Colombia. Eso no se reescribe, se parametriza: cada
> país mapea su realidad sobre un mismo modelo de datos común, y sus umbrales son
> valores de configuración, no programas distintos. El modelo no es ni una caja negra
> global impuesta a todos, ni nueve modelos hechos a mano; es una sola receta de
> entrenamiento que, con el dato de cada país, produce un modelo calibrado para ese
> país. Adaptar es recalibrar con esa misma receta, no volver a construir. Por eso la
> infraestructura-como-código es justamente lo que evita los nueve pilotos: estampo una
> instancia gobernada por país desde la misma definición, con sus parámetros, y las
> nueve heredan los mismos controles de calidad y seguridad; no vuelvo a probar que es
> seguro nueve veces. Y siendo honesto en la otra dirección: sí, cada país tiene un
> trabajo de puesta a punto —conectar su feed, mapear su taxonomía, afinar sus umbrales
> y validar— y eso toma semanas; pero es trabajo de configuración sobre un activo
> compartido, y el mantenimiento sigue siendo uno, no nueve."**
>
> _[Si pide el "cómo": modelo de datos canónico con mapeo por país a nivel de
> configuración; una sola pipeline de entrenamiento parametrizada que produce un modelo
> calibrado por país (umbrales como config, no código); Asset Bundles que estampan una
> instancia gobernada por país desde la misma definición; gobierno central de Unity
> Catalog heredado por todas; onboarding por país = semanas de configuración, no un
> rebuild, con mantenimiento único.]_

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

**"Si algo se rompe, alguien tiene que estar disponible. ¿Quién es ese alguien, cuál es el modelo de soporte, y qué pasa si necesito soporte a las tres de la mañana en un país donde ustedes no tienen presencia?"**
> **"Es una preocupación válida, y la respuesta tiene dos capas. La primera: buena parte
> de 'que algo se rompa' ni siquiera depende de que haya alguien despierto. La
> plataforma es gestionada, sin servidores que administrar, con el respaldo y el acuerdo
> de nivel de servicio del proveedor de nube, que ya opera soporte veinticuatro-siete a
> nivel mundial; si falla algo de la infraestructura, eso lo cubre el proveedor, no mi
> equipo a las tres de la mañana. La segunda capa es el diseño: el sistema está hecho
> para degradar con elegancia. La pantalla que ve el gerente lee predicciones ya
> calculadas, así que aunque la ingesta tenga un tropiezo de madrugada, nadie se queda a
> oscuras: sigue viendo la última lectura buena mientras el proceso se recupera solo,
> porque reintenta los lotes fallidos sin intervención. Y sobre nuestro soporte: es por
> niveles y sigue al sol. El monitoreo automático detecta y alerta en el momento; el
> equipo regional atiende en horario; y como cubrimos varias regiones, las tres de la
> mañana en un país son horario de oficina en otro. Para eso no necesito tener gente
> físicamente en ese país: la plataforma se opera y se vigila de forma central, en la
> nube. Así que el modelo no depende de héroes despiertos: depende de infraestructura
> gestionada, monitoreo que se anticipa, procedimientos documentados y cobertura que
> sigue al sol."**
>
> _[Si pide el "cómo": SLA del proveedor de nube + Databricks sobre infra serverless;
> serving desacoplado (la última predicción buena en Lakebase sigue disponible aunque
> falle la ingesta); reintento automático de micro-batches; soporte en niveles (L1
> monitoreo/alertas automáticas, L2 on-call regional, L3 follow-the-sun) con runbooks y
> linaje de Unity Catalog para diagnóstico rápido.]_

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
