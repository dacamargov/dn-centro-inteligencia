import { Megaphone } from 'lucide-react';
import { PromocionGondola } from '../../lib/api';
import { bandera, fmtPrecio, relTime } from '../../lib/format';

interface Props {
  promociones: PromocionGondola[];
}

export default function PromocionesPanel({ promociones }: Props) {
  if (promociones.length === 0) return null;

  return (
    <section className="rounded-xl border border-dn-600/30 bg-white overflow-hidden">
      <header className="px-5 py-3 border-b border-marco bg-dn-50/60">
        <h2 className="text-[11px] uppercase tracking-[0.22em] text-dn-600 font-semibold flex items-center gap-2">
          <Megaphone className="w-3.5 h-3.5" strokeWidth={2} />
          Promociones en góndola · activas
        </h2>
        <p className="text-[11px] text-humo mt-0.5">
          lanzadas desde el simulador · cada fila queda en el log de acciones para rastreo
        </p>
      </header>
      <ul className="divide-y divide-marco max-h-[280px] overflow-y-auto">
        {promociones.map((p) => (
          <li key={p.promo_id} className="px-5 py-3 flex items-start gap-3 hover:bg-nieve/80">
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold text-tinta truncate">
                {p.producto ?? p.sku}
              </div>
              <div className="text-[11px] text-humo mt-0.5">
                {bandera(p.country_code)} {p.cadena} · {p.marca ?? p.sku}
              </div>
              <div className="text-[12px] text-grafito mt-1">
                <span className="font-semibold text-dn-600">{p.descuento_pct}% off</span>
                {' · '}
                {p.duracion}
                {' · '}
                góndola {fmtPrecio(p.precio_gondola_usd)}
                <span className="text-humo"> (antes {fmtPrecio(p.precio_base_usd)})</span>
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-[10px] uppercase tracking-widest text-humo">log</div>
              <div className="text-[10px] font-mono text-grafito">{p.promo_id}</div>
              <div className="text-[10px] text-humo mt-0.5">{relTime(p.lanzada_en)}</div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
