import { AlertTriangle, Bot, Check, ChevronDown, X } from 'lucide-react';
import { useState } from 'react';
import { Kpis, Recomendacion, Severity } from '../lib/api';
import { fmtDecimal, fmtPrecio, relTime } from '../lib/format';
import { estimarImpacto } from '../lib/impact';
import { AGENT_META } from '../lib/icons';
import { ACTION_TYPE_LABEL } from './TopActionBanner';

const SEV: Record<Severity, { label: string; ring: string; bg: string; text: string; ribbon: string; haloColor: string }> = {
  critical: {
    label: 'CRÍTICO',
    ring: 'border-red-500/50',
    bg: 'from-red-500/[0.12] via-white to-nieve',
    text: 'text-red-600',
    ribbon: 'bg-red-500',
    haloColor: 'rgba(239,68,68,0.35)',
  },
  high: {
    label: 'ALTO',
    ring: 'border-orange-500/45',
    bg: 'from-orange-500/[0.10] via-white to-nieve',
    text: 'text-orange-600',
    ribbon: 'bg-orange-500',
    haloColor: 'rgba(249,115,22,0.30)',
  },
  medium: {
    label: 'MEDIO',
    ring: 'border-dn-400/40',
    bg: 'from-amber-400/[0.08] via-white to-nieve',
    text: 'text-dn-600',
    ribbon: 'bg-dn-400',
    haloColor: 'rgba(51,189,238,0.25)',
  },
  low: {
    label: 'BAJO',
    ring: 'border-marco',
    bg: 'from-white to-nieve',
    text: 'text-grafito',
    ribbon: 'bg-humo',
    haloColor: 'rgba(113,113,122,0.20)',
  },
};

interface Props {
  rec: Recomendacion;
  kpis: Kpis | null;
  onDecide: (id: string, action: 'APPROVED' | 'REJECTED') => Promise<void>;
}

