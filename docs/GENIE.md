# Genie — modo demostración y sala real

El chat de Genie (el botón flotante abajo a la derecha) tiene dos modos. Por defecto arranca en
el primero, que no requiere ningún montaje.

## Modo demostración

Con `genie_space_id` vacío, las preguntas sugeridas devuelven respuestas y tablas precargadas en
`src/app/server/canned_genie.json`. Sirve para demostrar la capacidad sin costo ni setup, y las
cifras no contradicen al tablero porque **se generan del dato real del workspace**.

Ese archivo viaja en el repositorio con las cifras de la instalación donde se generó. Si las
cifras de tu workspace son distintas, el chat va a decir algo que el tablero no dice. Para
regenerarlo, con la operación andando un rato:

```bash
./scripts/construir_genie_precargado.sh
databricks bundle deploy -t demo        # para que el app se lleve el JSON nuevo
```

## Sala real

Con una sala Genie conectada, las preguntas van al lakehouse y Genie genera el SQL en vivo. Es
lo que conviene mostrar cuando la conversación es sobre gobierno y no sobre la interfaz.

1. Creá el Genie Space en la interfaz (**Genie → New**) con el mismo warehouse de la instalación
   y agregale las tablas del esquema:

   `visitas`, `tiendas`, `productos`, `paises`, `metas_categoria`, `precios_competencia`,
   `social_posts`

2. Copiá el `space_id` de la URL: `/genie/rooms/<SPACE_ID>`.

3. Verificá que la sala responde y que tenés permiso sobre ella:

   ```bash
   ./scripts/verificar_genie.sh <SPACE_ID>
   ```

4. Instalá pasándole el id:

   ```bash
   ./instalar.sh --var genie_space_id=<SPACE_ID>
   ```

   O, si ya está instalado y solo querés cambiar el modo:

   ```bash
   databricks bundle deploy -t demo --var genie_space_id=<SPACE_ID>
   ```

Para volver al modo demostración, desplegá con el valor vacío:

```bash
databricks bundle deploy -t demo --var genie_space_id=
```

## Preguntas que funcionan bien

Las mismas que trae precargadas el modo demostración, porque están escritas contra el modelo de
datos y no contra una intuición de él:

1. ¿Cuál es la disponibilidad en anaquel por categoría?
2. ¿Qué puntos de venta tienen la peor ejecución esta hora?
3. ¿Cuál es el share of shelf de nuestras marcas por país?
4. ¿Qué SKUs están agotados en más puntos de venta?
5. ¿Cómo se compara nuestro índice de precio con la competencia por cadena?
