import { BrechaPrecio } from './api';

/** Identifica una observación de anaquel: un SKU en una cadena de un país. */
export const claveFila = (b: BrechaPrecio) => `${b.sku}|${b.cadena}|${b.country_code}`;

/**
 * Un SKU caro suele estarlo en todas las cadenas a la vez, así que la lista
 * cruda de brechas repite el mismo producto una y otra vez. Esto deja una fila
 * por SKU — la de la cadena donde el índice es peor — y ordena de peor a mejor.
 */
export function peorPorSku(brechas: BrechaPrecio[]): BrechaPrecio[] {
  const peor = new Map<string, BrechaPrecio>();
  for (const b of brechas) {
    const actual = peor.get(b.sku);
    if (!actual || b.indice_precio > actual.indice_precio) peor.set(b.sku, b);
  }
  return [...peor.values()].sort((a, b) => b.indice_precio - a.indice_precio);
}
