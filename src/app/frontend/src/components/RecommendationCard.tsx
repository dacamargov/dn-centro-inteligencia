import { Bot, Shield, Zap } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { Kpis, Recomendacion, Severity } from '../lib/api';
import { fmtDecimal, relTime } from '../lib/format';
import { estimarImpacto } from '../lib/impact';
import { AGENT_META } from '../lib/icons';
import { ACTION_TYPE_LABEL } from './TopActionBanner';
import SeverityPill from './SeverityPill';

const SEV_BAR: Record<Severity, string> = {
  critical: 'before:bg-red-500 before:shadow-[0_0_22px_-2px_rgba(239,68,68,0.65)]',
  high:     'before:bg-orange-500 before:shadow-[0_0_18px_-2px_rgba(249,115,22,0.55)]',
  medium:   'before:bg-dn-400 before:shadow-[0_0_14px_-2px_rgba(51,189,238,0.45)]',
  low:      'before:bg-humo',
};

interface Props {
  rec: Recomendacion;
  onDecide: (id: string, action: 'APPROVED' | 'REJECTED') => Promise<void>;
  kpis?: Kpis | null;
  /**
   * Botón para ejecutar la acción concreta que propone el agente, no solo
   * aprobarla. Aprobar deja constancia; esto la hace pasar.
   */
  accionPrimaria?: ReactNode;
}

