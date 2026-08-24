import { AlertTriangle, Bot, Check, Shield, X, Zap } from 'lucide-react';
import { useState } from 'react';
import { api, Kpis, Recomendacion } from '../lib/api';
import { fmtDecimal } from '../lib/format';
import { estimarImpacto } from '../lib/impact';
import { AGENT_META } from '../lib/icons';

export const ACTION_TYPE_LABEL: Record<string, string> = {
  visita_prioritaria:    'Visita prioritaria',
  corregir_planograma:   'Corregir planograma',
  ajustar_precio:        'Ajustar precio',
  activar_promo:         'Activar promoción',
  ampliar_espacio:       'Ampliar espacio',
  respuesta_crisis:      'Respuesta de crisis',
  amplificar_contenido:  'Amplificar contenido',
  other:                 'Acción',
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: 'border-red-500/60 shadow-[0_0_50px_-10px_rgba(239,68,68,0.55)]',
  high:     'border-orange-500/55 shadow-[0_0_40px_-10px_rgba(249,115,22,0.5)]',
  medium:   'border-dn-400/50 shadow-[0_0_30px_-10px_rgba(51,189,238,0.4)]',
  low:      'border-marco',
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: 'CRÍTICO', high: 'ALTO', medium: 'MEDIO', low: 'BAJO',
};

const SEVERITY_TEXT: Record<string, string> = {
  critical: 'text-red-600',
  high:     'text-orange-600',
  medium:   'text-dn-600',
  low:      'text-grafito',
};

interface Props {
  rec: Recomendacion | null;
  kpis: Kpis | null;
  onDecidida: (rec: Recomendacion, action: 'APPROVED' | 'REJECTED') => void;
}

type FxState =
  | { kind: 'idle' }
  | { kind: 'submitting' }
  | { kind: 'success'; action: 'APPROVED' | 'REJECTED' }
  | { kind: 'error'; msg: string };

