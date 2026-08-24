import AnimatedNumber from './AnimatedNumber';

interface Props {
  label: string;
  /** Numeric value used for animated transition. */
  value: number | null | undefined;
  format: (n: number) => string;
  sublabel?: string;
  /** Highlight color (true = amber accent). */
  accent?: boolean;
  /** Optional severity flavor: "good" emerald, "warn" amber, "bad" red — overrides accent. */
  flavor?: 'good' | 'warn' | 'bad';
  /** Tiny sparkline values (last N data points). */
  sparkline?: number[];
}

const FLAVOR_TEXT: Record<NonNullable<Props['flavor']>, string> = {
  good: 'text-emerald-600',
  warn: 'text-dn-600',
  bad: 'text-red-600',
};

const FLAVOR_GLOW: Record<NonNullable<Props['flavor']>, string> = {
  good: 'from-emerald-400/0 via-emerald-400 to-emerald-400/0',
  warn: 'from-amber-400/0 via-amber-400 to-amber-400/0',
  bad: 'from-red-400/0 via-red-400 to-red-400/0',
};

function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (!values || values.length < 2) return null;
  const w = 80;
  const h = 24;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);
  const points = values
    .map((v, i) => `${i * step},${h - ((v - min) / range) * h}`)
    .join(' ');
  return (
    <svg width={w} height={h} className="opacity-80">
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

export default function KpiCard({
  label,
  value,
  format,
  sublabel,
  accent,
  flavor,
  sparkline,
}: Props) {
  const numberClass = flavor
    ? FLAVOR_TEXT[flavor]
    : accent
      ? 'text-dn-600'
      : 'text-tinta';
  const glow = flavor
    ? FLAVOR_GLOW[flavor]
    : accent
      ? 'from-amber-400/0 via-amber-400 to-amber-400/0'
      : '';

  const hasNumber = typeof value === 'number' && !Number.isNaN(value);
  const sparkColor =
    flavor === 'good' ? '#34d399'
      : flavor === 'bad' ? '#f87171'
      : flavor === 'warn' || accent ? '#fbbf24'
      : '#6C7F93';

  return (
    <div
      className={[
        'group relative bg-white border border-marco rounded-lg p-5',
        'flex flex-col gap-1 overflow-hidden transition-all',
        accent || flavor ? 'shadow-[0_0_24px_-12px_rgba(51,189,238,0.45)]' : '',
        'hover:border-marco',
      ].join(' ')}
    >
      {/* top accent line */}
      {(accent || flavor) && (
        <div
          className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${glow}`}
        />
      )}

      <div className="flex items-start justify-between">
        <div className="text-[10.5px] uppercase tracking-[0.18em] text-humo font-medium">
          {label}
        </div>
        {sparkline && sparkline.length > 1 && (
          <Sparkline values={sparkline} color={sparkColor} />
        )}
      </div>

      <div
        className={`text-[2.7rem] leading-tight font-bold tabular-nums tracking-tight ${numberClass}`}
      >
        {hasNumber ? <AnimatedNumber value={value as number} format={format} /> : '—'}
      </div>

      {sublabel && (
        <div className="text-xs text-humo mt-0.5">{sublabel}</div>
      )}
    </div>
  );
}