export default function RecomendacionCard({ rec, onDecide, kpis, accionPrimaria }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const agent = AGENT_META[rec.agent_name] ?? {
    Icon: Bot, color: '#7b8fa8', name: rec.agent_name, tagline: '',
  };
  const sa = (rec.suggested_action as any) ?? {};
  const actionType = sa.type ?? 'other';
  const actionLabel = ACTION_TYPE_LABEL[actionType] ?? actionType;
  const impact = estimarImpacto(rec, kpis ?? null);
  const decided = rec.status !== 'pending';
  const sevBar = SEV_BAR[rec.severity] ?? SEV_BAR.low;

  async function decide(a: 'APPROVED' | 'REJECTED') {
    setBusy(true);
    try {
      await onDecide(rec.id, a);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article
      className={[
        'relative bg-white border rounded-lg pl-6 pr-5 py-4',
        'overflow-hidden transition-colors duration-150',
        'before:content-[""] before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1',
        sevBar,
        decided ? 'border-marco opacity-80' : 'border-marco hover:border-marco',
      ].join(' ')}
    >
      {/* Header row */}
      <div className="flex items-start gap-3 mb-2.5">
        {/* Agent avatar */}
        <div
          className="flex-shrink-0 w-11 h-11 rounded-lg flex items-center justify-center"
          style={{
            backgroundColor: `${agent.color}20`,
            border: `1px solid ${agent.color}66`,
            color: agent.color,
          }}
          title={agent.name}
        >
          <agent.Icon className="w-5 h-5" strokeWidth={1.8} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <SeverityPill severity={rec.severity} />
            <span className="text-[10px] uppercase tracking-widest text-humo font-medium">
              {agent.name}
            </span>
            {decided && (
              <span
                className={[
                  'text-[10px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded border',
                  rec.status === 'approved'
                    ? 'bg-emerald-500/15 text-emerald-600 border-emerald-500/40'
                    : 'bg-dn-100/40 text-grafito border-marco',
                ].join(' ')}
              >
                {rec.status === 'approved' ? '✓ APROBADO' : '✗ RECHAZADO'}
              </span>
            )}
          </div>
          <h3 className="text-base font-semibold text-tinta leading-snug mt-1">
            {rec.title}
          </h3>
        </div>

        <span className="text-[11px] text-humo tabular-nums shrink-0 mt-1">
          {relTime(rec.created_at)}
        </span>
      </div>

      {/* Analysis */}
      {rec.analysis && (
        <p className="text-[13px] text-grafito leading-relaxed mb-3 line-clamp-3">
          {rec.analysis}
        </p>
      )}

      {/* Action + impact strip */}
      <div className="flex items-center gap-3 flex-wrap mb-3">
        <span
          className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full border"
          style={{
            borderColor: `${agent.color}66`,
            backgroundColor: `${agent.color}12`,
            color: agent.color,
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: agent.color }} />
          {actionLabel}
        </span>

        {impact.pp > 0 && (
          <span
            className={[
              'inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full border',
              impact.esProtectivo
                ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-600'
                : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600',
            ].join(' ')}
            title={impact.racional}
          >
            {impact.esProtectivo
              ? <Shield className="w-3 h-3" strokeWidth={2} />
              : <Zap className="w-3 h-3" strokeWidth={2} fill="currentColor" />}
            {impact.esProtectivo ? 'protege ~' : '+'}{fmtDecimal(impact.pp)} pp de {impact.metrica}
            {' '}en {impact.horizonte}
          </span>
        )}

        <span className="text-[10px] uppercase tracking-widest text-humo ml-auto">
          conf: {impact.confianza}
        </span>
      </div>

      {/* Recomendacion callout */}
      <div className="bg-nieve border border-marco rounded px-3.5 py-2.5 mb-3">
        <div className="text-[10px] uppercase tracking-widest text-humo mb-0.5">
          recomendación
        </div>
        <p className="text-[13.5px] text-tinta leading-relaxed">{rec.recommendation}</p>
      </div>

      {accionPrimaria && <div className="mb-2.5">{accionPrimaria}</div>}

      {/* Action buttons */}
      <div className="flex gap-2">
        {!decided && (
          <>
            <button
              disabled={busy}
              onClick={() => decide('APPROVED')}
              className={[
                'flex-1 px-4 py-2 text-sm font-semibold uppercase tracking-wider rounded-md',
                'bg-emerald-500/15 border border-emerald-500/50 text-emerald-600',
                'hover:bg-emerald-500/25 hover:border-emerald-400 hover:text-emerald-700',
                'transition-all disabled:opacity-50 disabled:cursor-not-allowed',
                'shadow-[0_0_16px_-6px_rgba(16,185,129,0.5)]',
              ].join(' ')}
            >
              {busy ? '…' : '✓ Aprobar'}
            </button>
            <button
              disabled={busy}
              onClick={() => decide('REJECTED')}
              className={[
                'flex-1 px-4 py-2 text-sm font-medium uppercase tracking-wider rounded-md',
                'bg-white border border-marco text-grafito',
                'hover:bg-dn-100 hover:text-tinta',
                'transition-all disabled:opacity-50 disabled:cursor-not-allowed',
              ].join(' ')}
            >
              ✗ Rechazar
            </button>
          </>
        )}
        <button
          onClick={() => setOpen((o) => !o)}
          className={[
            'px-4 py-2 text-xs font-medium uppercase tracking-wider rounded-md',
            'bg-white border border-marco text-grafito',
            'hover:bg-white hover:text-tinta transition-all',
            decided ? 'flex-1' : '',
          ].join(' ')}
        >
          {open ? '▴ Ocultar' : '▾ Detalles'}
        </button>
      </div>

      {/* Decision footer if decided */}
      {decided && rec.decision && (
        <div className="mt-3 pt-3 border-t border-marco text-[11px] text-humo">
          <span className={rec.status === 'approved' ? 'text-emerald-600' : 'text-grafito'}>
            {rec.status === 'approved' ? '✓' : '✗'}
          </span>{' '}
          decidido por <span className="text-grafito">{rec.decision.actor}</span>
          {rec.decision.notes && <span> · "{rec.decision.notes}"</span>}
          <span className="text-humo ml-1">· {relTime(rec.decision.occurred_at)}</span>
        </div>
      )}

      {/* Expandable JSON details */}
      {open && (
        <div className="mt-4 grid md:grid-cols-2 gap-3">
          <DetailBlock title="suggested_action" data={rec.suggested_action} />
          <DetailBlock title="supporting_data" data={rec.supporting_data} />
        </div>
      )}
    </article>
  );
}

function DetailBlock({ title, data }: { title: string; data: any }) {
  if (!data || (typeof data === 'object' && Object.keys(data).length === 0)) {
    return (
      <div className="bg-nieve border border-marco rounded p-3">
        <div className="text-[10px] uppercase tracking-widest text-humo mb-1">{title}</div>
        <div className="text-xs text-humo">vacío</div>
      </div>
    );
  }
  // Pretty key-value rendering when it's a flat object
  const isFlat = typeof data === 'object' && !Array.isArray(data) && Object.values(data).every(
    (v) => v === null || ['string', 'number', 'boolean'].includes(typeof v),
  );
  if (isFlat) {
    return (
      <div className="bg-nieve border border-marco rounded p-3">
        <div className="text-[10px] uppercase tracking-widest text-humo mb-1.5">{title}</div>
        <dl className="space-y-1">
          {Object.entries(data as Record<string, any>).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 text-[12px] border-b border-marco pb-1 last:border-0">
              <dt className="text-humo">{k}</dt>
              <dd className="text-tinta font-mono tabular-nums text-right break-all">
                {v === null || v === '' ? <span className="text-humo">—</span> : String(v)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    );
  }
  // Nested → keep the JSON dump but pretty
  return (
    <div className="bg-nieve border border-marco rounded p-3 overflow-hidden">
      <div className="text-[10px] uppercase tracking-widest text-humo mb-1">{title}</div>
      <pre className="text-[11px] font-mono text-grafito whitespace-pre-wrap break-words">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
