import { Flame, PackageX, Radio, Thermometer, Zap } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import SocialPostCard from '../components/SocialPostCard';
import AgenteEnContexto from '../components/v2/AgenteEnContexto';
import AmplificarDialog from '../components/v2/AmplificarDialog';
import BrandThermometer from '../components/v2/BrandThermometer';
import CampanasPanel from '../components/v2/CampanasPanel';
import TrendingPostHero from '../components/v2/TrendingPostHero';
import {
  api, Campana, Recomendacion, SocialCategoria, SocialPost, TermometroMarca,
} from '../lib/api';
import { fmtDecimal, fmtNumber } from '../lib/format';
import { CATEGORY_ICON } from '../lib/icons';

const PLATAFORMAS = ['', 'twitter', 'instagram', 'tiktok'];
const PLATAFORMA_LABEL: Record<string, string> = {
  '': 'Todas',
  twitter: 'X / Twitter',
  instagram: 'Instagram',
  tiktok: 'TikTok',
};

/**
 * El puente entre lo que vio el agente y lo que hace la persona.
 *
 * Cuando el agente recomienda amplificar, trae el post_id y la ganancia
 * proyectada en `suggested_action.params`. Aprobar la recomendación deja
 * constancia de la decisión; este botón la ejecuta: abre la campaña sobre ese
 * post concreto. Si la recomendación no señala un post, no hay nada que
 * viralizar y el botón no aparece.
 */
function BotonViralizar({
  rec,
  onViralizar,
}: {
  rec: Recomendacion;
  onViralizar: (postId: string) => void;
}) {
  const sa = (rec.suggested_action ?? {}) as any;
  if (sa.type !== 'amplificar_contenido') return null;
  const postId: string | undefined = sa.params?.post_id;
  if (!postId) return null;

  const alcance = Number(sa.params?.alcance_estimado ?? 0);

  return (
    <button
      onClick={() => onViralizar(postId)}
      className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-dn-600 hover:bg-dn-700 text-white text-sm font-semibold transition-colors"
    >
      <Zap className="w-4 h-4" strokeWidth={2.5} />
      Hacer viral este post
      {alcance > 0 && (
        <span className="font-normal opacity-90">
          · +{fmtNumber(alcance)} impresiones proyectadas
        </span>
      )}
    </button>
  );
}

// Volumen de posts por minuto en la última media hora.
function VolumeSparkline({ feed }: { feed: SocialPost[] }) {
  const buckets = useMemo(() => {
    const now = Date.now();
    const bins = Array.from({ length: 30 }, () => 0);
    for (const p of feed) {
      const diff = Math.floor((now - new Date(p.posted_at).getTime()) / 60_000);
      if (diff >= 0 && diff < 30) bins[29 - diff] += 1;
    }
    return bins;
  }, [feed]);
  const max = Math.max(1, ...buckets);
  return (
    <svg viewBox="0 0 90 24" width="100" height="24" className="opacity-80">
      {buckets.map((v, i) => {
        const h = (v / max) * 22;
        return (
          <rect
            key={i}
            x={i * 3}
            y={24 - h}
            width={2}
            height={h}
            fill="#33bdee"
            rx={0.5}
            opacity={i === buckets.length - 1 ? 1 : 0.5}
          />
        );
      })}
    </svg>
  );
}

