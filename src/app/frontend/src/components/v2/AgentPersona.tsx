import { LucideIcon } from 'lucide-react';
import { Recomendacion } from '../../lib/api';

interface Props {
  name: string;
  Icon: LucideIcon;
  color: string;
  tagline: string;
  recs: Recomendacion[];
  active: boolean;
  onClick: () => void;
}

// "Mood" derived from recent activity & severity
function moodOf(recs: Recomendacion[]): { label: string; tone: string; pulse: boolean } {
  const now = Date.now();
  const last10 = recs.filter((r) => now - new Date(r.created_at).getTime() < 10 * 60_000);
  const critical = last10.filter((r) => r.severity === 'critical' || r.severity === 'high').length;
  const total = last10.length;
  if (critical >= 2) return { label: 'crítico', tone: 'text-red-600', pulse: true };
  if (critical === 1) return { label: 'activo', tone: 'text-orange-600', pulse: true };
  if (total >= 1) return { label: 'monitoreando', tone: 'text-dn-600', pulse: false };
  return { label: 'en calma', tone: 'text-emerald-600', pulse: false };
}

// Tiny sparkline: count of recs in each of the last 12 5-min buckets
function ActivitySparkline({ recs, color }: { recs: Recomendacion[]; color: string }) {
  const now = Date.now();
  const bucketMs = 5 * 60_000;
  const buckets = Array.from({ length: 12 }, (_, i) => {
    const start = now - (12 - i) * bucketMs;
    const end = start + bucketMs;
    return recs.filter((r) => {
      const t = new Date(r.created_at).getTime();
      return t >= start && t < end;
    }).length;
  });
  const max = Math.max(1, ...buckets);
  const w = 100, h = 26;
  const bar = w / buckets.length;
  return (
    <svg width={w} height={h} className="opacity-80">
      {buckets.map((v, i) => {
        const bh = (v / max) * (h - 2);
        return (
          <rect
            key={i}
            x={i * bar + 1}
            y={h - bh}
            width={bar - 2}
            height={bh}
            fill={color}
            rx={1}
            opacity={i === buckets.length - 1 ? 1 : 0.55}
          />
        );
      })}
    </svg>
  );
}

export default function AgentPersona({ name, Icon, color, tagline, recs, active, onClick }: Props) {
  const pending = recs.filter((r) => r.status === 'pending').length;
  const mood = moodOf(recs);

  return (
    <button
      onClick={onClick}
      className={[
        'group relative w-full text-left rounded-2xl border bg-white px-5 py-4 transition-all',
        'overflow-hidden',
        active
          ? 'border-marco shadow-[0_0_42px_-14px_var(--ring-color)]'
          : 'border-marco hover:border-marco',
      ].join(' ')}
      style={{ ['--ring-color' as any]: `${color}aa` }}
    >
      {/* Top accent */}
      <div className="absolute inset-x-0 top-0 h-0.5" style={{ background: color }} />

      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className="relative">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{
              backgroundColor: `${color}22`,
              border: `1.5px solid ${color}88`,
              boxShadow: `0 0 28px -8px ${color}66`,
              color,
            }}
          >
            <Icon className="w-7 h-7" strokeWidth={1.8} />
          </div>
          {mood.pulse && (
            <span
              className="absolute -top-1 -right-1 w-3 h-3 rounded-full"
              style={{ background: color, boxShadow: `0 0 10px ${color}` }}
            >
              <span
                className="absolute inset-0 rounded-full animate-ping"
                style={{ background: color, opacity: 0.55 }}
              />
            </span>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <div className="text-base font-bold leading-tight" style={{ color }}>
              {name}
            </div>
            <span className={`text-[10px] uppercase tracking-widest font-bold ${mood.tone}`}>
              · {mood.label}
            </span>
          </div>
          <div className="text-[11px] text-humo mt-0.5">{tagline}</div>

          <div className="flex items-center gap-4 mt-2.5">
            <ActivitySparkline recs={recs} color={color} />
            <div className="leading-none">
              <div className="text-2xl font-bold text-tinta tabular-nums">{pending}</div>
              <div className="text-[9px] uppercase tracking-widest text-humo">pendientes</div>
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}
