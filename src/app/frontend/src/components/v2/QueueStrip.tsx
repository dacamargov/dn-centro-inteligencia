import { Zap, Shield } from 'lucide-react';
import { Kpis, Recomendacion, Severity } from '../../lib/api';
import { fmtDecimal, relTime } from '../../lib/format';
import { estimarImpacto } from '../../lib/impact';
import { AGENT_META } from '../../lib/icons';

const SEV_DOT: Record<Severity, string> = {
  critical: 'bg-red-500', high: 'bg-orange-500', medium: 'bg-dn-400', low: 'bg-humo',
};

interface Props {
  items: Recomendacion[];
  kpis: Kpis | null;
  onPromote: (id: string) => void;
}

/**
 * Horizontal queue of pending recs (excluding the hero).
 * Scrolls horizontally on overflow, no vertical stack of cards.
 */
export default function QueueStrip({ items, kpis, onPromote }: Props) {
  if (items.length === 0) return null;
  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[10px] uppercase tracking-[0.25em] text-grafito font-semibold">
          Próximas en la fila · {items.length}
        </h2>
        <span className="text-[10px] uppercase tracking-widest text-humo">
          clic para promover al destacado
        </span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-2 px-2 snap-x">
        {items.map((r) => {
          const meta = AGENT_META[r.agent_name];
          const AgentI = meta?.Icon;
          const agentColor = meta?.color ?? '#6C7F93';
          const impact = estimarImpacto(r, kpis);
          return (
            <button
              key={r.id}
              onClick={() => onPromote(r.id)}
              className="snap-start flex-shrink-0 w-[260px] text-left bg-white border border-marco hover:border-marco rounded-xl px-3.5 py-3 transition-colors"
            >
              <header className="flex items-start gap-2 mb-1.5">
                <div
                  className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: `${agentColor}22`, border: `1px solid ${agentColor}55`, color: agentColor }}
                >
                  {AgentI && <AgentI className="w-3.5 h-3.5" strokeWidth={2} />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${SEV_DOT[r.severity]}`} />
                    <span className="text-[9px] uppercase tracking-widest text-grafito font-bold">
                      {r.severity.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-[10px] text-humo tabular-nums leading-none mt-0.5">
                    {relTime(r.created_at)}
                  </div>
                </div>
              </header>
              <div className="text-[13px] font-semibold text-tinta leading-snug line-clamp-2 mb-2">
                {r.title}
              </div>
              {impact.pp > 0 && (
                <div
                  className={[
                    'inline-flex items-center gap-1 text-[10.5px] font-medium px-1.5 py-0.5 rounded-full border',
                    impact.esProtectivo
                      ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-600'
                      : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600',
                  ].join(' ')}
                >
                  {impact.esProtectivo
                    ? <Shield className="w-3 h-3" strokeWidth={2.5} />
                    : <Zap className="w-3 h-3" strokeWidth={2.5} fill="currentColor" />}
                  {impact.esProtectivo ? '~' : '+'}{fmtDecimal(impact.pp)} pp
                </div>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
