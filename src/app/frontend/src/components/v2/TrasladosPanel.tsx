import {
  ArrowRight, Check, Crosshair, Route, Truck, X,
} from 'lucide-react';
import { useState } from 'react';
import { api, Traslado } from '../../lib/api';
import { bandera, fmtDecimal, fmtNumber, fmtPrecio, fmtUSD, relTime } from '../../lib/format';

interface Props {
  traslados: Traslado[];
  /** Resalta la ruta en el mapa mientras el cursor está sobre la tarjeta. */
  onHover?: (t: Traslado | null) => void;
  /** Lleva el mapa a la ruta, que a escala continental no se ve sola. */
  onEnfocar?: (t: Traslado) => void;
  onDecidido?: (t: Traslado) => void;
}

export default function TrasladosPanel({
  traslados,
  onHover,
  onEnfocar,
  onDecidido,
}: Props) {
  const propuestos = traslados.filter((t) => t.estado === 'propuesto');
  const aprobados = traslados.filter((t) => t.estado === 'aprobado');

  const gananciaEnCola = propuestos.reduce((a, t) => a + t.ganancia_neta_usd, 0);
  const gananciaAprobada = aprobados.reduce((a, t) => a + t.ganancia_neta_usd, 0);

  return (
    <section className="bg-white border border-marco rounded-xl overflow-hidden">
      <header className="px-5 py-3 border-b border-marco">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
              <Route className="w-3.5 h-3.5 text-dn-600" strokeWidth={2} />
              Malla de distribución
            </h2>
            <p className="text-[11px] text-humo mt-0.5">
              el agente cruza cada quiebre con la tienda con sobrestock más cercana ·
              nada se mueve sin aprobación
            </p>
          </div>
          <div className="flex items-center gap-4 text-right">
            <div>
              <div className="text-[9px] uppercase tracking-widest text-humo">en cola</div>
              <div className="text-lg font-bold tabular-nums text-dn-600 leading-none">
                {fmtUSD(gananciaEnCola)}
              </div>
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-widest text-humo">aprobado</div>
              <div
                className={[
                  'text-lg font-bold tabular-nums leading-none',
                  aprobados.length > 0 ? 'text-emerald-700' : 'text-humo',
                ].join(' ')}
              >
                {fmtUSD(gananciaAprobada)}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* La cola: lo único sobre lo que hay que decidir. */}
      <div className="px-5 pt-3 pb-1 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-humo font-semibold">
          Esperando decisión
        </span>
        <span className="text-[10px] tabular-nums text-humo">{propuestos.length}</span>
      </div>

      {propuestos.length === 0 ? (
        <div className="px-5 py-8 text-center text-humo text-[13px]">
          {aprobados.length > 0
            ? 'Cola vacía: decidiste todo lo que el agente puso arriba de la mesa.'
            : 'El agente de red todavía no encontró traslados que rindan. Corre cada dos minutos mientras la demo está encendida.'}
        </div>
      ) : (
        <ul className="divide-y divide-marco max-h-[430px] overflow-y-auto border-t border-marco">
          {propuestos.map((t) => (
            <TrasladoCard
              key={t.traslado_id}
              t={t}
              onHover={onHover}
              onEnfocar={onEnfocar}
              onDecidido={onDecidido}
            />
          ))}
        </ul>
      )}

      {aprobados.length > 0 && (
        <div className="border-t-2 border-emerald-500/30">
          <div className="px-5 py-2 bg-emerald-50/70 flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-widest text-emerald-800 font-semibold flex items-center gap-1.5">
              <Truck className="w-3.5 h-3.5" strokeWidth={2.2} />
              Traslados aprobados · en ruta
            </span>
            <span className="text-[10px] tabular-nums text-emerald-800">
              {aprobados.length} · {fmtNumber(aprobados.reduce((a, t) => a + t.unidades, 0))} unidades
            </span>
          </div>
          <ul className="divide-y divide-marco max-h-[260px] overflow-y-auto">
            {aprobados.map((t) => (
              <TrasladoAprobado
                key={t.traslado_id}
                t={t}
                onHover={onHover}
                onEnfocar={onEnfocar}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function TrasladoCard({
  t,
  onHover,
  onEnfocar,
  onDecidido,
}: {
  t: Traslado;
  onHover?: (t: Traslado | null) => void;
  onEnfocar?: (t: Traslado) => void;
  onDecidido?: (t: Traslado) => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decidir = async (accion: 'aprobar' | 'descartar') => {
    setOcupado(true);
    setError(null);
    try {
      const actualizado = await api.decidirTraslado(t.traslado_id, accion);
      onHover?.(null);
      onDecidido?.(actualizado);
    } catch (e: any) {
      setError(String(e?.message ?? e).slice(0, 90));
      setOcupado(false);
    }
  };

  return (
    <li
      className={['px-4 py-3 transition-opacity', ocupado ? 'opacity-40' : 'hover:bg-nieve'].join(' ')}
      onMouseEnter={() => onHover?.(t)}
      onMouseLeave={() => onHover?.(null)}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-tinta truncate">
            {t.producto ?? t.sku}
          </div>
          <div className="text-[10px] text-humo font-mono">
            {t.sku} · {t.categoria}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[9px] uppercase tracking-widest text-humo">ganancia neta</div>
          <div className="text-lg font-bold tabular-nums leading-none text-dn-600">
            {fmtUSD(t.ganancia_neta_usd)}
          </div>
        </div>
      </div>

      <Ruta t={t} onEnfocar={onEnfocar} />

      <div className="flex items-center gap-3 text-[10px] text-humo tabular-nums mb-2 flex-wrap">
        <span>
          <span className="text-grafito font-semibold">{fmtNumber(t.unidades)}</span> unidades
        </span>
        <span>
          venta recuperada{' '}
          <span className="text-grafito font-semibold">{fmtPrecio(t.venta_recuperada_usd)}</span>
        </span>
        <span>
          costo logístico{' '}
          <span className="text-grafito font-semibold">{fmtPrecio(t.costo_logistico_usd)}</span>
        </span>
      </div>

      {error && <div className="text-[11px] text-red-600 mb-1.5">{error}</div>}

      <div className="flex items-center gap-2">
        <button
          onClick={() => decidir('aprobar')}
          disabled={ocupado}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-dn-600 hover:bg-dn-700 text-white text-[11px] font-semibold transition-colors disabled:opacity-50"
        >
          <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
          {ocupado ? 'Despachando…' : 'Aprobar traslado'}
        </button>
        <button
          onClick={() => decidir('descartar')}
          disabled={ocupado}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-marco text-humo hover:text-grafito hover:border-humo text-[11px] transition-colors disabled:opacity-50"
        >
          <X className="w-3.5 h-3.5" strokeWidth={2} />
          Descartar
        </button>
      </div>
    </li>
  );
}

/** Fila compacta: ya se decidió, así que solo interesa qué se movió y a dónde. */
function TrasladoAprobado({
  t,
  onHover,
  onEnfocar,
}: {
  t: Traslado;
  onHover?: (t: Traslado | null) => void;
  onEnfocar?: (t: Traslado) => void;
}) {
  return (
    <li
      className="px-4 py-2.5 bg-emerald-50/40 hover:bg-emerald-50 transition-colors cursor-pointer"
      onMouseEnter={() => onHover?.(t)}
      onMouseLeave={() => onHover?.(null)}
      onClick={() => onEnfocar?.(t)}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[12px] font-semibold text-tinta truncate">
            {t.producto ?? t.sku}
          </div>
          <div className="text-[10.5px] text-grafito truncate">
            {bandera(t.country_code)} {t.origen_nombre} → {t.destino_nombre}
          </div>
          <div className="text-[10px] text-emerald-800 mt-0.5">
            <Check className="w-3 h-3 inline -mt-px" strokeWidth={2.5} />{' '}
            {t.decidido_por ?? 'aprobado'}
            {t.decidido_en && <span className="text-humo"> · {relTime(t.decidido_en)}</span>}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[15px] font-bold tabular-nums text-emerald-700 leading-none">
            {fmtUSD(t.ganancia_neta_usd)}
          </div>
          <div className="text-[10px] text-humo tabular-nums mt-0.5">
            {fmtNumber(t.unidades)} u · {fmtDecimal(t.distancia_km)} km
          </div>
        </div>
      </div>
    </li>
  );
}

function Ruta({ t, onEnfocar }: { t: Traslado; onEnfocar?: (t: Traslado) => void }) {
  return (
    <div className="flex items-center gap-2 text-[11px] mb-2">
      <div className="flex-1 min-w-0 rounded-md border border-marco bg-nieve px-2 py-1">
        <div className="text-[9px] uppercase tracking-widest text-humo">sobrestock</div>
        <div className="text-grafito truncate">
          {bandera(t.country_code)} {t.origen_nombre}
        </div>
        <div className="text-[10px] text-humo truncate">{t.origen_ciudad}</div>
      </div>
      <button
        onClick={() => onEnfocar?.(t)}
        title="ver la ruta en el mapa"
        className="flex flex-col items-center shrink-0 px-1 text-humo hover:text-dn-600 transition-colors"
      >
        <Crosshair className="w-3.5 h-3.5" strokeWidth={2} />
        <span className="text-[10px] tabular-nums whitespace-nowrap">
          {fmtDecimal(t.distancia_km)} km
        </span>
        <ArrowRight className="w-3 h-3" strokeWidth={2.5} />
      </button>
      <div className="flex-1 min-w-0 rounded-md border border-red-500/30 bg-red-50 px-2 py-1">
        <div className="text-[9px] uppercase tracking-widest text-red-600">quiebre</div>
        <div className="text-grafito truncate">{t.destino_nombre}</div>
        <div className="text-[10px] text-humo truncate">{t.destino_ciudad}</div>
      </div>
    </div>
  );
}
