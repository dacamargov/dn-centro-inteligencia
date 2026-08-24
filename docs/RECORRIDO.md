# Recorrido

Guía de las pantallas, con la instalación hecha y la operación encendida (`./encender.sh` o el
botón **Iniciar demo** del app). Abrí la URL del app con tu sesión del workspace iniciada.

El dato fluye en vivo mientras los jobs estén activos. Las pestañas se refrescan solas por
polling: no hace falta recargar.

## El guion en un minuto

Si hay poco tiempo, este recorrido cuenta la historia completa:

1. **Ejecución** — "esto es lo que está pasando en el anaquel ahora mismo".
2. Abrí el drill-down de **Culinarios** en Meta vs Realizado, la categoría rezagada.
3. Dejá que la explicación cruce el quiebre con el precio y con la conversación social.
4. **Despachá** la acción del banner superior.
5. **Campo** — la acción ya está esperando en el celular del mercaderista, servida en menos de
   100 ms.

Ese salto de "el tablero detectó" a "el mercaderista ya lo tiene" es el momento de la demo.

## Ejecución

El tablero operativo, y la pantalla para dejar abierta.

- **KPIs en vivo**: disponibilidad en anaquel, ejecución perfecta, share of shelf y cobertura de
  la red en los últimos 15 minutos.
- **Meta vs Realizado**: cumplimiento por categoría contra la meta pactada. Cada barra abre un
  drill-down con diagnóstico y explicación generada por el modelo.
- **Serie de ejecución**: disponibilidad y ejecución minuto a minuto por categoría. Las acciones
  despachadas quedan anotadas sobre la línea de tiempo, para ver su efecto.
- **Lecturas de anaquel en vivo**: cada observación entrando, unas dos por segundo, con los
  quiebres en rojo. Abajo tiene la leyenda de los íconos: el cubo naranja es "fuera de
  planograma" y es la falla más rentable, porque se corrige moviendo el producto sin reponer
  nada.
- **Ranking por país**: dónde está fallando la red.

## Agentes

Cuatro agentes corriendo como jobs agendados, cada dos minutos. Cada tarjeta trae severidad,
análisis, recomendación y una acción estructurada; se puede **Despachar** o **Descartar**, y la
decisión queda registrada en `action_log`.

| Agente | Qué vigila |
|---|---|
| **Pulso de ejecución** | Disponibilidad, planograma y quiebres sistemáticos. |
| **Precio y promoción** | Dónde el índice de precio se sale de banda. |
| **Sentimiento de marca** | La conversación negativa, cruzada con el anaquel. |
| **Red de abastecimiento** | Sobrestock contra quiebre: qué traslado entre PDV conviene. |

Son modelos con *tool-calling* real sobre el lakehouse, no reglas fijas: reciben herramientas y
deciden cuáles consultar. Las primeras recomendaciones aparecen uno o dos minutos después de
encender.

## Puntos de venta

Mapa de la red de auditoría, de Guatemala a Perú. El color de cada punto indica su estado de
ejecución y el tamaño el volumen de lecturas.

La pieza que suele generar la mejor conversación son los **traslados**: el agente de red cruza
un PDV con sobrestock contra otro con quiebre del mismo SKU, calcula la ganancia neta después
del costo logístico y lo propone. Al aprobar, el traslado pasa a la lista de aprobados y su ruta
se dibuja sólida sobre el mapa; las propuestas pendientes van en línea de trazos. La lógica de
matcheo y de economía es SQL determinista, no del modelo: así el número es auditable y el
modelo se queda con lo que sabe hacer, que es explicarlo.

**PDV por atender** lista los puntos que necesitan visita, con el motivo derivado del dato
(tendencia en caída, mucho tiempo sin lectura, SKU crítico agotado) y el botón para despachar.

## Precios

El índice se calcula **normalizado por contenido dentro de la subcategoría**, no contra el
promedio de la categoría: comparar un litro de leche con un yogurt individual no dice nada.

El simulador permite mover el precio y ver el margen y el volumen proyectado, con la ventana
óptima marcada en verde. Es la pantalla donde el equipo de revenue growth discute un cambio
antes de bajarlo a la cadena.

## Marca

La conversación del consumidor cruzada con el anaquel: termómetro de salud de marca, ranking por
marca y feed de posts.

El panel que pone el sentimiento por categoría al lado de su disponibilidad es el que cierra el
argumento: la queja en redes casi siempre viene después del quiebre en góndola.

Cuando el agente detecta un post con tracción, se puede **amplificar**: convertirlo en campaña
con presupuesto y alcance estimado. La decisión es humana; el agente solo señala dónde está la
ganancia.

## Campo

El copiloto del mercaderista, servido desde Lakebase. **Viene deshabilitado** para no incurrir
en costo de base de datos — ver [LAKEBASE.md](LAKEBASE.md). Con Lakebase encendido:

- **Simulador de visita**: elegís un PDV y recibís su plan priorizado, con el impacto estimado
  de cada acción.
- **Jornada en vivo**: la jornada real, con varios mercaderistas abriendo la app a la vez.
- **SLA de latencia**: p50, p95 y p99 contra el presupuesto de 100 ms.

El ciclo cierra: cada plan servido vuelve con lo que el mercaderista efectivamente corrigió, así
que la tasa de ejecución se mide en vez de suponerse.

## Genie

Botón flotante abajo a la derecha, en todas las pestañas operativas. Preguntas en español sobre
la operación.

En **modo demostración** (el que trae por defecto) las respuestas están precargadas a partir del
dato real del workspace, sin costo ni Genie Space. En **modo real** las preguntas van al
lakehouse y Genie genera el SQL en vivo — ver [GENIE.md](GENIE.md).

Preguntas para empezar:

1. ¿Cuál es la disponibilidad en anaquel por categoría?
2. ¿Qué puntos de venta tienen la peor ejecución esta hora?
3. ¿Cuál es el share of shelf de nuestras marcas por país?
4. ¿Qué SKUs están agotados en más puntos de venta?
5. ¿Cómo se compara nuestro índice de precio con la competencia por cadena?

## Dashboard AI/BI

El dashboard Lakeview se abre directo en el workspace y queda embebido en el app. Es la mirada
analítica que complementa al tablero operativo: el mismo dato, sin la capa de decisión.

---

## Para que la demostración salga bien

- Encendé unos minutos antes, para que los agentes acumulen recomendaciones.
- Tené dos pestañas: el app y Workflows, para mostrar los jobs corriendo de verdad.
- Si algo aparece vacío, esperá uno o dos minutos, o `./encender.sh --sin-espera`.
- Para empezar limpio entre presentaciones: `./scripts/limpiar.sh && ./encender.sh`.
- Si retomás después de horas, el generador detecta el hueco y re-siembra la ventana completa en
  la primera corrida. No hay que hacer nada especial.
