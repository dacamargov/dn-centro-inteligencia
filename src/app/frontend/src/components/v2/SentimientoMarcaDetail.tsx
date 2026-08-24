import { Flame, MessageSquareHeart, Thermometer } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api, SocialCategoria, SocialPost, TermometroMarca } from '../../lib/api';
import { fmtDecimal, fmtNumber } from '../../lib/format';
import { CATEGORY_ICON } from '../../lib/icons';

// Palabras vacías del español más el ruido propio del dominio: no aportan al
// tema de la queja y ensucian el conteo.
const STOP = new Set([
  'el','la','los','las','un','una','unos','unas','de','del','y','o','para','que','no','con','ya','en',
  'es','yo','mi','mis','esto','esta','eso','esa','se','le','lo','muy','mas','más','pero','por','al','su',
  'sus','como','cuando','donde','hay','tiene','tienen','está','estan','están','este','ese','nada','todo',
  'super','tienda','marca','producto','precio',
]);

export default function SentimientoMarcaDetail() {
  const [porCategoria, setPorCategoria] = useState<SocialCategoria[]>([]);
  const [termometro, setTermometro] = useState<TermometroMarca[]>([]);
  const [recientes, setRecientes] = useState<SocialPost[]>([]);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [c, t, r] = await Promise.all([
          api.socialPorCategoria(60),
          api.socialTermometro(60),
          api.socialRecientes({ solo_cliente: true, limit: 80 }),
        ]);
        if (!active) return;
        setPorCategoria(c);
        setTermometro(t);
        setRecientes(r);
      } catch {
        /* mantiene el último dato bueno */
      }
    };
    tick();
    const id = setInterval(tick, 12000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const temas = useMemo(() => {
    const neg = recientes.filter((p) => p.sentiment === 'negativo');
    const words: Record<string, number> = {};
    for (const p of neg) {
      const tokens = p.content
        .toLowerCase()
        .replace(/[^\wáéíóúñü ]/g, ' ')
        .split(/\s+/)
        .filter((w) => w.length >= 4 && !STOP.has(w));
      for (const t of tokens) words[t] = (words[t] ?? 0) + 1;
    }
    return Object.entries(words)
      .map(([w, count]) => ({ w, count }))
      .filter((x) => x.count >= 2)
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [recientes]);

  const nuestras = termometro.filter((m) => m.es_cliente);
  const maxTema = Math.max(1, ...temas.map((t) => t.count));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <section className="lg:col-span-2 rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
            <MessageSquareHeart className="w-3.5 h-3.5 text-violet-600" strokeWidth={2} />
            Sentimiento por categoría · última hora
          </h3>
          <p className="text-[11px] text-humo mt-0.5">
            cruzado contra la disponibilidad medida en el mismo período
          </p>
        </header>
        <div className="p-4 space-y-2.5">
          {porCategoria.length === 0 && (
            <div className="text-center py-6 text-humo text-sm">
              Sin posts categorizados en esta ventana.
            </div>
          )}
          {porCategoria.map((c) => {
            const CI = CATEGORY_ICON[c.categoria];
            const color = c.score >= 65 ? '#34d399' : c.score >= 45 ? '#fb923c' : '#ef4444';
            const dispBaja = c.disponibilidad_pct != null && c.disponibilidad_pct < 90;
            return (
              <div key={c.categoria} className="grid grid-cols-[170px_1fr_120px] gap-3 items-center">
                <div className="flex items-center gap-2 min-w-0 text-[12px] text-grafito">
                  {CI && <CI className="w-3.5 h-3.5 text-humo flex-shrink-0" strokeWidth={1.8} />}
                  <span className="truncate">{c.categoria}</span>
                </div>
                <div className="relative h-5 rounded-full bg-nieve overflow-hidden">
                  <div
                    className="h-full transition-[width] duration-700"
                    style={{ width: `${c.score}%`, backgroundColor: `${color}88` }}
                  />
                </div>
                <div className="text-right text-[11px] tabular-nums">
                  <span className="font-semibold text-tinta">{Math.round(c.score)}</span>
                  <span className="text-humo"> · {fmtNumber(c.menciones)}</span>
                  <div className={`text-[10px] ${dispBaja ? 'text-red-600' : 'text-humo'}`}>
                    disp{' '}
                    {c.disponibilidad_pct == null ? '—' : `${fmtDecimal(c.disponibilidad_pct)}%`}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-xl border border-orange-500/30 bg-orange-500/[0.04] overflow-hidden">
        <header className="px-5 py-3 border-b border-orange-500/30">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-orange-600 font-semibold flex items-center gap-2">
            <Flame className="w-3.5 h-3.5" strokeWidth={2} />
            Términos en alza · negativos
          </h3>
          <p className="text-[11px] text-orange-600/60 mt-0.5">
            palabras que se repiten en las quejas sobre nuestras marcas
          </p>
        </header>
        <div className="p-4 space-y-1.5">
          {temas.length === 0 && (
            <div className="text-center py-6 text-humo text-sm">
              Sin temas recurrentes ahora.
            </div>
          )}
          {temas.map((t) => (
            <div key={t.w} className="flex items-center gap-2">
              <span className="text-[12px] text-tinta w-28 truncate">{t.w}</span>
              <div className="flex-1 h-2 rounded-full bg-nieve overflow-hidden">
                <div
                  className="h-full bg-orange-500/60 rounded-full"
                  style={{ width: `${(t.count / maxTema) * 100}%` }}
                />
              </div>
              <span className="text-[11px] text-humo tabular-nums w-6 text-right">
                {t.count}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="lg:col-span-3 rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h3 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
            <Thermometer className="w-3.5 h-3.5 text-dn-600" strokeWidth={2} />
            Score de nuestras marcas
          </h3>
        </header>
        <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          {nuestras.map((m) => {
            const color = m.score >= 65 ? '#34d399' : m.score >= 45 ? '#fb923c' : '#ef4444';
            return (
              <div key={m.marca} className="rounded-lg bg-nieve border border-marco px-3 py-2.5">
                <div className="text-[12px] font-semibold text-tinta truncate">{m.marca}</div>
                <div className="text-xl font-bold tabular-nums" style={{ color }}>
                  {Math.round(m.score)}
                </div>
                <div className="flex items-center justify-between mt-1 text-[10px] text-humo tabular-nums">
                  <span>{fmtNumber(m.menciones)} menc.</span>
                  <span className={m.negativos_pct > 30 ? 'text-red-600' : ''}>
                    {fmtDecimal(m.negativos_pct)}% neg.
                  </span>
                </div>
              </div>
            );
          })}
          {nuestras.length === 0 && (
            <div className="col-span-full text-center py-6 text-humo text-sm">
              Sin menciones de nuestras marcas en la ventana.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