export default function HeroRecommendation({ rec, kpis, onDecide }: Props) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const agent = AGENT_META[rec.agent_name] ?? { Icon: Bot, color: '#6C7F93', name: rec.agent_name, tagline: '' };
  const sa = (rec.suggested_action as any) ?? {};
  const actionType = sa.type ?? 'other';
  const actionLabel = ACTION_TYPE_LABEL[actionType] ?? actionType;
  const params = sa.params ?? {};
  const sev = SEV[rec.severity] ?? SEV.low;
  const impact = estimarImpacto(rec, kpis);

  // Resumen compacto propio de cada tipo de acción, para que el ejecutivo vea
  // el "qué cambia" sin abrir el detalle.
  let actionSummary = '';
  if (actionType === 'ajustar_precio' && params.precio_actual != null && params.precio_sugerido != null) {
    actionSummary = `${fmtPrecio(Number(params.precio_actual))} → ${fmtPrecio(Number(params.precio_sugerido))}`;
  } else if (actionType === 'visita_prioritaria' || actionType === 'corregir_planograma') {
    const parts: string[] = [];
    if (params.categoria) parts.push(params.categoria);
    if (params.pdv != null) parts.push(`${params.pdv} PDV`);
    if (params.sku) parts.push(String(params.sku));
    actionSummary = parts.join(' · ');
  } else if (actionType === 'ampliar_espacio' && params.facings_extra != null) {
    actionSummary = `+${params.facings_extra} cara(s) en ${params.categoria ?? 'la categoría'}`;
  } else if (actionType === 'respuesta_crisis' && params.tema) {
    actionSummary = `tema: ${params.tema}`;
  } else if (actionType === 'amplificar_contenido' && params.post_id) {
    actionSummary = `post ${params.post_id}`;
  }

  async function decide(action: 'APPROVED' | 'REJECTED') {
    setBusy(true);
    try {
      await onDecide(rec.id, action);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className={[
        'relative rounded-2xl border bg-gradient-to-br',
        sev.ring, sev.bg,
        'overflow-hidden shadow-[0_30px_80px_-30px_rgba(0,0,0,0.7)]',
      ].join(' ')}
    >
      {/* Halo glow behind */}
      <div
        className="pointer-events-none absolute -top-24 -right-24 w-[420px] h-[420px] rounded-full blur-3xl opacity-70"
        style={{ background: sev.haloColor }}
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-dn-400/50 to-transparent" />

      {/* Top ribbon */}
      <div className="relative flex items-center justify-between gap-3 px-7 py-3 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className={`w-1.5 h-6 rounded-full ${sev.ribbon}`} />
          <span className="text-[11px] font-bold uppercase tracking-[0.25em] text-grafito">
            Acción destacada
          </span>
          <span className={`text-[10px] uppercase tracking-widest font-bold px-2 py-0.5 rounded inline-flex items-center gap-1 ${sev.text}`}
                style={{ backgroundColor: 'rgba(255,255,255,0.04)', border: `1px solid ${sev.haloColor}` }}
          >
            <AlertTriangle className="w-3 h-3" strokeWidth={2.5} />
            {sev.label}
          </span>
        </div>
        <div className="text-[11px] uppercase tracking-widest text-humo">
          identificado {relTime(rec.created_at)}
        </div>
      </div>

      {/* Body */}
      <div className="relative p-7 grid grid-cols-12 gap-7 items-center">
        {/* Left — agent identity */}
        <div className="col-span-12 lg:col-span-3">
          <div className="flex items-center gap-3">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center"
              style={{
                backgroundColor: `${agent.color}22`,
                border: `1.5px solid ${agent.color}88`,
                boxShadow: `0 0 36px -8px ${agent.color}88`,
                color: agent.color,
              }}
            >
              <agent.Icon className="w-7 h-7" strokeWidth={1.8} />
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-humo">Agente</div>
              <div className="text-base font-bold leading-tight" style={{ color: agent.color }}>
                {agent.name}
              </div>
              <div className="text-[11px] text-humo mt-0.5">{agent.tagline}</div>
            </div>
          </div>
        </div>

        {/* Center — title + analysis */}
        <div className="col-span-12 lg:col-span-6 min-w-0">
          <h1 className="text-[28px] leading-tight font-bold text-tinta tracking-tight mb-2">
            {rec.title}
          </h1>
          <p className="text-[14px] leading-relaxed text-grafito line-clamp-3 max-w-prose">
            {rec.recommendation || rec.analysis}
          </p>
          {actionSummary && (
            <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-nieve border border-marco">
              <span className="text-[10px] uppercase tracking-widest text-humo">{actionLabel}</span>
              <span className="text-tinta">·</span>
              <span className="text-sm font-semibold text-tinta tabular-nums">{actionSummary}</span>
            </div>
          )}
        </div>

        {/* Right — impact + buttons */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-3">
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.06] px-4 py-3">
            <div className="text-[10px] uppercase tracking-widest text-emerald-600/80 mb-0.5">
              {impact.esProtectivo ? 'Deterioro evitado' : 'Impacto estimado'}
            </div>
            <div className={`text-3xl font-bold tabular-nums leading-none ${
              impact.esProtectivo ? 'text-cyan-600' : 'text-emerald-600'
            }`}>
              {impact.esProtectivo ? '~' : '+'}{fmtDecimal(impact.pp)} pp
            </div>
            <div className="text-[11px] text-grafito mt-1">
              {impact.metrica} · en {impact.horizonte}{' '}
              <span className="text-humo">· {impact.pdv} PDV · conf. {impact.confianza}</span>
            </div>
          </div>

          <button
            disabled={busy}
            onClick={() => decide('APPROVED')}
            className={[
              'w-full py-3 rounded-xl text-sm font-bold uppercase tracking-[0.2em] transition-all',
              'bg-emerald-500/15 border border-emerald-400/60 text-emerald-700',
              'hover:bg-emerald-500/25 hover:border-emerald-300 hover:text-white',
              'shadow-[0_0_30px_-8px_rgba(16,185,129,0.6)]',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            ].join(' ')}
          >
            {busy ? 'esperando…' : 'Despachar a campo'}
          </button>

          <div className="grid grid-cols-2 gap-2">
            <button
              disabled={busy}
              onClick={() => decide('REJECTED')}
              className={[
                'py-2 rounded-lg text-[12px] font-medium uppercase tracking-wider transition-all',
                'bg-white border border-marco text-grafito',
                'hover:bg-dn-100 hover:text-tinta',
                'disabled:opacity-50',
              ].join(' ')}
            >
              Descartar
            </button>
            <button
              onClick={() => setOpen((o) => !o)}
              className="py-2 rounded-lg text-[12px] font-medium uppercase tracking-wider bg-white border border-marco text-grafito hover:text-tinta hover:bg-white"
            >
              {open ? '▴ Ocultar' : '▾ Detalles'}
            </button>
          </div>
        </div>
      </div>

      {/* Expandable analytical context */}
      {open && (
        <div className="relative px-7 pb-7 grid lg:grid-cols-2 gap-4">
          <DetailPanel title="Cómo razonó el agente" body={rec.analysis} />
          <DetailPanel title="Datos de soporte" data={rec.supporting_data} />
        </div>
      )}
    </section>
  );
}

function DetailPanel({ title, body, data }: { title: string; body?: string; data?: any }) {
  return (
    <div className="rounded-lg border border-marco bg-nieve p-4">
      <div className="text-[10px] uppercase tracking-widest text-humo mb-2">{title}</div>
      {body && <p className="text-[13px] text-grafito leading-relaxed">{body}</p>}
      {!body && data && (
        <pre className="text-[11px] font-mono text-grafito whitespace-pre-wrap break-words leading-relaxed">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
