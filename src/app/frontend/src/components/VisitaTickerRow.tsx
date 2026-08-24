import { AlertTriangle, Check, LayoutGrid, X } from 'lucide-react';
import { ReactNode } from 'react';
import { Visita } from '../lib/api';
import { bandera, fmtPrecio, relTime } from '../lib/format';

export default function VisitaTickerRow({ visita, esNueva }: { visita: Visita; esNueva?: boolean }) {
  const quiebre = visita.es_cliente && !visita.en_stock;
  return (
    <div
      className={[
        'flex items-center gap-3 px-4 py-2.5 border-b border-marco transition-colors',
        quiebre ? 'bg-red-500/[0.05] hover:bg-red-500/[0.09]' : 'hover:bg-white',
        esNueva ? 'animate-flash' : '',
      ].join(' ')}
    >
      <div className="font-mono text-[11px] uppercase text-humo w-9 shrink-0 text-center">
        {bandera(visita.country_code)}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 text-sm text-tinta truncate">
          <span className="truncate">{visita.producto ?? visita.sku}</span>
          {visita.es_cliente && (
            <span className="shrink-0 text-[9px] uppercase tracking-wider font-bold text-dn-600 bg-dn-400/10 border border-dn-400/25 rounded px-1">
              cliente
            </span>
          )}
        </div>
        <div className="text-[11px] text-humo truncate">
          {visita.cadena} · {visita.ciudad} · {visita.canal.toLowerCase()} · {visita.facings} caras
        </div>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        {visita.en_stock ? (
          <Check className="w-3.5 h-3.5 text-emerald-600" strokeWidth={2.5} />
        ) : (
          <X className="w-3.5 h-3.5 text-red-600" strokeWidth={2.5} />
        )}
        {!visita.planograma_ok && (
          <LayoutGrid className="w-3.5 h-3.5 text-orange-600" strokeWidth={2} />
        )}
        {quiebre && <AlertTriangle className="w-3.5 h-3.5 text-red-600" strokeWidth={2} />}
      </div>

      <div className="text-right shrink-0 w-20">
        <div className="font-mono text-sm tabular-nums text-dn-600">
          {visita.precio_usd != null ? fmtPrecio(visita.precio_usd) : '—'}
        </div>
        <div className="text-[10px] text-humo">{relTime(visita.visit_ts)}</div>
      </div>
    </div>
  );
}

function Clave({ figura, children }: { figura: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <span className="inline-flex items-center justify-center min-w-4 shrink-0">{figura}</span>
      {children}
    </span>
  );
}

/** Descifra los iconos del ticker.
 *
 * Vive al lado de la fila a propósito: son las mismas figuras con los mismos
 * colores, y separarlas en otro archivo es la receta para que un día la leyenda
 * describa un icono que ya no existe.
 */
export function LeyendaTicker() {
  return (
    <div className="px-4 py-2.5 border-t border-marco bg-nieve">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-humo">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-grafito">
          Cómo leerlo
        </span>

        <Clave figura={<Check className="w-3.5 h-3.5 text-emerald-600" strokeWidth={2.5} />}>
          el SKU está en anaquel
        </Clave>

        <Clave figura={<X className="w-3.5 h-3.5 text-red-600" strokeWidth={2.5} />}>
          quiebre: no se encontró
        </Clave>

        <Clave figura={<LayoutGrid className="w-3.5 h-3.5 text-orange-600" strokeWidth={2} />}>
          fuera de planograma
        </Clave>

        <Clave figura={<AlertTriangle className="w-3.5 h-3.5 text-red-600" strokeWidth={2} />}>
          quiebre en producto del cliente
        </Clave>

        <Clave
          figura={
            <span className="text-[9px] uppercase tracking-wider font-bold text-dn-600 bg-dn-400/10 border border-dn-400/25 rounded px-1">
              cliente
            </span>
          }
        >
          marca del cliente; el resto es competencia
        </Clave>
      </div>

      <p className="mt-1.5 text-[11px] text-humo">
        <strong className="font-semibold text-grafito">caras</strong> son los frentes visibles
        del producto en el anaquel. Un SKU en anaquel pero fuera de planograma (
        <Check className="inline w-3 h-3 text-emerald-600 -mt-0.5" strokeWidth={2.5} />
        {' + '}
        <LayoutGrid className="inline w-3 h-3 text-orange-600 -mt-0.5" strokeWidth={2} />) es la
        falla más rentable: se corrige moviéndolo, sin reponer nada.
      </p>
    </div>
  );
}
