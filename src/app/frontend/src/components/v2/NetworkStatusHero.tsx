import { AlertTriangle, LayoutGrid, MapPin, PackageCheck, Sparkles, TrendingUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Pdv } from '../../lib/api';
import { fmtDecimal, fmtNumber } from '../../lib/format';

interface Props {
  pdv: Pdv[];
  categoria?: string;
}

interface Narrative {
  headline: string;
  body: string;
  tone: 'good' | 'warn' | 'bad';
  toneColor: string;
}

function narrative(pdv: Pdv[]): Narrative {
  const medidos = pdv.filter((p) => p.observaciones > 0);
  const criticos = pdv.filter((p) => p.estado === 'critico');
  const riesgo = pdv.filter((p) => p.estado === 'riesgo');
  const quiebres = pdv.reduce((a, p) => a + p.quiebres, 0);
  const peor = [...medidos].sort(
    (a, b) => (a.ejecucion_pct ?? 100) - (b.ejecucion_pct ?? 100),
  )[0];

  if (criticos.length > 0) {
    return {
      headline: 'Ejecución comprometida · despachar campo',
      body: `${criticos.length} PDV en rojo y ${quiebres} quiebres activos${
        peor ? ` · el peor es ${peor.nombre} con ${fmtDecimal(peor.ejecucion_pct ?? 0)}% de ejecución` : ''
      }. Cada hora sin reposición es venta que se va al competidor del anaquel de al lado.`,
      tone: 'bad',
      toneColor: '#ef4444',
    };
  }
  if (riesgo.length >= 3) {
    return {
      headline: 'Red bajo presión · ajustes recomendados',
      body: `${riesgo.length} PDV en riesgo de caer bajo meta${
        peor ? ` · ${peor.cadena} en ${peor.ciudad} es el más expuesto` : ''
      }. Reordenar la ruta de mercadeo hoy evita que se conviertan en quiebres mañana.`,
      tone: 'warn',
      toneColor: '#fb923c',
    };
  }
  return {
    headline: 'Red ejecutando en meta',
    body: `${medidos.length} PDV medidos sin alertas críticas. La ejecución se sostiene pareja entre canal moderno y tradicional.`,
    tone: 'good',
    toneColor: '#10b981',
  };
}

const TONE_RANK: Record<Narrative['tone'], number> = { bad: 2, warn: 1, good: 0 };

