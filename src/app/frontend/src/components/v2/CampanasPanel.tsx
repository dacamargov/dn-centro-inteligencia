import { Megaphone } from 'lucide-react';
import { Campana } from '../../lib/api';
import { bandera, fmtNumber, relTime } from '../../lib/format';

const OBJETIVO_LABEL: Record<string, string> = {
  amplificar: 'Amplificar',
  defender: 'Defender',
  lanzar: 'Empujar',
};

const OBJETIVO_COLOR: Record<string, string> = {
  amplificar: 'border-emerald-500/40 bg-emerald-50 text-emerald-700',
  defender: 'border-red-500/40 bg-red-50 text-red-700',
  lanzar: 'border-dn-600/40 bg-dn-50 text-dn-600',
};

export default function CampanasPanel({ campanas }: { campanas: Campana[] }) {
  if (campanas.length === 0) return null;

  const inversion = campanas.reduce((a, c) => a + c.presupuesto_usd, 0);
  const alcance = campanas.reduce((a, c) => a + c.alcance_estimado, 0);

  return (
    <section className="rounded-xl border border-dn-600/30 bg-white overflow-hidden">
      <header className="px-5 py-3 border-b border-marco bg-dn-50 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[11px] uppercase tracking-[0.22em] text-dn-600 font-semibold flex items-center gap-2">
            <Megaphone className="w-3.5 h-3.5" strokeWidth={2.5} />
            Campañas activas · {campanas.length}
          </h2>
          <p className="text-[11px] text-humo mt-0.5">
            lanzadas desde este tablero sobre conversación real
          </p>
        </div>
        <div className="flex gap-6">
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-widest text-humo">Inversión</div>
            <div className="text-lg font-bold text-tinta tabular-nums leading-none">
              US$ {fmtNumber(inversion)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-widest text-humo">Alcance pagado</div>
            <div className="text-lg font-bold text-dn-600 tabular-nums leading-none">
              {fmtNumber(alcance)}
            </div>
          </div>
        </div>
      </header>

      <div className="divide-y divide-marco">
        {campanas.map((c) => {
          // El engagement actual incluye lo que sumó la pauta; el delta contra
          // el orgánico es lo que la campaña realmente aportó.
          const ganado = Math.max(0, (c.engagement_actual ?? 0) - c.engagement_base);
          return (
            <article key={c.campana_id} className="px-5 py-3.5">
              <div className="flex items-start gap-3 flex-wrap">
                <span
                  className={`px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-widest ${
                    OBJETIVO_COLOR[c.objetivo] ?? OBJETIVO_COLOR.lanzar
                  }`}
                >
                  {OBJETIVO_LABEL[c.objetivo] ?? c.objetivo}
                </span>
                <div className="flex-1 min-w-[220px]">
                  <div className="text-[13px] text-tinta font-medium leading-snug">{c.nombre}</div>
                  {c.contenido && (
                    <div className="text-[11.5px] text-humo leading-snug line-clamp-1 mt-0.5">
                      {c.contenido}
                    </div>
                  )}
                </div>
                <div className="text-right text-[11px] tabular-nums">
                  <div className="text-tinta font-semibold">
                    US$ {fmtNumber(c.presupuesto_usd)}
                  </div>
                  <div className="text-humo">{fmtNumber(c.alcance_estimado)} impresiones</div>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-[10.5px] text-humo">
                <span>{c.plataformas.join(' · ') || '—'}</span>
                {c.marca && (
                  <span>
                    {c.country_code ? `${bandera(c.country_code)} ` : ''}
                    {c.marca}
                    {c.categoria ? ` · ${c.categoria}` : ''}
                  </span>
                )}
                {ganado > 0 && (
                  <span className="text-emerald-700 font-medium">
                    +{fmtNumber(ganado)} interacciones desde el lanzamiento
                  </span>
                )}
                {c.creada_en && <span className="ml-auto">{relTime(c.creada_en)}</span>}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
