import { Severity } from '../lib/api';

const STYLES: Record<Severity, { bg: string; text: string; border: string; label: string; emoji: string }> = {
  critical: { bg: 'bg-red-500/15',    text: 'text-red-600',    border: 'border-red-500/40',    label: 'CRÍTICO', emoji: '🚨' },
  high:     { bg: 'bg-orange-500/15', text: 'text-orange-600', border: 'border-orange-500/40', label: 'ALTO',    emoji: '🔥' },
  medium:   { bg: 'bg-dn-400/15',  text: 'text-dn-600',  border: 'border-dn-400/40',  label: 'MEDIO',   emoji: '⚠️' },
  low:      { bg: 'bg-dn-100/40',   text: 'text-grafito',   border: 'border-marco',      label: 'BAJO',    emoji: '➖' },
};

interface Props {
  severity: Severity;
  size?: 'sm' | 'md';
}

export default function SeverityPill({ severity, size = 'sm' }: Props) {
  const sev = (severity ?? 'low') as Severity;
  const s = STYLES[sev] ?? STYLES.low;
  const sizing = size === 'md' ? 'text-[11px] px-2 py-0.5' : 'text-[10px] px-1.5 py-0.5';
  return (
    <span
      className={[
        'inline-flex items-center gap-1 font-bold tracking-widest border rounded',
        s.bg, s.text, s.border, sizing,
      ].join(' ')}
    >
      <span className="text-[11px] leading-none">{s.emoji}</span>
      {s.label}
    </span>
  );
}
