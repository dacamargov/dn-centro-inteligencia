import { Recomendacion } from '../lib/api';
import { relTime } from '../lib/format';

const AGENT_EMOJI: Record<string, string> = {
  pulso_ejecucion: '📈',
  price_promo: '🎯',
  sentimiento_marca: '💬',
};

interface Props {
  decided: Recomendacion[];
}

export default function DecisionTimeline({ decided }: Props) {
  if (decided.length === 0) {
    return null;
  }
  return (
    <section className="bg-white border border-marco rounded-xl overflow-hidden">
      <header className="px-5 py-3 border-b border-marco flex items-center justify-between">
        <div>
          <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
            Decisiones tomadas
          </h2>
          <p className="text-[11px] text-humo mt-0.5">
            historial de esta sesión · acciones que cambiaron el rumbo de la jornada
          </p>
        </div>
        <span className="text-[11px] text-humo tabular-nums">
          {decided.length} {decided.length === 1 ? 'decisión' : 'decisiones'}
        </span>
      </header>
      <ol className="divide-y divide-marco">
        {decided.slice(0, 10).map((r) => {
          const ok = r.status === 'approved';
          const emoji = AGENT_EMOJI[r.agent_name] ?? '🤖';
          return (
            <li key={r.id} className="px-5 py-2.5 flex items-center gap-3 hover:bg-white transition-colors">
              <div
                className={[
                  'w-7 h-7 rounded-full flex items-center justify-center text-[13px] font-bold shrink-0',
                  ok
                    ? 'bg-emerald-500/15 border border-emerald-500/50 text-emerald-600'
                    : 'bg-dn-100/40 border border-marco text-grafito',
                ].join(' ')}
              >
                {ok ? '✓' : '✗'}
              </div>
              <span className="text-base flex-shrink-0">{emoji}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] text-tinta truncate">{r.title}</div>
                <div className="text-[11px] text-humo">
                  {r.decision?.actor ?? '—'}
                </div>
              </div>
              <span className="text-[11px] text-humo tabular-nums shrink-0">
                {r.decision?.occurred_at ? relTime(r.decision.occurred_at) : relTime(r.created_at)}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
