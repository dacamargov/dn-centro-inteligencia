import { Traslado } from './api';

type Punto = [number, number];

/**
 * Un traslado va de 1 a 60 km, y el mapa encuadra de Guatemala a Perú. A esa
 * escala un segmento recto entre las dos tiendas mide dos o tres píxeles y
 * queda tapado por los propios círculos de los PDV, que llegan a 23 de radio:
 * las rutas estaban dibujadas, simplemente no se veían.
 *
 * La solución es curvarlas. El arco se separa de la recta lo suficiente para
 * leerse aunque las dos tiendas estén encima una de la otra, y de paso separa
 * visualmente dos rutas que compartan un extremo.
 *
 * La comba se mide en píxeles, no en grados: en grados fijos el arco se ve al
 * zoom continental y se vuelve un lazo absurdo de 180 km al acercarse, o al
 * revés. Atada a la pantalla, la ruta se lee igual de bien en los dos extremos.
 */
// El vértice de una bezier cuadrática llega a la mitad del punto de control,
// así que esto son ~48 px de comba real. Parece mucho, pero al encuadre
// continental las dos tiendas de un traslado caen prácticamente en el mismo
// píxel y bajo el mismo círculo de PDV: sin una comba que se escape del
// círculo, la ruta se dibuja adentro del punto y no se lee.
const COMBA_PX = 95;
const COMBA_PROPORCIONAL = 0.12;
const PASOS = 24;

/** Píxeles por grado de longitud en el esquema de teselas estándar de 256 px. */
function pxPorGrado(zoom: number): number {
  return (256 * 2 ** zoom) / 360;
}

export function arcoDeTraslado(t: Traslado, zoom = 5): Punto[] | null {
  const { origen_lat, origen_lon, destino_lat, destino_lon } = t;
  if (
    origen_lat == null || origen_lon == null ||
    destino_lat == null || destino_lon == null
  ) {
    return null;
  }

  const a: Punto = [origen_lat, origen_lon];
  const b: Punto = [destino_lat, destino_lon];

  const dLat = b[0] - a[0];
  const dLon = b[1] - a[1];
  const largo = Math.hypot(dLat, dLon);

  // Dos tiendas en la misma esquina: sin dirección definida, se comba al norte.
  const [nLat, nLon] = largo < 1e-6 ? [0, 1] : [dLat / largo, dLon / largo];
  const comba = Math.max(COMBA_PX / pxPorGrado(zoom), largo * COMBA_PROPORCIONAL);

  // Perpendicular a la recta, siempre hacia el mismo lado para que dos rutas
  // entre las mismas dos tiendas no se dibujen una encima de la otra.
  const control: Punto = [
    (a[0] + b[0]) / 2 + -nLon * comba,
    (a[1] + b[1]) / 2 + nLat * comba,
  ];

  const puntos: Punto[] = [];
  for (let i = 0; i <= PASOS; i += 1) {
    const s = i / PASOS;
    const u = 1 - s;
    puntos.push([
      u * u * a[0] + 2 * u * s * control[0] + s * s * b[0],
      u * u * a[1] + 2 * u * s * control[1] + s * s * b[1],
    ]);
  }
  return puntos;
}

/** Encuadre de las dos tiendas, con aire para que la comba entre en cuadro. */
export function limitesDeTraslado(t: Traslado): [Punto, Punto] | null {
  const { origen_lat, origen_lon, destino_lat, destino_lon } = t;
  if (
    origen_lat == null || origen_lon == null ||
    destino_lat == null || destino_lon == null
  ) {
    return null;
  }
  // Piso de margen: dos tiendas a 1,4 km encuadradas al milímetro dejarían un
  // recuadro degenerado y el mapa saltaría al zoom máximo.
  const margen = Math.max(
    0.12,
    Math.hypot(destino_lat - origen_lat, destino_lon - origen_lon) * 0.45,
  );
  return [
    [Math.min(origen_lat, destino_lat) - margen, Math.min(origen_lon, destino_lon) - margen],
    [Math.max(origen_lat, destino_lat) + margen, Math.max(origen_lon, destino_lon) + margen],
  ];
}
