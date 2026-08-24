import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, Recomendacion, Severity } from '../lib/api';

import { Bot } from 'lucide-react';
import { AGENT_META } from '../lib/icons';

const SEVERITY_STYLE: Record<Severity, { bg: string; border: string; text: string; glow: string; label: string }> = {
  critical: { bg: 'bg-red-500/15',   border: 'border-red-500/60',   text: 'text-red-600',   glow: 'shadow-[0_0_30px_-6px_rgba(239,68,68,0.5)]',  label: 'CRÍTICO' },
  high:     { bg: 'bg-orange-500/12',border: 'border-orange-500/50',text: 'text-orange-600',glow: 'shadow-[0_0_24px_-6px_rgba(249,115,22,0.45)]',label: 'ALTO' },
  medium:   { bg: 'bg-dn-400/10', border: 'border-dn-400/40', text: 'text-dn-600', glow: 'shadow-[0_0_18px_-6px_rgba(51,189,238,0.4)]', label: 'MEDIO' },
  low:      { bg: 'bg-dn-100/30',  border: 'border-marco',     text: 'text-grafito',  glow: '',                                              label: 'BAJO' },
};

const ACTION_TYPE_PT: Record<string, string> = {
  campaign_boost:   'Impulso de campaña',
  price_change:     'Ajuste de precio',
  crisis_response:  'Respuesta de crisis',
  content_amplify:  'Amplificar contenido',
  stock_alert:      'Alerta de inventario',
  other:            'Acción',
};

function formatActionSummary(rec: Recomendacion): string {
  const sa = rec.suggested_action;
  if (!sa || typeof sa !== 'object') return '';
  const type = sa.type ?? 'other';
  const params = sa.params ?? {};
  const label = ACTION_TYPE_PT[type] ?? type;

  if (type === 'price_change' && params.sku) {
    const cur = params.current_price;
    const sug = params.suggested_price;
    if (cur != null && sug != null) {
      return `${label} · ${params.sku} · $ ${cur.toLocaleString('es-CO')} → $ ${sug.toLocaleString('es-CO')}`;
    }
    return `${label} · ${params.sku}`;
  }
  if (type === 'campaign_boost') {
    const parts = [
      params.category,
      params.channel,
      params.increment_pct != null ? `+${params.increment_pct}%` : null,
    ].filter(Boolean);
    return `${label} · ${parts.join(' · ')}`;
  }
  if (type === 'crisis_response' && params.theme) {
    return `${label} · ${params.theme}`;
  }
  if (type === 'content_amplify' && params.post_id) {
    return `${label} · ${params.post_id}`;
  }
  return label;
}

interface ToastEntry {
  rec: Recomendacion;
  arrivedAt: number;
}

const HOLD_MS = 45_000; // each toast stays for 45s
const MAX_VISIBLE = 3;

export default function AgentAlertToasts() {
  const navigate = useNavigate();
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const seenIds = useRef<Set<string>>(new Set());
  const initialized = useRef(false);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const recs = await api.recomendaciones(undefined, 30);
        if (!active) return;

        // First load: mark everything as seen so we don't dump 30 toasts on screen
        if (!initialized.current) {
          recs.forEach((r) => seenIds.current.add(r.id));
          initialized.current = true;
          return;
        }

        // Find NEW recs we haven't shown yet, with high or critical severity, still pending
        const newOnes = recs
          .filter((r) => !seenIds.current.has(r.id))
          .filter((r) => r.severity === 'high' || r.severity === 'critical')
          .filter((r) => r.status === 'pending')
          .reverse(); // oldest first → newest goes on top

        if (newOnes.length > 0) {
          newOnes.forEach((r) => seenIds.current.add(r.id));
          const now = Date.now();
          setToasts((cur) => {
            const updated = [
              ...newOnes.map((r) => ({ rec: r, arrivedAt: now })),
              ...cur,
            ];
            return updated.slice(0, MAX_VISIBLE);
          });
        }
      } catch {
        // ignore poll errors
      }
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  // Auto-fade old toasts
  useEffect(() => {
    if (toasts.length === 0) return;
    const id = setInterval(() => {
      setToasts((cur) => cur.filter((t) => Date.now() - t.arrivedAt < HOLD_MS));
    }, 1500);
    return () => clearInterval(id);
  }, [toasts.length]);

  const dismiss = (recId: string) => {
    setToasts((cur) => cur.filter((t) => t.rec.id !== recId));
  };

  const goToAgent = (recId: string) => {
    navigate(`/agents?focus=${recId}`);
  };

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-20 right-4 z-50 flex flex-col gap-3 pointer-events-none"
      style={{ width: 'min(92vw, 380px)' }}
      aria-live="polite"
    >
      {toasts.map((t) => {
        const rec = t.rec;
        const sev = SEVERITY_STYLE[rec.severity];
        const agent = AGENT_META[rec.agent_name] ?? {
          Icon: Bot,
          color: '#6C7F93',
          name: rec.agent_name,
          tagline: '',
        };
        const summary = formatActionSummary(rec);
        const ageSec = Math.floor((Date.now() - t.arrivedAt) / 1000);

        return (
          <div
            key={rec.id}
            onClick={() => goToAgent(rec.id)}
            className={[
              'relative pointer-events-auto cursor-pointer',
              'rounded-lg border backdrop-blur-md bg-white',
              'p-3 pr-8 transition-all duration-300 animate-slide-in-right',
              sev.border,
              sev.glow,
            ].join(' ')}
          >
            {/* dismiss */}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); dismiss(rec.id); }}
              className="absolute top-2 right-2 text-humo hover:text-grafito text-lg leading-none w-5 h-5 flex items-center justify-center"
              aria-label="descartar"
            >
              ×
            </button>

            <div className="flex items-start gap-2.5">
              <div
                className="flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center"
                style={{ backgroundColor: `${agent.color}22`, border: `1px solid ${agent.color}55`, color: agent.color }}
              >
                <agent.Icon className="w-4 h-4" strokeWidth={2} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span
                    className={`text-[9px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded ${sev.bg} ${sev.text}`}
                  >
                    {sev.label}
                  </span>
                  <span className="text-[10px] uppercase tracking-wider text-humo">
                    {agent.name}
                  </span>
                  <span className="text-[10px] text-humo ml-auto">hace {ageSec}s</span>
                </div>
                <div className={`text-sm font-semibold leading-snug ${sev.text} mb-1`}>
                  {rec.title}
                </div>
                {summary && (
                  <div className="text-[11px] text-grafito leading-snug truncate">
                    {summary}
                  </div>
                )}
                <div className="text-[10px] text-humo mt-1.5">
                  Clic para ver detalles →
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
