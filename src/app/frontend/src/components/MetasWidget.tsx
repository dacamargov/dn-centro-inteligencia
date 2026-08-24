import { ArrowDownRight, ArrowRight, ArrowUpRight, type LucideIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, MetaCategoria } from '../lib/api';
import { fmtDecimal } from '../lib/format';
import { CATEGORY_ICON } from '../lib/icons';
import CategoryDrillDrawer from './CategoryDrillDrawer';

const STATUS_STYLE: Record<
  MetaCategoria['status'],
  { bar: string; pill: string; pillBg: string; pillBorder: string; Icon: LucideIcon; label: string }
> = {
  above: {
    bar: 'bg-emerald-500/55', pill: 'text-emerald-600', pillBg: 'bg-emerald-500/15',
    pillBorder: 'border-emerald-500/40', Icon: ArrowUpRight, label: 'sobre meta',
  },
  on: {
    bar: 'bg-dn-400/55', pill: 'text-dn-600', pillBg: 'bg-dn-400/15',
    pillBorder: 'border-dn-400/40', Icon: ArrowRight, label: 'en meta',
  },
  behind: {
    bar: 'bg-red-500/55', pill: 'text-red-600', pillBg: 'bg-red-500/15',
    pillBorder: 'border-red-500/40', Icon: ArrowDownRight, label: 'bajo meta',
  },
};

export default function MetasWidget() {
  const [data, setData] = useState<MetaCategoria[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [drillCategoria, setDrillCategoria] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const r = await api.metas();
        if (active) {
          setData(r);
          setError(null);
        }
      } catch (e: any) {
        if (active) setError(e?.message ?? String(e));
      }
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const conDato = data.filter((c) => c.observaciones > 0);
  const obsTotal = conDato.reduce((a, c) => a + c.obs_cliente, 0);
  // Ponderamos por observaciones del cliente para que una categoría con poca
  // muestra no arrastre el indicador global.
  const paceGlobal =
    obsTotal > 0
      ? conDato.reduce((a, c) => a + c.cumplimiento_pct * c.obs_cliente, 0) / obsTotal
      : 0;
  const ejecPromedio =
    obsTotal > 0
      ? conDato.reduce((a, c) => a + (c.ejecucion_pct ?? 0) * c.obs_cliente, 0) / obsTotal
      : 0;
  const metaPromedio =
    obsTotal > 0
      ? conDato.reduce((a, c) => a + c.meta_ejecucion_pct * c.obs_cliente, 0) / obsTotal
      : 0;

  return (
    <section className="rounded-xl border border-marco bg-white overflow-hidden">
      <header className="flex items-center justify-between gap-3 px-5 py-3 border-b border-marco">
        <div>
          <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
            Meta vs Realizado · ejecución por categoría
          </h2>
          <p className="text-[11px] text-humo mt-0.5">
            ejecución perfecta medida contra la meta del cliente · barra llena = 100% de la meta
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-widest text-humo">
              Ejecución realizada
            </div>
            <div className="text-xl font-bold text-tinta tabular-nums">
              {obsTotal > 0 ? `${fmtDecimal(ejecPromedio)}%` : '—'}
            </div>
          </div>
          <div className="text-right pl-3 border-l border-marco">
            <div className="text-[10px] uppercase tracking-widest text-humo">Meta ponderada</div>
            <div className="text-xl font-bold text-dn-600 tabular-nums">
              {obsTotal > 0 ? `${fmtDecimal(metaPromedio)}%` : '—'}
            </div>
          </div>
          {obsTotal > 0 && (() => {
            const status: MetaCategoria['status'] =
              paceGlobal >= 105 ? 'above' : paceGlobal >= 95 ? 'on' : 'behind';
            const s = STATUS_STYLE[status];
            return (
              <span
                className={[
                  'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-bold uppercase tracking-widest',
                  s.pillBg, s.pillBorder, s.pill,
                ].join(' ')}
              >
                <s.Icon className="w-3 h-3" strokeWidth={2.5} />
                {s.label} · {paceGlobal.toFixed(0)}%
              </span>
            );
          })()}
        </div>
      </header>

      {error && (
        <div className="px-5 py-2 text-red-600 text-xs bg-red-500/10 border-b border-red-500/30">
          {error}
        </div>
      )}

      <div className="p-3 grid grid-cols-2 md:grid-cols-5 gap-2">
        {data.map((t) => {
          const s = STATUS_STYLE[t.status];
          const capped = Math.min(100, t.cumplimiento_pct);
          const overshoot = t.cumplimiento_pct > 100;
          const CI = CATEGORY_ICON[t.categoria];
          return (
            <button
              key={t.categoria}
              type="button"
              onClick={() => setDrillCategoria(t.categoria)}
              className="bg-nieve border border-marco rounded-lg p-3 text-left transition-colors hover:border-dn-400/60 hover:bg-nieve focus:outline-none focus:ring-2 focus:ring-dn-400/40"
              title={`Ejecución ${fmtDecimal(t.ejecucion_pct)}% · meta ${t.meta_ejecucion_pct}% · ${t.obs_cliente} lecturas del cliente · clic para el detalle`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-1.5 min-w-0 text-tinta">
                  {CI && <CI className="w-3.5 h-3.5 flex-shrink-0 text-grafito" strokeWidth={1.8} />}
                  <span className="text-[12px] font-semibold truncate">{t.categoria}</span>
                </div>
                <span
                  className={[
                    'inline-flex items-center gap-0.5 text-[10px] font-bold tabular-nums px-1.5 py-px rounded',
                    s.pillBg, s.pill,
                  ].join(' ')}
                >
                  <s.Icon className="w-2.5 h-2.5" strokeWidth={2.5} />
                  {Math.round(t.cumplimiento_pct)}%
                </span>
              </div>

              <div className="relative h-2 rounded-full bg-white overflow-hidden mb-1.5">
                <div
                  className={`absolute top-0 left-0 h-full ${s.bar} transition-[width] duration-700 ease-out`}
                  style={{ width: `${capped}%` }}
                />
                {overshoot && (
                  <div className="absolute top-0 right-0 h-full bg-emerald-300/60" style={{ width: '4%' }} />
                )}
              </div>

              <div className="flex items-baseline justify-between text-[10.5px] text-humo tabular-nums">
                <span className="text-grafito">{fmtDecimal(t.ejecucion_pct)}%</span>
                <span>/ {t.meta_ejecucion_pct}%</span>
              </div>
              <div className="flex items-baseline justify-between text-[10px] text-humo tabular-nums mt-0.5">
                <span>disp {fmtDecimal(t.disponibilidad_pct)}%</span>
                <span>SOS {fmtDecimal(t.sos_pct)}%</span>
              </div>
            </button>
          );
        })}
      </div>
      <CategoryDrillDrawer categoria={drillCategoria} onClose={() => setDrillCategoria(null)} />
    </section>
  );
}
