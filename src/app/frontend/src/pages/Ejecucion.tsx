import { useEffect, useMemo, useState } from 'react';
import EjecucionChart from '../components/EjecucionChart';
import KpiCard from '../components/KpiCard';
import MetasWidget from '../components/MetasWidget';
import TopActionBanner from '../components/TopActionBanner';
import VisitaTickerRow, { LeyendaTicker } from '../components/VisitaTickerRow';
import { api, Kpis, PaisCorte, Recomendacion, Visita, VisitasTimeline } from '../lib/api';
import { bandera, fmtDecimal, fmtNumber } from '../lib/format';
import {
  AccionAprobada,
  cargarAcciones,
  estimarImpacto,
  guardarAcciones,
} from '../lib/impact';

export default function Ejecucion() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [visitas, setVisitas] = useState<Visita[]>([]);
  const [paises, setPaises] = useState<PaisCorte[]>([]);
  const [timeline, setTimeline] = useState<VisitasTimeline | null>(null);
  const [recs, setRecs] = useState<Recomendacion[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Las acciones despachadas viven en localStorage para sobrevivir un refresh
  // en medio de la demo.
  const [acciones, setAcciones] = useState<AccionAprobada[]>(() => cargarAcciones());

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [k, p, t, rs] = await Promise.all([
          api.kpis(),
          api.visitasPorPais(),
          api.visitasTimeline(30),
          api.recomendaciones(undefined, 50),
        ]);
        if (!active) return;
        setKpis(k);
        setPaises(p);
        setTimeline(t);
        setRecs(rs);
        setError(null);
      } catch (e: any) {
        if (active) setError(e?.message ?? String(e));
      }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  // El ticker va por su cuenta y más rápido que el resto del tablero. Los KPIs y
  // las series se mueven en minutos y no ganan nada con refrescarse seguido; el
  // flujo de lecturas sí, y el backend lo revela a ritmo de reloj, así que cada
  // consulta trae las que sincronizaron desde la anterior.
  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const v = await api.visitasRecientes(200);
        if (active) setVisitas(v);
      } catch {
        /* un hipo del ticker no debe borrar el feed en pantalla */
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const recDestacada = useMemo<Recomendacion | null>(
    () =>
      recs.find(
        (r) => r.status === 'pending' && (r.severity === 'high' || r.severity === 'critical'),
      ) ?? null,
    [recs],
  );

  // Conciliamos lo guardado localmente con el servidor: solo sobreviven las
  // acciones que siguen aprobadas allá y que se despacharon en la última hora.
  useEffect(() => {
    const haceUnaHora = Date.now() - 3600_000;
    const aprobadasServidor = new Set(
      recs.filter((r) => r.status === 'approved').map((r) => r.id),
    );
    setAcciones((cur) => {
      const filtradas = cur.filter(
        (a) =>
          new Date(a.aprobada_en).getTime() > haceUnaHora && aprobadasServidor.has(a.rec_id),
      );
      if (filtradas.length !== cur.length) guardarAcciones(filtradas);
      return filtradas;
    });
  }, [recs]);

  function onDecidida(rec: Recomendacion, action: 'APPROVED' | 'REJECTED') {
    if (action !== 'APPROVED') return;
    const impacto = estimarImpacto(rec, kpis);
    const sa = (rec.suggested_action as any) ?? {};
    const entrada: AccionAprobada = {
      rec_id: rec.id,
      aprobada_en: new Date().toISOString(),
      agent_name: rec.agent_name,
      title: rec.title,
      action_type: sa.type ?? 'other',
      impacto_pp: impacto.pp,
      impacto_metrica: impacto.metrica,
      pdv: impacto.pdv,
      esProtectivo: !!impacto.esProtectivo,
    };
    setAcciones((cur) => {
      const next = [...cur, entrada];
      guardarAcciones(next);
      return next;
    });
  }

  const puntos = timeline?.puntos ?? [];
  const ultimos12 = puntos.slice(-12);
  const sparkDisp = ultimos12.map((p) => p.disponibilidad_pct);
  const sparkEjec = ultimos12.map((p) => p.ejecucion_pct);
  const peorPais = paises.length ? paises[0] : null;

  return (
    <div className="p-6 space-y-5">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-600 text-sm rounded p-3">
          Error al consultar Unity Catalog: <span className="font-mono">{error}</span>
        </div>
      )}

      <TopActionBanner rec={recDestacada} kpis={kpis} onDecidida={onDecidida} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Disponibilidad en anaquel"
          value={kpis?.disponibilidad_pct ?? null}
          format={(n) => `${fmtDecimal(n)}%`}
          sublabel={
            kpis
              ? `${fmtNumber(kpis.observaciones)} lecturas · ${fmtNumber(kpis.quiebres)} quiebres`
              : 'cargando…'
          }
          accent
          sparkline={sparkDisp}
        />
        <KpiCard
          label="Ejecución perfecta"
          value={kpis?.ejecucion_pct ?? null}
          format={(n) => `${fmtDecimal(n)}%`}
          sublabel={kpis ? `planograma ${fmtDecimal(kpis.planograma_pct)}%` : ''}
          sparkline={sparkEjec}
        />
        <KpiCard
          label="Share of shelf"
          value={kpis?.sos_cliente_pct ?? null}
          format={(n) => `${fmtDecimal(n)}%`}
          sublabel="caras del cliente sobre el total medido"
          flavor="good"
        />
        <KpiCard
          label="Cobertura de la red"
          value={kpis?.pdv_visitados ?? null}
          format={(n) => fmtNumber(n)}
          sublabel={
            kpis
              ? `PDV medidos en ${kpis.paises} países · ${fmtDecimal(kpis.obs_por_min)} lecturas/min`
              : ''
          }
        />
      </div>

      <MetasWidget />

      <EjecucionChart anotaciones={acciones} />

      <div className="grid lg:grid-cols-2 gap-4">
        <section className="bg-white border border-marco rounded-lg overflow-hidden flex flex-col">
          <header className="flex items-center justify-between px-4 py-3 border-b border-marco">
            <div>
              <h2 className="text-sm uppercase tracking-widest text-grafito font-semibold">
                Lecturas de anaquel en vivo
              </h2>
              <p className="text-[11px] text-humo">
                últimas {visitas.length} lecturas · ~2 por segundo · sincronizan del campo
                con ~1 min de rezago
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse-slow" />
              streaming
            </span>
          </header>
          <div className="flex-1 max-h-[480px] overflow-y-auto">
            {visitas.length === 0 && (
              <div className="text-center text-humo text-sm py-12">
                Sin lecturas por ahora.
              </div>
            )}
            {/* La clave lleva el SKU: una visita produce una lectura por producto y
                con solo `visita_id` se repetía en ~9 filas, así que React reusaba
                nodos entre lecturas distintas. */}
            {visitas.map((v) => (
              <VisitaTickerRow key={`${v.visita_id}-${v.sku}`} visita={v} />
            ))}
          </div>
          <LeyendaTicker />
        </section>

        <section className="bg-white border border-marco rounded-lg overflow-hidden flex flex-col">
          <header className="flex items-center justify-between px-4 py-3 border-b border-marco">
            <div>
              <h2 className="text-sm uppercase tracking-widest text-grafito font-semibold">
                Ejecución por país
              </h2>
              <p className="text-[11px] text-humo">
                de menor a mayor · moderno vs tradicional
              </p>
            </div>
            {peorPais && (
              <span className="text-[11px] text-red-600 bg-red-500/10 border border-red-500/30 rounded-full px-2 py-0.5">
                foco: {peorPais.pais}
              </span>
            )}
          </header>
          <div className="p-4 space-y-3 flex-1">
            {paises.length === 0 && (
              <div className="text-center text-humo text-sm py-12">
                Sin datos por país por ahora.
              </div>
            )}
            {paises.map((p) => (
              <div key={p.country_code} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-grafito inline-flex items-center gap-1.5">
                    <span>{bandera(p.country_code)}</span>
                    <span className="font-medium">{p.pais}</span>
                    <span className="text-humo">{fmtNumber(p.pdv)} PDV</span>
                  </span>
                  <span className="font-mono tabular-nums text-dn-600">
                    {fmtDecimal(p.ejecucion_pct)}%
                    <span className="text-humo ml-2">
                      SOS {fmtDecimal(p.sos_cliente_pct)}%
                    </span>
                  </span>
                </div>
                <div className="h-2 bg-nieve rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-dn-500/70 to-dn-400/70 rounded-full transition-all duration-700"
                    style={{ width: `${Math.min(100, p.ejecucion_pct)}%` }}
                  />
                </div>
                <div className="flex gap-4 text-[10px] text-humo tabular-nums">
                  <span>moderno {fmtDecimal(p.ejecucion_moderno_pct)}%</span>
                  <span>tradicional {fmtDecimal(p.ejecucion_tradicional_pct)}%</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