export default function NetworkStatusHero({ pdv, categoria }: Props) {
  const medidos = pdv.filter((p) => p.observaciones > 0);
  const lecturas = pdv.reduce((a, p) => a + p.observaciones, 0);
  const quiebres = pdv.reduce((a, p) => a + p.quiebres, 0);
  const enAlerta = pdv.filter((p) => p.estado === 'critico' || p.estado === 'riesgo').length;
  // Promedios ponderados por lecturas: un PDV con 3 observaciones no puede
  // mover el indicador de la red igual que uno con 300.
  const pond = (sel: (p: Pdv) => number | null) => {
    const base = medidos.filter((p) => sel(p) != null);
    const tot = base.reduce((a, p) => a + p.observaciones, 0);
    if (!tot) return 0;
    return base.reduce((a, p) => a + (sel(p) as number) * p.observaciones, 0) / tot;
  };
  const dispRed = pond((p) => p.disponibilidad_pct);
  const ejecRed = pond((p) => p.ejecucion_pct);

  const n = narrative(pdv);

  // Detect when tone IMPROVES (e.g. bad→warn or warn→good) and trigger sweep effect.
  const prevTone = useRef<Narrative['tone'] | null>(null);
  const [improving, setImproving] = useState(false);
  // Force-remount the sweep div on each improvement so the CSS animation replays.
  const [sweepKey, setSweepKey] = useState(0);

  useEffect(() => {
    if (prevTone.current === null) {
      prevTone.current = n.tone;
      return;
    }
    if (TONE_RANK[n.tone] < TONE_RANK[prevTone.current]) {
      setImproving(true);
      setSweepKey((k) => k + 1);
      const t = setTimeout(() => setImproving(false), 6000);
      prevTone.current = n.tone;
      return () => clearTimeout(t);
    }
    prevTone.current = n.tone;
  }, [n.tone]);

  return (
    <section
      className="relative rounded-2xl border bg-gradient-to-br from-white via-white to-nieve overflow-hidden transition-[border-color,box-shadow] duration-[1200ms] ease-out"
      style={{ borderColor: `${n.toneColor}55`, boxShadow: `0 30px 80px -30px ${n.toneColor}33` }}
    >
      <div className="absolute inset-x-0 top-0 h-px transition-colors duration-[1200ms]" style={{ background: `linear-gradient(90deg, transparent, ${n.toneColor}cc, transparent)` }} />
      <div
        className="absolute -top-32 -right-32 w-[400px] h-[400px] rounded-full blur-3xl opacity-30 pointer-events-none transition-colors duration-[1200ms]"
        style={{ background: n.toneColor }}
      />
      {/* Sweep effect when status improves */}
      {improving && <div key={sweepKey} className="status-sweep" />}

      {/* "Estabilizando" badge while sweep is active */}
      {improving && (
        <div
          className="absolute top-4 right-5 z-10 inline-flex items-center gap-1.5 px-3 py-1 rounded-full border bg-emerald-500/15 border-emerald-500/60 text-emerald-600 text-[10px] uppercase tracking-[0.22em] font-bold badge-pulse"
          style={{ color: '#10b981' }}
        >
          <Sparkles className="w-3 h-3" strokeWidth={2.5} />
          <span className="text-emerald-600">ejecución recuperándose</span>
        </div>
      )}

      <div className="relative grid grid-cols-12 gap-6 p-7 items-center">
        {/* Status pill + icon */}
        <div className="col-span-12 lg:col-span-2 flex flex-col items-start gap-2">
          <div className="text-[10px] uppercase tracking-[0.25em] font-bold flex items-center gap-1.5" style={{ color: n.toneColor }}>
            {n.tone === 'bad'
              ? <AlertTriangle className="w-3.5 h-3.5" strokeWidth={2.5} />
              : n.tone === 'warn'
                ? <AlertTriangle className="w-3.5 h-3.5" strokeWidth={2.5} />
                : <PackageCheck className="w-3.5 h-3.5" strokeWidth={2.5} />}
            estado de la red
          </div>
          <div
            className="w-20 h-20 rounded-2xl flex items-center justify-center"
            style={{
              backgroundColor: `${n.toneColor}22`,
              border: `1.5px solid ${n.toneColor}88`,
              boxShadow: `0 0 40px -8px ${n.toneColor}88`,
              color: n.toneColor,
            }}
          >
            <MapPin className="w-9 h-9" strokeWidth={1.6} />
          </div>
          <div className="text-xl font-bold leading-tight" style={{ color: n.toneColor }}>
            {pdv.length} PDV
          </div>
        </div>

        {/* Narrative */}
        <div className="col-span-12 lg:col-span-6">
          <h1 className="text-[26px] leading-tight font-bold text-tinta tracking-tight mb-2.5">
            {n.headline}
          </h1>
          <p className="text-[14px] leading-relaxed text-grafito max-w-prose">
            {n.body}
          </p>
          {categoria && (
            <p className="text-[12px] text-humo mt-3">
              filtro activo: <span className="text-dn-600 font-semibold">{categoria}</span>
            </p>
          )}
        </div>

        {/* Stats grid */}
        <div className="col-span-12 lg:col-span-4 grid grid-cols-2 gap-3">
          <StatTile
            icon={<PackageCheck className="w-4 h-4" strokeWidth={2} />}
            label="Disponibilidad"
            value={`${fmtDecimal(dispRed)}%`}
            tone="accent"
          />
          <StatTile
            icon={<LayoutGrid className="w-4 h-4" strokeWidth={2} />}
            label="Ejecución perfecta"
            value={`${fmtDecimal(ejecRed)}%`}
            tone="neutral"
          />
          <StatTile
            icon={<TrendingUp className="w-4 h-4" strokeWidth={2} />}
            label="Lecturas"
            value={fmtNumber(lecturas)}
            tone="neutral"
            subtext={`${medidos.length} PDV con medición`}
          />
          <StatTile
            icon={<AlertTriangle className="w-4 h-4" strokeWidth={2} />}
            label="PDV en alerta"
            value={`${enAlerta} / ${pdv.length}`}
            tone={enAlerta > 0 ? 'bad' : 'good'}
            subtext={quiebres > 0 ? `${quiebres} quiebres activos` : 'sin quiebres del cliente'}
          />
        </div>
      </div>
    </section>
  );
}

function StatTile({
  icon, label, value, tone, subtext,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: 'accent' | 'good' | 'warn' | 'bad' | 'neutral';
  subtext?: string;
}) {
  const cls = tone === 'accent' ? 'text-dn-600 border-dn-600/30 bg-dn-600/[0.06]'
    : tone === 'good' ? 'text-emerald-600 border-emerald-500/30 bg-emerald-500/[0.06]'
    : tone === 'bad' ? 'text-red-600 border-red-500/30 bg-red-500/[0.06]'
    : tone === 'warn' ? 'text-dn-600 border-dn-600/30 bg-dn-600/[0.06]'
    : 'text-tinta border-marco bg-nieve';
  return (
    <div className={`rounded-xl border ${cls} px-3.5 py-2.5`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest opacity-80 mb-1">
        {icon}
        {label}
      </div>
      <div className="text-xl font-bold tabular-nums leading-none">{value}</div>
      {subtext && <div className="text-[10px] opacity-70 mt-1">{subtext}</div>}
    </div>
  );
}
