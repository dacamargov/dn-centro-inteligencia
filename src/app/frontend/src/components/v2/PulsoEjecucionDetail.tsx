import { AlertOctagon, PackageX, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, CategoriaCorte, PaisCorte, SkuCritico } from '../../lib/api';
import { bandera, fmtDecimal, fmtNumber } from '../../lib/format';
import { CATEGORY_ICON } from '../../lib/icons';

export default function PulsoEjecucionDetail() {
  const [skus, setSkus] = useState<SkuCritico[]>([]);
  const [cats, setCats] = useState<CategoriaCorte[]>([]);
  const [paises, setPaises] = useState<PaisCorte[]>([]);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [s, c, p] = await Promise.all([
          api.skusCriticos(30, 12),
          api.visitasPorCategoria(30),
          api.visitasPorPais(30),
        ]);
        if (!active) return;
        setSkus(s);
        setCats(c);
        setPaises(p);
      } catch {
        /* el panel sigue mostrando el último dato bueno */
      }
    };
    tick();
    const id = setInterval(tick, 10000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const dispTone = (pct: number) =>
    pct >= 95 ? 'text-emerald-600' : pct >= 88 ? 'text-orange-600' : 'text-red-600';

  const criticos = skus.filter((s) => s.disponibilidad_pct < 90).slice(0, 3);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <section className="lg:col-span-2 rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-dn-600" strokeWidth={2} />
            SKUs con peor disponibilidad · últimos 30 min
          </h3>
          <p className="text-[11px] text-humo mt-0.5">
            solo marcas del cliente · ordenado por disponibilidad en anaquel
          </p>
        </header>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-nieve">
              <tr className="text-left text-[10px] uppercase tracking-widest text-humo">
                <th className="px-4 py-2 font-medium">#</th>
                <th className="px-4 py-2 font-medium">Producto</th>
                <th className="px-4 py-2 font-medium text-right">Lecturas</th>
                <th className="px-4 py-2 font-medium text-right">PDV afect.</th>
                <th className="px-4 py-2 font-medium text-right">Disponib.</th>
                <th className="px-4 py-2 font-medium text-right">Planograma</th>
              </tr>
            </thead>
            <tbody>
              {skus.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-humo text-sm">
                    sin lecturas en esta ventana
                  </td>
                </tr>
              )}
              {skus.map((s, i) => {
                const CI = CATEGORY_ICON[s.categoria];
                return (
                  <tr key={s.sku} className="border-b border-marco hover:bg-nieve">
                    <td className="px-4 py-2 text-humo tabular-nums w-8">{i + 1}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {CI && (
                          <CI className="w-3.5 h-3.5 text-humo flex-shrink-0" strokeWidth={1.8} />
                        )}
                        <div className="min-w-0">
                          <div className="text-tinta text-[13px] truncate">
                            {s.producto ?? s.sku}
                          </div>
                          <div className="text-[10px] text-humo font-mono">
                            {s.sku} · {s.marca}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-grafito">
                      {fmtNumber(s.observaciones)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-grafito">
                      {s.pdv_afectados}
                    </td>
                    <td
                      className={`px-4 py-2 text-right tabular-nums font-semibold ${dispTone(s.disponibilidad_pct)}`}
                    >
                      {fmtDecimal(s.disponibilidad_pct)}%
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-grafito">
                      {fmtDecimal(s.planograma_pct)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-red-500/30 bg-red-500/[0.04] overflow-hidden">
        <header className="px-5 py-3 border-b border-red-500/30">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-red-600 font-semibold flex items-center gap-2">
            <AlertOctagon className="w-3.5 h-3.5" strokeWidth={2} />
            Quiebres que exigen ruta hoy
          </h3>
          <p className="text-[11px] text-red-600/60 mt-0.5">
            disponibilidad bajo 90% en varios PDV a la vez
          </p>
        </header>
        <div className="p-3 space-y-2">
          {criticos.length === 0 && (
            <div className="text-center py-6 text-humo text-sm">
              Sin quiebres sistemáticos ahora.
              <br />
              La reposición está al día.
            </div>
          )}
          {criticos.map((s) => (
            <div key={s.sku} className="rounded-lg bg-nieve border border-marco px-3 py-2.5">
              <div className="text-[13px] font-semibold text-tinta leading-tight line-clamp-1">
                {s.emoji ?? ''} {s.producto ?? s.sku}
              </div>
              <div className="flex items-center justify-between mt-1.5 text-[11px]">
                <span className="text-humo tabular-nums">
                  {s.pdv_afectados} PDV · {s.quiebres} quiebres
                </span>
                <span className="text-red-600 font-semibold tabular-nums">
                  {fmtDecimal(s.disponibilidad_pct)}%
                </span>
              </div>
              <div className="text-[11px] text-grafito mt-1.5 leading-snug">
                sugerencia: priorizar visita de reposición en la ruta de mañana
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="lg:col-span-2 rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
            Ejecución por categoría · últimos 30 min
          </h3>
        </header>
        <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-3">
          {cats.map((c) => {
            const CI = CATEGORY_ICON[c.categoria];
            return (
              <div key={c.categoria} className="rounded-lg bg-nieve border border-marco px-3 py-2.5">
                <div className="flex items-center gap-1.5 mb-1.5">
                  {CI && <CI className="w-3.5 h-3.5 text-grafito" strokeWidth={1.8} />}
                  <span className="text-[12px] font-semibold text-tinta truncate">
                    {c.categoria}
                  </span>
                </div>
                <div className={`text-lg font-bold tabular-nums ${dispTone(c.disponibilidad_pct)}`}>
                  {fmtDecimal(c.disponibilidad_pct)}%
                </div>
                <div className="flex items-center justify-between mt-1 text-[11px]">
                  <span className="text-humo tabular-nums">{c.pdv} PDV</span>
                  <span className="text-grafito tabular-nums">
                    SOS {fmtDecimal(c.sos_cliente_pct)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
            <PackageX className="w-3.5 h-3.5 text-grafito" strokeWidth={2} />
            Brecha moderno vs tradicional
          </h3>
        </header>
        <div className="p-4 space-y-2">
          {paises.map((p) => {
            const brecha = p.ejecucion_moderno_pct - p.ejecucion_tradicional_pct;
            return (
              <div key={p.country_code} className="flex items-center justify-between gap-2 text-[12px]">
                <span className="text-grafito truncate">
                  {bandera(p.country_code)} {p.pais}
                </span>
                <span className="tabular-nums text-grafito shrink-0">
                  {fmtDecimal(p.ejecucion_moderno_pct)}% /{' '}
                  {fmtDecimal(p.ejecucion_tradicional_pct)}%
                  <span
                    className={`ml-2 font-semibold ${brecha > 8 ? 'text-orange-600' : 'text-humo'}`}
                  >
                    {brecha >= 0 ? '+' : ''}
                    {fmtDecimal(brecha)} pp
                  </span>
                </span>
              </div>
            );
          })}
          {paises.length === 0 && (
            <div className="text-center py-6 text-humo text-sm">sin datos por país</div>
          )}
        </div>
      </section>
    </div>
  );
}
