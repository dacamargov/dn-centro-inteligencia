import { Tag } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api, BrechaPrecio, PrecioCadena } from '../../lib/api';
import { bandera, fmtDecimal, fmtPrecio } from '../../lib/format';
import { peorPorSku } from '../../lib/precio';
import SkuPrecioCard from './SkuPrecioCard';

export default function PrecioPromoDetail() {
  const [brechas, setBrechas] = useState<BrechaPrecio[]>([]);
  const [cadenas, setCadenas] = useState<PrecioCadena[]>([]);

  const onPromoLanzada = useCallback((sku: string) => {
    setBrechas((cur) => cur.filter((b) => b.sku !== sku));
  }, []);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [b, ca] = await Promise.all([
          api.brechasPrecio(),
          api.preciosPorCadena(),
        ]);
        if (!active) return;
        setBrechas(b);
        setCadenas(ca);
      } catch {
        /* mantiene el último dato bueno */
      }
    };
    tick();
    const id = setInterval(tick, 20000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const idxTone = (idx: number) =>
    idx >= 108 ? 'text-red-600' : idx <= 95 ? 'text-emerald-600' : 'text-dn-600';

  const topCadenas = [...cadenas].sort((a, b) => b.indice_cliente - a.indice_cliente).slice(0, 6);

  // Los tres peores abren el simulador acá mismo: el drill-down del agente es
  // donde se toma la decisión, no solo donde se mira la lista.
  const simulables = peorPorSku(brechas).slice(0, 3);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {simulables.length > 0 && (
        <section className="lg:col-span-3 space-y-3">
          {simulables.map((b, i) => (
            <SkuPrecioCard
              key={`${b.sku}-${b.cadena}-${b.country_code}`}
              sku={b}
              rank={i + 1}
              onPromoLanzada={onPromoLanzada}
            />
          ))}
        </section>
      )}

      <section className="lg:col-span-3 rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
            <Tag className="w-3.5 h-3.5 text-red-600" strokeWidth={2} />
            SKUs sobre la banda de precio
          </h3>
          <p className="text-[11px] text-humo mt-0.5">
            índice normalizado por contenido dentro de la subcategoría
          </p>
        </header>
        <div className="overflow-x-auto max-h-[340px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-nieve sticky top-0">
              <tr className="text-left text-[10px] uppercase tracking-widest text-humo">
                <th className="px-4 py-2 font-medium">Producto</th>
                <th className="px-4 py-2 font-medium">Cadena</th>
                <th className="px-4 py-2 font-medium text-right">Nuestro</th>
                <th className="px-4 py-2 font-medium text-right">Rival</th>
                <th className="px-4 py-2 font-medium text-right">Índice</th>
              </tr>
            </thead>
            <tbody>
              {brechas.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-humo text-sm">
                    ningún SKU fuera de banda
                  </td>
                </tr>
              )}
              {brechas.slice(0, 15).map((r, i) => (
                <tr key={`${r.sku}-${i}`} className="border-b border-marco hover:bg-nieve">
                  <td className="px-4 py-2">
                    <div className="text-tinta text-[13px] truncate">
                      {r.producto ?? r.sku}
                    </div>
                    <div className="text-[10px] text-humo font-mono">{r.marca}</div>
                  </td>
                  <td className="px-4 py-2 text-grafito text-[12px]">
                    {bandera(r.country_code)} {r.cadena}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-grafito">
                    {fmtPrecio(r.precio_usd)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-grafito">
                    {r.precio_rival_usd != null ? fmtPrecio(r.precio_rival_usd) : '—'}
                  </td>
                  <td
                    className={`px-4 py-2 text-right tabular-nums font-semibold ${idxTone(r.indice_precio)}`}
                  >
                    {fmtDecimal(r.indice_precio)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="lg:col-span-3 rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
            Cadenas donde más pesa el sobreprecio
          </h3>
        </header>
        <div className="p-4 grid grid-cols-2 md:grid-cols-6 gap-3">
          {topCadenas.map((c) => (
            <div
              key={`${c.country_code}-${c.cadena}`}
              className="rounded-lg bg-nieve border border-marco px-3 py-2.5"
            >
              <div className="text-[12px] font-semibold text-tinta truncate">
                {bandera(c.country_code)} {c.cadena}
              </div>
              <div className={`text-lg font-bold tabular-nums ${idxTone(c.indice_cliente)}`}>
                {fmtDecimal(c.indice_cliente)}
              </div>
              <div className="text-[10px] text-humo tabular-nums">
                rival {fmtDecimal(c.indice_competencia)}
              </div>
            </div>
          ))}
          {topCadenas.length === 0 && (
            <div className="col-span-full text-center py-6 text-humo text-sm">
              sin datos por cadena
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
