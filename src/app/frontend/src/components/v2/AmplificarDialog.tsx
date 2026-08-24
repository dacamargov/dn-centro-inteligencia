import { Loader2, Megaphone, Target, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { api, Campana, ObjetivoCampana, SocialPost } from '../../lib/api';
import { fmtNumber } from '../../lib/format';

// Mismos rendimientos que usa el backend para calcular el alcance. Están
// duplicados a propósito: la estimación se mueve mientras el usuario arrastra
// el presupuesto, y pedirla al servidor en cada píxel no vale la pena.
const ALCANCE_POR_USD: Record<string, number> = {
  tiktok: 420,
  instagram: 260,
  facebook: 310,
  x: 190,
};

const PLATAFORMA_LABEL: Record<string, string> = {
  x: 'X / Twitter',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  facebook: 'Facebook',
};

const OBJETIVOS: { id: ObjetivoCampana; label: string; ayuda: string }[] = [
  {
    id: 'amplificar',
    label: 'Amplificar',
    ayuda: 'poner pauta detrás de una conversación que ya funciona sola',
  },
  {
    id: 'defender',
    label: 'Defender',
    ayuda: 'contrarrestar una narrativa negativa con contenido propio',
  },
  {
    id: 'lanzar',
    label: 'Empujar',
    ayuda: 'sostener un lanzamiento o una promoción en curso',
  },
];

interface Props {
  post: SocialPost;
  onClose: () => void;
  onCreada: (c: Campana) => void;
}

export default function AmplificarDialog({ post, onClose, onCreada }: Props) {
  const sugerido: ObjetivoCampana = post.sentiment === 'negativo' ? 'defender' : 'amplificar';
  const [objetivo, setObjetivo] = useState<ObjetivoCampana>(sugerido);
  const [presupuesto, setPresupuesto] = useState(5000);
  const [plataformas, setPlataformas] = useState<string[]>(() =>
    ALCANCE_POR_USD[post.platform] ? [post.platform] : ['instagram'],
  );
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const alcance = useMemo(() => {
    if (!plataformas.length) return 0;
    const porPlataforma = presupuesto / plataformas.length;
    return Math.round(
      plataformas.reduce((a, p) => a + porPlataforma * (ALCANCE_POR_USD[p] ?? 0), 0),
    );
  }, [presupuesto, plataformas]);

  // Multiplicador sobre lo que el post logró orgánicamente: es la cifra que
  // hace tangible la decisión, más que las impresiones absolutas.
  const multiplicador = post.engagement > 0 ? alcance / post.engagement : 0;

  const toggle = (p: string) =>
    setPlataformas((cur) =>
      cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p],
    );

  const lanzar = async () => {
    if (!plataformas.length) {
      setError('Elige al menos una plataforma.');
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const c = await api.amplificar(post.post_id, {
        objetivo,
        presupuesto_usd: presupuesto,
        plataformas,
      });
      onCreada(c);
    } catch (e: any) {
      setError(String(e?.message ?? e).slice(0, 200));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dn-900/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-2xl border border-marco bg-white shadow-[0_40px_120px_-30px_rgba(20,38,59,0.45)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 px-6 py-4 border-b border-marco bg-nieve">
          <div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-dn-600 font-bold mb-1 flex items-center gap-1.5">
              <Megaphone className="w-3.5 h-3.5" strokeWidth={2.5} />
              Convertir en campaña
            </div>
            <h2 className="text-lg font-semibold text-tinta leading-tight">
              Amplificar {post.author_handle}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-humo hover:text-tinta transition-colors"
            aria-label="Cerrar"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        <div className="px-6 py-5 space-y-5">
          <blockquote className="rounded-lg border border-marco bg-nieve px-4 py-3 text-[13px] text-grafito leading-relaxed">
            {post.content}
            <div className="mt-2 text-[11px] text-humo tabular-nums">
              {fmtNumber(post.engagement)} interacciones orgánicas
              {post.marca ? ` · ${post.marca}` : ''}
            </div>
          </blockquote>

          <div>
            <label className="text-[10px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-1.5 mb-2">
              <Target className="w-3.5 h-3.5" strokeWidth={2.5} />
              Objetivo
            </label>
            <div className="grid grid-cols-3 gap-2">
              {OBJETIVOS.map((o) => {
                const on = objetivo === o.id;
                return (
                  <button
                    key={o.id}
                    onClick={() => setObjetivo(o.id)}
                    className={[
                      'rounded-lg border px-3 py-2.5 text-left transition-colors',
                      on
                        ? 'border-dn-600 bg-dn-50 ring-1 ring-dn-600/30'
                        : 'border-marco bg-white hover:border-dn-300',
                    ].join(' ')}
                  >
                    <div
                      className={`text-[13px] font-semibold ${on ? 'text-dn-600' : 'text-tinta'}`}
                    >
                      {o.label}
                    </div>
                    <div className="text-[10.5px] text-humo leading-snug mt-0.5">{o.ayuda}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="text-[10px] uppercase tracking-[0.22em] text-grafito font-semibold mb-2 block">
              Plataformas
            </label>
            <div className="flex flex-wrap gap-2">
              {Object.keys(ALCANCE_POR_USD).map((p) => {
                const on = plataformas.includes(p);
                return (
                  <button
                    key={p}
                    onClick={() => toggle(p)}
                    className={[
                      'px-3 py-1.5 rounded-full border text-[12px] font-medium transition-colors',
                      on
                        ? 'border-dn-600 bg-dn-600 text-white'
                        : 'border-marco bg-white text-grafito hover:border-dn-300',
                    ].join(' ')}
                  >
                    {PLATAFORMA_LABEL[p]}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-2">
              <label className="text-[10px] uppercase tracking-[0.22em] text-grafito font-semibold">
                Presupuesto
              </label>
              <span className="text-lg font-bold text-tinta tabular-nums">
                US$ {fmtNumber(presupuesto)}
              </span>
            </div>
            <input
              type="range"
              min={500}
              max={50000}
              step={500}
              value={presupuesto}
              onChange={(e) => setPresupuesto(Number(e.target.value))}
              className="w-full accent-dn-600"
            />
            <div className="flex justify-between text-[10px] text-humo tabular-nums mt-1">
              <span>US$ 500</span>
              <span>US$ 50.000</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-dn-600/30 bg-dn-50 px-4 py-3">
              <div className="text-[10px] uppercase tracking-widest text-dn-600 mb-1">
                Alcance pagado estimado
              </div>
              <div className="text-2xl font-bold text-dn-600 tabular-nums leading-none">
                {fmtNumber(alcance)}
              </div>
              <div className="text-[10px] text-humo mt-1">
                impresiones sobre {plataformas.length || 0} plataforma
                {plataformas.length === 1 ? '' : 's'}
              </div>
            </div>
            <div className="rounded-xl border border-marco bg-nieve px-4 py-3">
              <div className="text-[10px] uppercase tracking-widest text-humo mb-1">
                Contra el orgánico
              </div>
              <div className="text-2xl font-bold text-tinta tabular-nums leading-none">
                {multiplicador >= 1 ? `${Math.round(multiplicador)}×` : '—'}
              </div>
              <div className="text-[10px] text-humo mt-1">
                el post ya trae {fmtNumber(post.engagement)} interacciones
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/40 bg-red-50 text-red-700 text-[12px] px-3 py-2">
              {error}
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-3 px-6 py-4 border-t border-marco bg-nieve">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-[13px] text-grafito hover:text-tinta transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={lanzar}
            disabled={enviando}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-dn-600 hover:bg-dn-700 text-white text-[13px] font-semibold transition-colors disabled:opacity-60"
          >
            {enviando ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Lanzando…
              </>
            ) : (
              <>
                <Megaphone className="w-4 h-4" strokeWidth={2.5} />
                Lanzar campaña
              </>
            )}
          </button>
        </footer>
      </div>
    </div>
  );
}
