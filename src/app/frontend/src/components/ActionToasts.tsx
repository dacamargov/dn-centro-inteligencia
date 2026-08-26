import { Check, Megaphone, Tag, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  ActionToastItem,
  ActionToastKind,
  subscribeActionToast,
} from '../lib/actionToast';

const HOLD_MS = 12_000;
const MAX_VISIBLE = 4;

const STYLE: Record<
  ActionToastKind,
  { border: string; glow: string; text: string; bg: string; Icon: typeof Megaphone }
> = {
  promo: {
    border: 'border-dn-600/50',
    glow: 'shadow-[0_0_24px_-6px_rgba(13,92,171,0.45)]',
    text: 'text-dn-600',
    bg: 'bg-dn-50',
    Icon: Megaphone,
  },
  precio: {
    border: 'border-emerald-500/50',
    glow: 'shadow-[0_0_20px_-6px_rgba(16,185,129,0.4)]',
    text: 'text-emerald-700',
    bg: 'bg-emerald-50',
    Icon: Tag,
  },
  ok: {
    border: 'border-emerald-500/40',
    glow: '',
    text: 'text-emerald-700',
    bg: 'bg-emerald-50',
    Icon: Check,
  },
  error: {
    border: 'border-red-500/50',
    glow: '',
    text: 'text-red-600',
    bg: 'bg-red-50',
    Icon: X,
  },
};

export default function ActionToasts() {
  const [toasts, setToasts] = useState<ActionToastItem[]>([]);

  useEffect(() => {
    return subscribeActionToast((item) => {
      setToasts((cur) => [item, ...cur].slice(0, MAX_VISIBLE));
    });
  }, []);

  useEffect(() => {
    if (toasts.length === 0) return;
    const id = setInterval(() => {
      setToasts((cur) => cur.filter((t) => Date.now() - t.arrivedAt < HOLD_MS));
    }, 1000);
    return () => clearInterval(id);
  }, [toasts.length]);

  const dismiss = (id: string) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-6 right-4 z-50 flex flex-col gap-2 pointer-events-none"
      style={{ width: 'min(92vw, 360px)' }}
      aria-live="polite"
    >
      {toasts.map((t) => {
        const sev = STYLE[t.kind];
        const ageSec = Math.floor((Date.now() - t.arrivedAt) / 1000);
        return (
          <div
            key={t.id}
            className={[
              'relative pointer-events-auto rounded-lg border backdrop-blur-md bg-white',
              'p-3 pr-8 animate-slide-in-right',
              sev.border,
              sev.glow,
            ].join(' ')}
          >
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="absolute top-2 right-2 text-humo hover:text-grafito text-lg leading-none w-5 h-5 flex items-center justify-center"
              aria-label="descartar"
            >
              ×
            </button>
            <div className="flex items-start gap-2.5">
              <div
                className={[
                  'flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center',
                  sev.bg,
                  sev.text,
                ].join(' ')}
              >
                <sev.Icon className="w-4 h-4" strokeWidth={2.25} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span
                    className={[
                      'text-[9px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded',
                      sev.bg,
                      sev.text,
                    ].join(' ')}
                  >
                    acción registrada
                  </span>
                  <span className="text-[10px] text-humo ml-auto">hace {ageSec}s</span>
                </div>
                <div className={`text-sm font-semibold leading-snug ${sev.text}`}>{t.title}</div>
                {t.summary && (
                  <div className="text-[11px] text-grafito leading-snug mt-0.5">{t.summary}</div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
