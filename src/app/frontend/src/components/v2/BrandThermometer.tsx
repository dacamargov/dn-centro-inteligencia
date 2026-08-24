import { Flame, MessageSquareHeart, ThumbsDown, ThumbsUp } from 'lucide-react';
import { useMemo } from 'react';
import { SocialPost } from '../../lib/api';
import { fmtNumber } from '../../lib/format';

interface Props {
  posts: SocialPost[];
  /** Fabricante cuyo termómetro se muestra; por defecto el cliente del estudio. */
  fabricante?: string;
}

interface Score {
  value: number; // 0–100
  label: string;
  tone: string;
  textCls: string;
  gradient: string;
}

function scoreOf(value: number): Score {
  if (value >= 70) {
    return { value, label: 'saludable', tone: '#10b981', textCls: 'text-emerald-600', gradient: 'from-emerald-500/30 to-emerald-500/5' };
  }
  if (value >= 45) {
    return { value, label: 'en alerta', tone: '#fb923c', textCls: 'text-orange-600', gradient: 'from-orange-400/30 to-orange-400/5' };
  }
  return { value, label: 'crise', tone: '#ef4444', textCls: 'text-red-600', gradient: 'from-red-500/30 to-red-500/5' };
}

export default function BrandThermometer({ posts, fabricante = 'Nestlé' }: Props) {
  const stats = useMemo(() => {
    const delCliente = posts.filter((p) => p.fabricante === fabricante);
    const total = delCliente.length;
    if (total === 0) {
      return { value: 50, pos: 0, neg: 0, neu: 0, viralPos: 0, viralNeg: 0, totalEng: 0 };
    }
    const pos = delCliente.filter((p) => p.sentiment === 'positivo').length;
    const neg = delCliente.filter((p) => p.sentiment === 'negativo').length;
    const neu = delCliente.filter((p) => p.sentiment === 'neutral').length;
    const viralPos = delCliente.filter((p) => p.is_viral && p.sentiment === 'positivo').length;
    const viralNeg = delCliente.filter((p) => p.is_viral && p.sentiment === 'negativo').length;
    const totalEng = delCliente.reduce((a, p) => a + p.engagement, 0);

    // Base: proporción de positivos contra negativos, mapeada a 0-100
    //   todo positivo (sin negativos) → 100   (diffRatio = 1)
    //   50/50 mix              → 50
    //   all negative           → 0
    const diffRatio = (pos - neg) / total; // range -1..+1
    const base = 50 + diffRatio * 50;

    // Viral skew: bounded so 10 viral positives can't push to 100 by themselves
    const viralSkew = viralPos - viralNeg;
    const viralBonus = Math.max(-15, Math.min(12, viralSkew * 1.8));

    const value = Math.max(0, Math.min(100, base + viralBonus));
    return { value: Math.round(value), pos, neg, neu, viralPos, viralNeg, totalEng };
  }, [posts, fabricante]);

  const score = scoreOf(stats.value);
  // Semicircle math — angle from -90° (left) to +90° (right)
  const angle = (stats.value / 100) * 180 - 90;
  const rad = (angle * Math.PI) / 180;
  const needleX = Math.sin(rad);
  const needleY = -Math.cos(rad);

  return (
    <section
      className={[
        'relative rounded-2xl border border-marco overflow-hidden',
        'bg-gradient-to-br', score.gradient, 'from-white via-white to-nieve',
      ].join(' ')}
    >
      <div
        className="absolute -top-32 -right-32 w-[400px] h-[400px] rounded-full blur-3xl opacity-30 pointer-events-none"
        style={{ background: score.tone }}
      />

      <div className="relative grid grid-cols-12 gap-6 p-7 items-center">
        {/* Gauge */}
        <div className="col-span-12 lg:col-span-5 flex flex-col items-center">
          <div className="text-[10px] uppercase tracking-[0.25em] text-humo font-bold mb-2">
            Salud de marca · {fabricante}
          </div>
          <svg viewBox="-1.2 -1.2 2.4 1.4" className="w-full max-w-[360px]" style={{ overflow: 'visible' }}>
            <defs>
              <linearGradient id="gauge-bg" x1="-1" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#ef4444" />
                <stop offset="45%" stopColor="#fbbf24" />
                <stop offset="70%" stopColor="#10b981" />
                <stop offset="100%" stopColor="#10b981" />
              </linearGradient>
            </defs>
            {/* outer track */}
            <path
              d="M -1 0 A 1 1 0 0 1 1 0"
              fill="none"
              stroke="#D8E3EE"
              strokeWidth="0.22"
              strokeLinecap="round"
            />
            {/* colored gradient track */}
            <path
              d="M -1 0 A 1 1 0 0 1 1 0"
              fill="none"
              stroke="url(#gauge-bg)"
              strokeWidth="0.18"
              strokeLinecap="round"
              opacity="0.6"
            />
            {/* needle */}
            <line
              x1="0" y1="0"
              x2={needleX * 0.9}
              y2={needleY * 0.9}
              stroke={score.tone}
              strokeWidth="0.04"
              strokeLinecap="round"
              style={{ filter: `drop-shadow(0 0 8px ${score.tone})`, transition: 'all 700ms cubic-bezier(0.4, 0, 0.2, 1)' }}
            />
            <circle cx="0" cy="0" r="0.08" fill={score.tone} style={{ filter: `drop-shadow(0 0 6px ${score.tone})` }} />
            {/* tick labels */}
            <text x="-1" y="0.32" textAnchor="middle" fill="#7b8fa8" fontSize="0.12" fontFamily="Inter, system-ui">0</text>
            <text x="0" y="-0.95" textAnchor="middle" fill="#7b8fa8" fontSize="0.12" fontFamily="Inter, system-ui">50</text>
            <text x="1" y="0.32" textAnchor="middle" fill="#7b8fa8" fontSize="0.12" fontFamily="Inter, system-ui">100</text>
          </svg>
          <div className="text-center mt-1">
            <div className={`text-5xl font-bold tabular-nums leading-none ${score.textCls}`}>
              {stats.value}
            </div>
            <div className={`text-[11px] uppercase tracking-[0.22em] font-bold mt-1 ${score.textCls}`}>
              {score.label}
            </div>
          </div>
        </div>

        {/* Side stats */}
        <div className="col-span-12 lg:col-span-7 grid grid-cols-2 gap-3">
          <Tile
            icon={<ThumbsUp className="w-4 h-4" strokeWidth={2} />}
            label="Posts positivos"
            value={String(stats.pos)}
            tone="good"
          />
          <Tile
            icon={<ThumbsDown className="w-4 h-4" strokeWidth={2} />}
            label="Posts negativos"
            value={String(stats.neg)}
            tone="bad"
          />
          <Tile
            icon={<Flame className="w-4 h-4" strokeWidth={2} />}
            label="Virales positivos"
            value={String(stats.viralPos)}
            tone="good"
          />
          <Tile
            icon={<Flame className="w-4 h-4" strokeWidth={2} />}
            label="Virales negativos"
            value={String(stats.viralNeg)}
            tone="bad"
          />
          <Tile
            icon={<MessageSquareHeart className="w-4 h-4" strokeWidth={2} />}
            label="Engagement total"
            value={fmtNumber(stats.totalEng)}
            tone="neutral"
            wide
          />
        </div>
      </div>
    </section>
  );
}

function Tile({
  icon, label, value, tone, wide,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: 'good' | 'bad' | 'warn' | 'neutral';
  wide?: boolean;
}) {
  const cls = tone === 'good' ? 'text-emerald-600 border-emerald-500/30 bg-emerald-500/[0.06]'
    : tone === 'bad' ? 'text-red-600 border-red-500/30 bg-red-500/[0.06]'
    : tone === 'warn' ? 'text-dn-600 border-dn-600/30 bg-dn-600/[0.06]'
    : 'text-tinta border-marco bg-nieve';
  return (
    <div className={`rounded-xl border ${cls} px-3.5 py-2.5 ${wide ? 'col-span-2' : ''}`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest opacity-80 mb-1">
        {icon}
        {label}
      </div>
      <div className="text-2xl font-bold tabular-nums leading-none">{value}</div>
    </div>
  );
}
