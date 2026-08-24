import { AlertTriangle, LayoutGrid, Loader2, MapPin, User, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, Pdv, PdvDetalle } from '../lib/api';
import { bandera, fmtDecimal, fmtNumber, relTime } from '../lib/format';
import { CATEGORY_ICON } from '../lib/icons';

const ESTADO_STYLE: Record<Pdv['estado'], { label: string; cls: string }> = {
  ok:           { label: 'EN META',      cls: 'text-emerald-600 bg-emerald-500/15 border-emerald-500/40' },
  riesgo:       { label: 'EN RIESGO',    cls: 'text-orange-600 bg-orange-500/15 border-orange-500/40' },
  critico:      { label: 'CRÍTICO',      cls: 'text-red-600 bg-red-500/15 border-red-500/40' },
  sin_medicion: { label: 'SIN MEDICIÓN', cls: 'text-grafito bg-dn-100/40 border-marco' },
};

export default function PdvDetailPanel({
  pdv,
  onClose,
}: {
  pdv: Pdv | null;
  onClose: () => void;
}) {
  const [detalle, setDetalle] = useState<PdvDetalle | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pdv) return;
    let active = true;
    setLoading(true);
    setError(null);
    setDetalle(null);
    api
      .pdvDetalle(pdv.store_id)
      .then((d) => {
        if (active) setDetalle(d);
      })
      .catch((e) => {
        if (active) setError(e?.message ?? String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [pdv?.store_id]);

  useEffect(() => {
    if (!pdv) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pdv, onClose]);

  const open = pdv !== null;
  const estado = pdv ? ESTADO_STYLE[pdv.estado] : null;

  return (
    <>
      <div
        onClick={onClose}
        className={[
          'fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity duration-200',
          open ? 'opacity-100' : 'opacity-0 pointer-events-none',
        ].join(' ')}
      />
      <aside
        className={[
          'fixed top-0 right-0 z-50 h-screen w-full max-w-[520px]',
          'bg-nieve border-l border-marco shadow-2xl',
          'transform transition-transform duration-300 ease-out flex flex-col',
          open ? 'translate-x-0' : 'translate-x-full',
        ].join(' ')}
        aria-hidden={!open}
      >
        {pdv && estado && (
          <>
            <header className="flex items-start justify-between gap-3 px-5 py-4 border-b border-marco">
              <div className="min-w-0">
                <div className="text-[10px] uppercase tracking-[0.22em] text-humo mb-0.5">
                  Punto de venta
                </div>
                <h2 className="text-xl font-bold text-tinta truncate">
                  {bandera(pdv.country_code)} {pdv.nombre}
                </h2>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-widest ${estado.cls}`}
                  >
                    {estado.label}
                  </span>
                  <span className="text-[11px] text-grafito inline-flex items-center gap-1">
                    <MapPin className="w-3 h-3" strokeWidth={2} />
                    {pdv.ciudad} · {pdv.cadena} · {pdv.formato}
                  </span>
                </div>
                {pdv.mercaderista && (
                  <div className="text-[11px] text-humo mt-1 inline-flex items-center gap-1">
                    <User className="w-3 h-3" strokeWidth={2} />
                    {pdv.mercaderista} · meta {pdv.visitas_mes_meta} visitas/mes
                  </div>
                )}
              </div>
              <button
                onClick={onClose}
                className="text-humo hover:text-tinta transition-colors p-1 rounded hover:bg-white"
                aria-label="Cerrar"
              >
                <X className="w-5 h-5" />
              </button>
            </header>

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
              <section className="grid grid-cols-3 gap-2">
                <Stat label="Disponibilidad" value={pdv.disponibilidad_pct} />
                <Stat label="Ejecución" value={pdv.ejecucion_pct} />
                <Stat label="Share of shelf" value={pdv.sos_pct} />
              </section>

              <div className="text-[11px] text-humo">
                {fmtNumber(pdv.observaciones)} lecturas en la ventana ·{' '}
                {pdv.ultima_visita ? `última ${relTime(pdv.ultima_visita)}` : 'sin visita reciente'}
              </div>

              {error && (
                <div className="text-red-600 text-xs bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}
              {loading && (
                <div className="flex items-center gap-2 text-grafito text-[11px]">
                  <Loader2 className="w-3 h-3 animate-spin" /> Cargando detalle…
                </div>
              )}

              {detalle && detalle.por_categoria.length > 0 && (
                <section>
                  <h3 className="text-[10px] uppercase tracking-[0.22em] text-humo mb-2">
                    Ejecución por categoría
                  </h3>
                  <div className="space-y-1.5">
                    {detalle.por_categoria.map((c) => {
                      const CI = CATEGORY_ICON[c.categoria];
                      return (
                        <div
                          key={c.categoria}
                          className="rounded-lg border border-marco bg-white px-3 py-2"
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="inline-flex items-center gap-1.5 text-[12px] text-tinta font-medium truncate">
                              {CI && <CI className="w-3.5 h-3.5 text-grafito" strokeWidth={1.8} />}
                              {c.categoria}
                            </span>
                            <span className="text-[11px] text-humo tabular-nums shrink-0">
                              {c.observaciones} lecturas
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-[10.5px] tabular-nums">
                            <span className="text-grafito">
                              disp{' '}
                              <span className="text-tinta">{fmtDecimal(c.disponibilidad_pct)}%</span>
                            </span>
                            <span className="text-grafito">
                              ejec{' '}
                              <span className="text-tinta">{fmtDecimal(c.ejecucion_pct)}%</span>
                            </span>
                            <span className="text-grafito">
                              SOS <span className="text-tinta">{fmtDecimal(c.sos_pct)}%</span>
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {detalle && detalle.quiebres.length > 0 && (
                <section>
                  <h3 className="text-[10px] uppercase tracking-[0.22em] text-humo mb-2">
                    SKUs agotados ahora
                  </h3>
                  <div className="space-y-1.5">
                    {detalle.quiebres.map((q) => (
                      <div
                        key={q.sku}
                        className="flex items-center gap-2.5 rounded-lg border border-red-500/25 bg-red-500/[0.06] px-3 py-2"
                      >
                        <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" strokeWidth={2} />
                        <div className="min-w-0 flex-1">
                          <div className="text-[12px] text-tinta truncate">
                            {q.emoji ?? ''} {q.producto ?? q.sku}
                          </div>
                          <div className="text-[10px] text-humo truncate">
                            {q.marca} · {q.categoria} ·{' '}
                            {q.ultima_lectura ? relTime(q.ultima_lectura) : 's/d'}
                          </div>
                        </div>
                        {!q.planograma_ok && (
                          <LayoutGrid className="w-3.5 h-3.5 text-orange-600 shrink-0" strokeWidth={2} />
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {detalle && detalle.quiebres.length === 0 && !loading && (
                <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/[0.06] px-3 py-3 text-[12px] text-emerald-700">
                  Sin quiebres del cliente en este PDV durante la ventana medida.
                </div>
              )}
            </div>
          </>
        )}
      </aside>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg border border-marco bg-white px-3 py-2">
      <div className="text-[9.5px] uppercase tracking-wider text-humo">{label}</div>
      <div className="text-lg font-bold tabular-nums text-tinta leading-tight">
        {value == null ? '—' : `${fmtDecimal(value)}%`}
      </div>
    </div>
  );
}
