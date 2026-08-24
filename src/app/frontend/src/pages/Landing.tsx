import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, ArrowUpRight, Megaphone, Radar, Tag } from 'lucide-react';
import { api, Kpis, Pdv } from '../lib/api';
import { fmtDecimal, fmtNumber } from '../lib/format';

interface Modulo {
  title: string;
  pitch: string;
  tagline: string;
  Icon: typeof Activity;
  gradient: string;
  to: string;
}

// Los cuatro módulos espejan las líneas de servicio de D&N: ejecución en el
// punto de venta, precio y promoción, marca, y la salida a la fuerza de campo.
const MODULOS: Modulo[] = [
  {
    title: 'Ejecución en el punto de venta',
    pitch: 'Disponibilidad, planograma y share of shelf medidos visita a visita',
    tagline: 'StoreConnect AI · Unity Catalog · Agentes',
    Icon: Activity,
    gradient: 'from-dn-400 via-dn-500 to-dn-700',
    to: '/ejecucion',
  },
  {
    title: 'Precio y promoción',
    pitch: 'Índice de precio normalizado contra la competencia, por cadena y país',
    tagline: 'Price Tracking · Genie · AI/BI',
    Icon: Tag,
    gradient: 'from-rose-400 via-rose-500 to-dn-700',
    to: '/precios',
  },
  {
    title: 'Marca y consumidor',
    pitch: 'Escucha social cruzada contra lo que realmente pasa en el anaquel',
    tagline: 'Brand & Ad Insight · Mosaic AI',
    Icon: Megaphone,
    gradient: 'from-violet-400 via-violet-500 to-dn-700',
    to: '/marca',
  },
  {
    title: 'Copiloto de campo',
    pitch: 'La siguiente acción del mercaderista, servida en menos de 100 ms',
    tagline: 'Lakebase Postgres · Online Features',
    Icon: Radar,
    gradient: 'from-teal-400 via-emerald-500 to-dn-700',
    to: '/campo',
  },
];

export default function Landing() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [pdv, setPdv] = useState<Pdv[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [k, p] = await Promise.all([api.kpis(), api.pdv()]);
        if (!active) return;
        setKpis(k);
        setPdv(p);
      } catch {
        // La portada sigue siendo usable aunque el backend esté degradado.
      }
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const pdvMedidos = pdv?.filter((p) => p.observaciones > 0).length ?? null;
  const pdvTotal = pdv?.length ?? null;

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-lienzo">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07] animate-grid-shift"
        style={{
          backgroundImage:
            'linear-gradient(rgba(51,189,238,0.35) 1px, transparent 1px),' +
            'linear-gradient(90deg, rgba(51,189,238,0.35) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="pointer-events-none absolute -top-40 -right-40 w-[720px] h-[720px] rounded-full bg-dn-600/20 blur-[130px] animate-blob-drift-a" />
      <div className="pointer-events-none absolute -bottom-48 -left-48 w-[720px] h-[720px] rounded-full bg-dn-400/10 blur-[130px] animate-blob-drift-b" />
      <div className="pointer-events-none absolute top-1/3 left-1/2 -translate-x-1/2 w-[520px] h-[520px] rounded-full bg-dn-100/30 blur-[150px] animate-blob-pulse" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(0,0,0,0)_0%,rgba(0,0,0,0.55)_70%)]" />

      <div className="relative max-w-[1500px] mx-auto px-8 py-12 space-y-12">
        <header className="flex flex-col lg:flex-row gap-8 lg:items-end justify-between">
          <div className="max-w-3xl">
            <div className="text-[10px] uppercase tracking-[0.32em] text-dn-600/80 font-bold mb-3">
              dichter &amp; neira · Medición continua de mercado
            </div>
            <h1 className="text-5xl md:text-6xl font-bold text-tinta leading-[1.05] tracking-tight">
              Centro de{' '}
              <span className="bg-gradient-to-r from-dn-400 via-dn-400 to-dn-500 bg-clip-text text-transparent">
                Inteligencia
              </span>
            </h1>
            <p className="text-grafito text-base md:text-lg mt-4 max-w-2xl leading-relaxed">
              Lo que pasa en el anaquel, medido{' '}
              <span className="text-tinta font-medium">visita a visita</span> en diez
              mercados, cruzado con{' '}
              <span className="text-tinta font-medium">precio, promoción y conversación</span>,
              y convertido en{' '}
              <span className="text-tinta font-medium">la próxima acción de campo</span>.
            </p>
          </div>

          <div className="text-right shrink-0">
            <div className="text-[9px] uppercase tracking-[0.25em] text-humo font-semibold mb-1">
              Construido sobre
            </div>
            <div className="text-[13px] tracking-wide text-grafito font-semibold">
              DATABRICKS · MOSAIC AI
            </div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-humo mt-0.5">
              Unity Catalog · Genie · Lakebase
            </div>
          </div>
        </header>

        <div className="rounded-2xl border border-marco bg-nieve backdrop-blur px-8 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <Kpi
              label="Disponibilidad en anaquel"
              value={kpis ? `${fmtDecimal(kpis.disponibilidad_pct)}%` : '—'}
            />
            <Kpi
              label="Ejecución perfecta"
              value={kpis ? `${fmtDecimal(kpis.ejecucion_pct)}%` : '—'}
            />
            <Kpi
              label="PDV medidos"
              value={pdvMedidos != null && pdvTotal != null ? `${pdvMedidos} / ${pdvTotal}` : '—'}
            />
            <Kpi
              label="Lecturas por minuto"
              value={kpis ? fmtNumber(Math.round(kpis.obs_por_min)) : '—'}
              suffix={
                <span className="text-[10px] uppercase tracking-widest text-emerald-600 ml-2 font-semibold inline-flex items-center gap-1">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  en vivo
                </span>
              }
            />
          </div>
        </div>

        <section className="space-y-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[10px] uppercase tracking-[0.28em] text-humo font-bold">
              Módulos del centro
            </h2>
            <div className="text-[11px] uppercase tracking-widest text-humo">
              4 dominios · 1 lakehouse
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {MODULOS.map((m, i) => (
              <Tile key={m.title} modulo={m} index={i} onOpen={() => navigate(m.to)} />
            ))}
          </div>
        </section>

        <div className="text-center pt-4">
          <div className="text-[10px] uppercase tracking-[0.25em] text-humo">
            dichter &amp; neira · Centro de Inteligencia · Demostración en vivo
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, suffix }: { label: string; value: string; suffix?: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.22em] text-humo font-semibold mb-1.5">
        {label}
      </div>
      <div className="flex items-baseline">
        <span className="text-2xl md:text-3xl font-bold tabular-nums text-tinta leading-none">
          {value}
        </span>
        {suffix}
      </div>
    </div>
  );
}