export default function TopActionBanner({ rec, kpis, onDecidida }: Props) {
  const [fx, setFx] = useState<FxState>({ kind: 'idle' });

  if (!rec) {
    return (
      <section className="rounded-lg border border-marco bg-gradient-to-r from-white via-white to-nieve p-4">
        <div className="flex items-center gap-3 text-humo text-sm">
          <span className="w-2 h-2 rounded-full bg-dn-100" />
          <span className="uppercase tracking-widest text-[11px]">
            Esperando la próxima lectura de los agentes
          </span>
          <span className="text-humo text-xs ml-auto">
            corren cada 2 min · la próxima recomendación aparece aquí
          </span>
        </div>
      </section>
    );
  }

  const agent = AGENT_META[rec.agent_name] ?? {
    Icon: Bot, color: '#7b8fa8', name: rec.agent_name, tagline: '',
  };
  const sa = (rec.suggested_action as any) ?? {};
  const actionType = sa.type ?? 'other';
  const actionLabel = ACTION_TYPE_LABEL[actionType] ?? actionType;
  const impacto = estimarImpacto(rec, kpis);
  const sevBorder = SEVERITY_BORDER[rec.severity] ?? '';
  const sevText = SEVERITY_TEXT[rec.severity] ?? 'text-tinta';
  const sevLabel = SEVERITY_LABEL[rec.severity] ?? rec.severity.toUpperCase();
  const edadSeg = Math.max(0, Math.floor((Date.now() - new Date(rec.created_at).getTime()) / 1000));

  async function decidir(action: 'APPROVED' | 'REJECTED') {
    if (!rec || fx.kind !== 'idle') return;
    setFx({ kind: 'submitting' });
    try {
      await api.decidir(
        rec.id,
        action,
        action === 'APPROVED' ? 'despachada por el equipo de cuenta' : null,
      );
      setFx({ kind: 'success', action });
      onDecidida(rec, action);
      setTimeout(() => setFx({ kind: 'idle' }), 2200);
    } catch (e: any) {
      setFx({ kind: 'error', msg: e?.message ?? 'falló el registro' });
    }
  }

  if (fx.kind === 'success' && fx.action === 'APPROVED') {
    return (
      <section className="rounded-lg border border-emerald-500/60 bg-emerald-500/10 p-5 shadow-[0_0_50px_-10px_rgba(16,185,129,0.55)] animate-pulse-slow">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-emerald-500/20 border border-emerald-500/60 flex items-center justify-center text-emerald-600">
            <Check className="w-5 h-5" strokeWidth={3} />
          </div>
          <div className="flex-1">
            <div className="text-emerald-600 font-bold text-lg">
              Acción despachada a campo · midiendo impacto
            </div>
            <div className="text-sm text-emerald-700/80 inline-flex items-center gap-1.5">
              <agent.Icon className="w-3.5 h-3.5" strokeWidth={2} />
              {agent.name} · {actionLabel} ·{' '}
              {impacto.esProtectivo ? 'protege' : 'recupera'} ~{fmtDecimal(impacto.pp)} pp de{' '}
              {impacto.metrica} en {impacto.horizonte}
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (fx.kind === 'success' && fx.action === 'REJECTED') {
    return (
      <section className="rounded-lg border border-marco bg-white p-5">
        <div className="flex items-center gap-3 text-grafito">
          <X className="w-5 h-5 text-grafito" strokeWidth={2.5} />
          <div className="text-sm">Acción descartada · la siguiente recomendación viene en camino</div>
        </div>
      </section>
    );
  }

  const submitting = fx.kind === 'submitting';

  return (
    <section
      className={['relative rounded-lg border bg-white overflow-hidden transition-all duration-300', sevBorder].join(' ')}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-dn-400/60 to-transparent" />

      <div className="grid grid-cols-12 gap-4 p-5 items-center">
        <div className="col-span-12 md:col-span-2 flex items-center gap-3">
          <div
            className="w-12 h-12 rounded-lg flex items-center justify-center"
            style={{
              backgroundColor: `${agent.color}1f`,
              border: `1px solid ${agent.color}66`,
              color: agent.color,
            }}
          >
            <agent.Icon className="w-6 h-6" strokeWidth={1.8} />
          </div>
          <div className="leading-tight">
            <div className="text-[10px] uppercase tracking-widest text-humo">{agent.name}</div>
            <div className="text-[10px] text-humo">hace {edadSeg}s</div>
          </div>
        </div>

        <div className="col-span-12 md:col-span-6 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={[
                'text-[10px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded',
                rec.severity === 'critical' ? 'bg-red-500/20 text-red-600' :
                rec.severity === 'high'     ? 'bg-orange-500/20 text-orange-600' :
                rec.severity === 'medium'   ? 'bg-dn-400/20 text-dn-600' :
                                              'bg-dn-100/30 text-grafito',
              ].join(' ')}
            >
              <AlertTriangle className="w-3 h-3 inline mr-1" strokeWidth={2.5} />
              {sevLabel}
            </span>
            <span className="text-[10px] uppercase tracking-widest text-humo">
              acción recomendada
            </span>
          </div>
          <div className={`text-lg font-semibold leading-snug truncate ${sevText}`}>{rec.title}</div>
          <div className="text-xs text-grafito leading-snug mt-0.5 line-clamp-2">
            {rec.recommendation || rec.analysis}
          </div>
          <div className="inline-flex items-center gap-1.5 mt-2 text-[11px] text-humo border border-marco rounded-full px-2 py-0.5">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: agent.color }} />
            {actionLabel}
          </div>
        </div>

        <div className="col-span-7 md:col-span-2 border-l border-marco md:pl-4">
          <div className="text-[10px] uppercase tracking-widest text-humo mb-0.5">
            {impacto.esProtectivo ? 'Deterioro evitado' : 'Impacto estimado'}
          </div>
          <div
            className={`text-2xl font-bold tabular-nums inline-flex items-center gap-1.5 ${
              impacto.esProtectivo ? 'text-cyan-600' : 'text-emerald-600'
            }`}
          >
            {impacto.esProtectivo
              ? <Shield className="w-4 h-4" strokeWidth={2} />
              : <Zap className="w-4 h-4" strokeWidth={2} fill="currentColor" />}
            {impacto.esProtectivo ? '~' : '+'}{fmtDecimal(impacto.pp)} pp
          </div>
          <div className="text-[11px] text-humo">
            {impacto.metrica} · {impacto.horizonte}
          </div>
          <div className="text-[10px] text-humo mt-0.5">
            {impacto.pdv} PDV · conf: {impacto.confianza}
          </div>
        </div>

        <div className="col-span-5 md:col-span-2 flex flex-col gap-2 items-stretch">
          <button
            disabled={submitting}
            onClick={() => decidir('APPROVED')}
            className={[
              'rounded-md px-4 py-2 text-sm font-semibold transition-all',
              'bg-emerald-500/15 border border-emerald-500/60 text-emerald-600',
              'hover:bg-emerald-500/25 hover:border-emerald-400 hover:text-emerald-700',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'shadow-[0_0_18px_-6px_rgba(16,185,129,0.5)]',
            ].join(' ')}
          >
            <span className="inline-flex items-center gap-2 justify-center w-full">
              <Check className="w-4 h-4" strokeWidth={3} />
              {submitting ? '…' : 'Despachar'}
            </span>
          </button>
          <button
            disabled={submitting}
            onClick={() => decidir('REJECTED')}
            className={[
              'rounded-md px-4 py-2 text-xs font-medium transition-all',
              'bg-white border border-marco text-grafito',
              'hover:bg-dn-100 hover:text-tinta',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            ].join(' ')}
          >
            <span className="inline-flex items-center gap-1.5 justify-center w-full">
              <X className="w-3.5 h-3.5" strokeWidth={2.5} />
              Descartar
            </span>
          </button>
        </div>
      </div>

      {fx.kind === 'error' && (
        <div className="px-5 py-2 bg-red-500/10 border-t border-red-500/30 text-red-600 text-xs">
          Error: {fx.msg}
        </div>
      )}
    </section>
  );
}
