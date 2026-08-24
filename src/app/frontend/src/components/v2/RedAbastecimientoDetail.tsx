import { Check, Clock, Route, TrendingUp } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api, ResumenTraslados, Traslado } from '../../lib/api';
import { fmtDecimal, fmtNumber, fmtUSD } from '../../lib/format';
import TrasladosPanel from './TrasladosPanel';

const CERO = { traslados: 0, ganancia_usd: 0, venta_usd: 0, unidades: 0, km_promedio: 0 };
const VACIO: ResumenTraslados = {
  propuesto: CERO,
  aprobado: CERO,
  descartado: CERO,
  vencido: CERO,
};

export default function RedAbastecimientoDetail() {
  const [traslados, setTraslados] = useState<Traslado[]>([]);
  const [resumen, setResumen] = useState<ResumenTraslados>(VACIO);

  const cargar = useCallback(async () => {
    try {
      const [t, r] = await Promise.all([
        api.traslados({ limit: 40 }),
        api.trasladosResumen().catch(() => VACIO),
      ]);
      setTraslados(t);
      setResumen(r);
    } catch {
      /* mantiene el último dato bueno */
    }
  }, []);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 15000);
    return () => clearInterval(id);
  }, [cargar]);

  const onDecidido = (t: Traslado) => {
    setTraslados((cur) => cur.map((x) => (x.traslado_id === t.traslado_id ? t : x)));
    cargar();
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <section className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tarjeta
          Icon={Clock}
          color="#0D5CAB"
          label="En cola de aprobación"
          valor={fmtNumber(resumen.propuesto.traslados)}
          pie={`${fmtUSD(resumen.propuesto.ganancia_usd)} de ganancia sin decidir`}
        />
        <Tarjeta
          Icon={Check}
          color="#059669"
          label="Aprobados"
          valor={fmtNumber(resumen.aprobado.traslados)}
          pie={`${fmtUSD(resumen.aprobado.ganancia_usd)} puestos en ruta`}
        />
        <Tarjeta
          Icon={TrendingUp}
          color="#0891B2"
          label="Venta recuperada"
          valor={fmtUSD(resumen.propuesto.venta_usd + resumen.aprobado.venta_usd)}
          pie={`${fmtNumber(resumen.propuesto.unidades + resumen.aprobado.unidades)} unidades en juego`}
        />
        <Tarjeta
          Icon={Route}
          color="#7C3AED"
          label="Distancia promedio"
          valor={`${fmtDecimal(resumen.propuesto.km_promedio || resumen.aprobado.km_promedio)} km`}
          pie="dentro de la misma plaza"
        />
      </section>

      <div className="lg:col-span-3">
        <TrasladosPanel traslados={traslados} onDecidido={onDecidido} />
      </div>
    </div>
  );
}

function Tarjeta({
  Icon,
  color,
  label,
  valor,
  pie,
}: {
  Icon: typeof Route;
  color: string;
  label: string;
  valor: string;
  pie: string;
}) {
  return (
    <div className="rounded-xl border border-marco bg-white px-4 py-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className="w-3.5 h-3.5" strokeWidth={2} style={{ color }} />
        <span className="text-[10px] uppercase tracking-widest text-humo">{label}</span>
      </div>
      <div className="text-2xl font-bold tabular-nums text-tinta leading-none">{valor}</div>
      <div className="text-[11px] text-humo mt-1.5">{pie}</div>
    </div>
  );
}