function Tile({
  modulo,
  index,
  onOpen,
}: {
  modulo: Modulo;
  index: number;
  onOpen: () => void;
}) {
  return (
    <button
      onClick={onOpen}
      style={{ animationDelay: `${100 + index * 80}ms` }}
      className={[
        'group relative text-left rounded-2xl overflow-hidden p-7 min-h-[200px]',
        'border border-marco transition-all duration-300 cursor-pointer',
        'hover:border-dn-400/60 hover:scale-[1.015]',
        'hover:shadow-[0_18px_60px_-20px_rgba(51,189,238,0.5)]',
        'animate-[slide-in-right_0.5s_cubic-bezier(0.22,1,0.36,1)_both]',
      ].join(' ')}
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${modulo.gradient} opacity-95`} />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(0,0,0,0.6)_0%,rgba(0,0,0,0)_60%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(255,255,255,0.16)_0%,rgba(255,255,255,0)_45%)]" />

      <div className="relative flex flex-col h-full">
        <div className="flex items-start justify-between gap-3">
          <div className="w-11 h-11 rounded-xl bg-black/30 backdrop-blur flex items-center justify-center border border-white/15">
            <modulo.Icon className="w-5 h-5 text-white" strokeWidth={2} />
          </div>
          <span className="text-[10px] uppercase tracking-[0.22em] font-bold px-2.5 py-1 rounded-full bg-emerald-400 text-emerald-950">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-700 mr-1.5 animate-pulse" />
            EN VIVO
          </span>
        </div>

        <div className="mt-auto pt-8">
          <h3 className="text-2xl font-bold leading-tight text-white">{modulo.title}</h3>
          <p className="mt-1.5 text-[13px] leading-snug text-white/85">{modulo.pitch}</p>
          <div className="mt-4 flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-widest font-semibold text-white/70">
              {modulo.tagline}
            </span>
            <ArrowUpRight
              className="w-5 h-5 text-white group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform"
              strokeWidth={2.2}
            />
          </div>
        </div>
      </div>

      <div className="pointer-events-none absolute -bottom-8 -right-4 text-[180px] font-black leading-none select-none text-white/[0.06]">
        {modulo.title.charAt(0)}
      </div>
    </button>
  );
}