export default function Marca() {
  const [feed, setFeed] = useState<SocialPost[]>([]);
  const [viral, setViral] = useState<SocialPost[]>([]);
  const [termometro, setTermometro] = useState<TermometroMarca[]>([]);
  const [porCategoria, setPorCategoria] = useState<SocialCategoria[]>([]);
  const [plataforma, setPlataforma] = useState('');
  const [cliente, setCliente] = useState('');
  const [campanas, setCampanas] = useState<Campana[]>([]);
  const [amplificando, setAmplificando] = useState<SocialPost | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.config().then((c) => setCliente(c.cliente)).catch(() => {});
  }, []);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [a, b, t, c, camp] = await Promise.all([
          api.socialRecientes({ platform: plataforma || undefined, limit: 60 }),
          api.socialVirales(15),
          api.socialTermometro(60),
          api.socialPorCategoria(60),
          api.campanas(20).catch(() => [] as Campana[]),
        ]);
        if (!active) return;
        setFeed(a);
        setViral(b);
        setTermometro(t);
        setPorCategoria(c);
        setCampanas(camp);
        setError(null);
      } catch (e: any) {
        if (active) setError(e?.message ?? String(e));
      }
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [plataforma]);

  const conCampana = useMemo(
    () => new Set(campanas.map((c) => c.post_id)),
    [campanas],
  );

  const onCampanaCreada = (c: Campana) => {
    setCampanas((cur) => [c, ...cur]);
    setAmplificando(null);
    setAviso(
      `Campaña lanzada · ${fmtNumber(c.alcance_estimado)} impresiones sobre ${c.plataformas.join(', ')}`,
    );
    // El post pasa a viral en el mismo instante; el refresco de 8s lo confirma
    // contra la tabla, pero adelantarlo evita que la pantalla se sienta muerta.
    setFeed((cur) =>
      cur.map((p) => (p.post_id === c.post_id ? { ...p, is_viral: true } : p)),
    );
    window.setTimeout(() => setAviso(null), 9000);
  };

  /**
   * El agente ya identificó la ganancia del post; esto lo trae a la pantalla
   * para que una persona decida. El post puede haber salido del feed visible,
   * así que si no está cargado se pide por id antes de abrir el diálogo.
   */
  const abrirAmplificar = async (postId: string) => {
    const enPantalla = [...feed, ...viral].find((p) => p.post_id === postId);
    if (enPantalla) {
      setAmplificando(enPantalla);
      return;
    }
    try {
      setAmplificando(await api.socialPost(postId));
    } catch {
      setAviso('Ese post ya no está disponible en la ventana de escucha.');
      window.setTimeout(() => setAviso(null), 6000);
    }
  };

  const topViral = useMemo(
    () => [...viral].sort((a, b) => b.engagement - a.engagement).slice(0, 3),
    [viral],
  );

  const feedReciente = useMemo(() => {
    const ids = new Set(topViral.map((v) => v.post_id));
    return feed.filter((p) => !ids.has(p.post_id)).slice(0, 16);
  }, [feed, topViral]);

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.25em] text-dn-600/80 font-bold mb-1">
            Marca y consumidor
          </div>
          <h1 className="text-2xl font-semibold text-tinta leading-tight">
            La conversación, cruzada con el anaquel
          </h1>
          <p className="text-xs text-humo mt-0.5">
            X, Instagram y TikTok en diez mercados · actualiza cada 8s
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <div className="text-[10px] uppercase tracking-widest text-humo mb-1">
              Volumen 30 min
            </div>
            <VolumeSparkline feed={feed} />
          </div>
          <div className="flex gap-1 bg-white border border-marco rounded-md p-1">
            {PLATAFORMAS.map((p) => (
              <button
                key={p || 'all'}
                onClick={() => setPlataforma(p)}
                className={`px-3 py-1.5 text-xs uppercase tracking-wider rounded transition-colors ${
                  plataforma === p
                    ? 'bg-dn-400 text-tinta font-semibold'
                    : 'text-grafito hover:text-tinta'
                }`}
              >
                {PLATAFORMA_LABEL[p]}
              </button>
            ))}
          </div>
        </div>
      </header>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-600 text-sm rounded p-3">
          {error}
        </div>
      )}

      {aviso && (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-50 text-emerald-800 text-sm px-4 py-2.5">
          {aviso}
        </div>
      )}

      <BrandThermometer posts={feed} fabricante={cliente || undefined} />

      {/* El agente de sentimiento a veces detectaba un quiebre de anaquel detrás
          de una queja. Es un buen hallazgo, pero reponer no se decide desde acá:
          esta pantalla solo acepta acciones de comunicación. */}
      <AgenteEnContexto
        agente="sentimiento_marca"
        limite={1}
        acciones={['amplificar_contenido', 'respuesta_crisis']}
        accionPrimaria={(rec) => <BotonViralizar rec={rec} onViralizar={abrirAmplificar} />}
      />

      <CampanasPanel campanas={campanas} />

      <div className="grid lg:grid-cols-2 gap-4">
        <RankingMarcas data={termometro} />
        <SentimientoVsAnaquel data={porCategoria} />
      </div>

      {topViral.length > 0 && (
        <section>
          <h2 className="text-[10px] uppercase tracking-[0.25em] text-grafito font-semibold mb-3 flex items-center gap-2">
            <Flame className="w-3.5 h-3.5 text-dn-600" strokeWidth={2} />
            Viral ahora · últimos 15 min
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {topViral.map((p) => (
              <TrendingPostHero
                key={p.post_id}
                post={p}
                onAmplificar={setAmplificando}
                yaTieneCampana={conCampana.has(p.post_id)}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-[10px] uppercase tracking-[0.25em] text-grafito font-semibold mb-3 flex items-center gap-2">
          <Radio className="w-3.5 h-3.5 text-emerald-600" strokeWidth={2} />
          Feed reciente
          <span className="text-humo normal-case font-normal tracking-normal">
            · {feedReciente.length} posts
          </span>
        </h2>
        {feedReciente.length === 0 ? (
          <div className="text-center py-12 bg-white border border-marco rounded-lg text-humo text-sm">
            Sin posts por ahora.
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {feedReciente.map((p) => (
              <SocialPostCard
                key={p.post_id}
                post={p}
                cliente={cliente || undefined}
                onAmplificar={setAmplificando}
                yaTieneCampana={conCampana.has(p.post_id)}
              />
            ))}
          </div>
        )}
      </section>

      {amplificando && (
        <AmplificarDialog
          post={amplificando}
          onClose={() => setAmplificando(null)}
          onCreada={onCampanaCreada}
        />
      )}
    </div>
  );
}

function RankingMarcas({ data }: { data: TermometroMarca[] }) {
  const max = Math.max(1, ...data.map((d) => d.menciones));
  return (
    <section className="rounded-xl border border-marco bg-white overflow-hidden">
      <header className="px-5 py-3 border-b border-marco">
        <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
          <Thermometer className="w-3.5 h-3.5 text-dn-600" strokeWidth={2} />
          Termómetro por marca · última hora
        </h2>
        <p className="text-[11px] text-humo mt-0.5">
          score 0-100 · nuestras marcas resaltadas
        </p>
      </header>
      <div className="p-4 space-y-2">
        {data.length === 0 && (
          <div className="text-center py-8 text-humo text-sm">Sin menciones en la ventana.</div>
        )}
        {data.map((m) => {
          const color = m.score >= 65 ? '#34d399' : m.score >= 45 ? '#fb923c' : '#ef4444';
          return (
            <div
              key={m.marca}
              className={[
                'grid grid-cols-[150px_1fr_120px] gap-3 items-center rounded-lg px-2 py-1.5',
                m.es_cliente ? 'bg-dn-400/[0.07] border border-dn-400/25' : '',
              ].join(' ')}
            >
              <div className="min-w-0">
                <div className="text-[12px] text-tinta truncate font-medium">{m.marca}</div>
                <div className="text-[10px] text-humo truncate">{m.fabricante ?? '—'}</div>
              </div>
              <div className="relative h-2.5 rounded-full bg-nieve overflow-hidden">
                <div
                  className="h-full rounded-full transition-[width] duration-700"
                  style={{ width: `${(m.menciones / max) * 100}%`, backgroundColor: `${color}99` }}
                />
              </div>
              <div className="text-right text-[11px] tabular-nums">
                <span className="font-bold" style={{ color }}>
                  {Math.round(m.score)}
                </span>
                <span className="text-humo"> · {m.menciones} menc.</span>
                {m.virales > 0 && (
                  <div className="text-[10px] text-orange-600">{m.virales} virales</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SentimientoVsAnaquel({ data }: { data: SocialCategoria[] }) {
  return (
    <section className="rounded-xl border border-marco bg-white overflow-hidden">
      <header className="px-5 py-3 border-b border-marco">
        <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
          <PackageX className="w-3.5 h-3.5 text-orange-600" strokeWidth={2} />
          Conversación vs disponibilidad
        </h2>
        <p className="text-[11px] text-humo mt-0.5">
          la queja en redes casi siempre viene después del quiebre en anaquel
        </p>
      </header>
      <div className="p-4 space-y-2.5">
        {data.length === 0 && (
          <div className="text-center py-8 text-humo text-sm">
            Sin posts categorizados en la ventana.
          </div>
        )}
        {data.map((c) => {
          const CI = CATEGORY_ICON[c.categoria];
          const scoreColor = c.score >= 65 ? '#34d399' : c.score >= 45 ? '#fb923c' : '#ef4444';
          const dispBaja = c.disponibilidad_pct != null && c.disponibilidad_pct < 90;
          return (
            <div
              key={c.categoria}
              className="grid grid-cols-[170px_1fr_auto] gap-3 items-center"
            >
              <div className="flex items-center gap-2 min-w-0 text-[12px] text-grafito">
                {CI && <CI className="w-3.5 h-3.5 text-humo flex-shrink-0" strokeWidth={1.8} />}
                <span className="truncate">{c.categoria}</span>
              </div>
              <div className="relative h-5 rounded-full bg-nieve overflow-hidden">
                <div
                  className="h-full transition-[width] duration-700"
                  style={{ width: `${c.score}%`, backgroundColor: `${scoreColor}88` }}
                />
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold tabular-nums text-tinta">
                  score {Math.round(c.score)}
                </span>
              </div>
              <div className="text-right text-[11px] tabular-nums w-[130px]">
                <span className={dispBaja ? 'text-red-600 font-semibold' : 'text-grafito'}>
                  disp{' '}
                  {c.disponibilidad_pct == null ? '—' : `${fmtDecimal(c.disponibilidad_pct)}%`}
                </span>
                <div className="text-[10px] text-humo">
                  {fmtNumber(c.menciones)} menc. · {fmtDecimal(c.negativos_pct)}% neg.
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
