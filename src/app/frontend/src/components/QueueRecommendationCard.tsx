import { Bot, Shield, Zap } from 'lucide-react';
import { Kpis, Recomendacion, Severity } from '../lib/api';
import { fmtDecimal, relTime } from '../lib/format';
import { estimarImpacto } from '../lib/impact';
import { AGENT_META } from '../lib/icons';

const SEV_BAR: Record<Severity, string> = {
  critical: 'before:bg-red-500',
  high:     'before:bg-orange-500',
  medium:   'before:bg-dn-400',
  low:      'before:bg-humo',
};

const SEV_DOT: Record<Severity, string> = {
  critical: 'bg-red-500', high: 'bg-orange-500', medium: 'bg-dn-400', low: 'bg-humo',
};

const SEV_LABEL: Record<Severity, string> = {
  critical: 'CRÍTICO', high: 'ALTO', medium: 'MEDIO', low: 'BAJO',
};

interface Props {
  rec: Recomendacion;
  kpis: Kpis | null;
  onDecide: (id: string, action: 'APPROVED' | 'REJECTED') => Promise<void>;
  onPromote?: () => void;
}

export default function QueueRecommendationCard({ rec, kpis, onDecide, onPromote }: Props) {
  const agent = AGENT_META[rec.agent_name] ?? { Icon: Bot, color: '#7b8fa8', name: rec.agent_name, tagline: '' };
  const impact = estimarImpacto(rec, kpis);
  const sevBar = SEV_BAR[rec.severity] ?? SEV_BAR.low;

  return (
    <article
      className={[
        'group relative bg-white border border-marco rounded-xl pl-4 pr-3 py-3.5',
        'flex flex-col gap-2.5 overflow-hidden transition-all',
        'hover:border-marco hover:bg-white',
        'before:content-[""] before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1',
        sevBar,
      ].join(' ')}
    >
      <header className="flex items-start gap-2.5">
        <div
          className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: `${agent.color}1f`, border: `1px solid ${agent.color}66`, color: agent.color }}
        >
          <agent.Icon className="w-4 h-4" strokeWidth={1.8} />
        </div>
        <div className="flex-1 min-w-0 leading-tight">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`w-1.5 h-1.5 rounded-full ${SEV_DOT[rec.severity]}`} />
            <span className="text-[10px] font-bold uppercase tracking-widest text-grafito">
              {SEV_LABEL[rec.severity]}
            </span>
            <span className="text-[10px] uppercase tracking-widest text-humo truncate">
              {agent.name}
            </span>
          </div>
          <div className="text-sm font-semibold text-tinta leading-snug mt-1 line-clamp-2">
            {rec.title}
          </div>
        </div>
        <span className="text-[10px] text-humo tabular-nums shrink-0 mt-0.5">
          {relTime(rec.created_at)}
        </span>
      </header>

      {impact.pp > 0 && (
        <div
          className={[
            'inline-flex items-center gap-1.5 self-start text-[11px] font-medium px-2 py-0.5 rounded-full border',
            impact.esProtectivo
              ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-600'
              : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600',
          ].join(' ')}
        >
          {impact.esProtectivo
            ? <Shield className="w-3 h-3" strokeWidth={2} />
            : <Zap className="w-3 h-3" strokeWidth={2} fill="currentColor" />}
          {impact.esProtectivo ? '~' : '+'}{fmtDecimal(impact.pp)} pp · {impact.horizonte}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 mt-1">
        <button
          onClick={() => onDecide(rec.id, 'APPROVED')}
          className="py-1.5 rounded-md text-[11px] font-bold uppercase tracking-wider bg-emerald-500/15 border border-emerald-500/40 text-emerald-600 hover:bg-emerald-500/25 hover:text-emerald-700 transition-colors"
        >
          Despachar
        </button>
        <button
          onClick={() => onDecide(rec.id, 'REJECTED')}
          className="py-1.5 rounded-md text-[11px] font-medium uppercase tracking-wider bg-white border border-marco text-grafito hover:text-tinta transition-colors"
        >
          Descartar
        </button>
      </div>

      {onPromote && (
        <button
          onClick={onPromote}
          className="absolute top-2.5 right-3 opacity-0 group-hover:opacity-100 text-[10px] text-humo hover:text-dn-600 transition-opacity"
          title="Traer a destacado"
        >
          ↥ destacar
        </button>
      )}
    </article>
  );
}
