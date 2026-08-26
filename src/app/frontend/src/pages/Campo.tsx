import {
  ArrowUpRight, Database, Loader2, MapPin, Pause, PackageCheck, Play, Radar, Sparkles,
  Target, Timer, X, Zap,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import {
  AccionSugerida,
  api,
  EstadoSugerencia,
  FlujoCampo,
  LakebaseImpacto,
  LakebaseStats,
  LakebaseStatus,
  PdvPerfil,
  SugerenciaDetalle,
  SugerenciaReciente,
  SugerirResult,
} from '../lib/api';
import { bandera, fmtDecimal, fmtNumber, fmtUSD, fmtUSDCompacto, relTime } from '../lib/format';

const CANALES = ['Moderno', 'Tradicional', 'Conveniencia', 'Mayorista'];

const ACCION_LABEL: Record<AccionSugerida['tipo_accion'], string> = {
  reponer: 'Reponer',
  corregir_planograma: 'Corregir planograma',
  ampliar_espacio: 'Ampliar espacio',
};

const ACCION_STYLE: Record<AccionSugerida['tipo_accion'], string> = {
  reponer: 'border-red-500/40 bg-red-500/10 text-red-600',
  corregir_planograma: 'border-orange-500/40 bg-orange-500/10 text-orange-600',
  ampliar_espacio: 'border-dn-400/40 bg-dn-400/10 text-dn-600',
};

export default function Campo() {
  const [status, setStatus] = useState<LakebaseStatus | null>(null);
  const [stats, setStats] = useState<LakebaseStats | null>(null);
  const [impacto, setImpacto] = useState<LakebaseImpacto | null>(null);
  const [pdv, setPdv] = useState<PdvPerfil[]>([]);
  const [filtro, setFiltro] = useState({ q: '', canal: '' });
  const [elegido, setElegido] = useState<PdvPerfil | null>(null);
  const [categoria, setCategoria] = useState('');
  const [resultado, setResultado] = useState<SugerirResult | null>(null);
  const [sugiriendo, setSugiriendo] = useState(false);
  const [recientes, setRecientes] = useState<SugerenciaReciente[]>([]);
  const [detalle, setDetalle] = useState<SugerenciaDetalle | null>(null);
  const [detalleCargando, setDetalleCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sinConfigurar, setSinConfigurar] = useState(false);
  const [flujo, setFlujo] = useState<FlujoCampo | null>(null);
  const [ritmo, setRitmo] = useState(6); // visitas por minuto simuladas
  const [cambiandoFlujo, setCambiandoFlujo] = useState(false);

  const cargarTableros = useCallback(async () => {
    try {
      const [s, st, rec, imp, fl] = await Promise.all([
        api.lakebaseStatus(),
        api.lakebaseStats(),
        api.lakebaseRecientes(20),
        api.lakebaseImpacto(),
        api.lakebaseFlujo(),
      ]);
      setStatus(s);
      setStats(st);
      setRecientes(rec);
      setImpacto(imp);
      setFlujo(fl);
      if (fl.activo) setRitmo(fl.ritmo_por_min);
      setError(null);
      setSinConfigurar(false);
    } catch (e: any) {
      const msg = e?.message ?? String(e);
      if (/\b503\b/.test(msg) || /configurad/i.test(msg)) {
        setSinConfigurar(true);
        setError(null);
      } else {
        setError(msg);
      }
    }
  }, []);

  const cargarPdv = useCallback(async () => {
    try {
      const list = await api.lakebasePdv({
        q: filtro.q || undefined,
        canal: filtro.canal || undefined,
        limit: 30,
      });
      setPdv(list);
    } catch (e: any) {
      if (!/\b503\b/.test(e?.message ?? '')) setError(e?.message ?? String(e));
    }
  }, [filtro.q, filtro.canal]);

  useEffect(() => {
    cargarTableros();
    const id = setInterval(cargarTableros, 2500);
    return () => clearInterval(id);
  }, [cargarTableros]);

  useEffect(() => {
    cargarPdv();
  }, [cargarPdv]);

  // La jornada la mueve un hilo del servidor, no esta pestaña. Antes vivía en un
  // setInterval acá y se congelaba al navegar a otra vista — justo cuando el
  // presentador recorre el resto del tablero y quiere volver a un feed con vida.
  const cambiarFlujo = async (activo: boolean, porMin = ritmo) => {
    setCambiandoFlujo(true);
    try {
      setFlujo(await api.lakebaseFlujoControl(activo, porMin));
      setTimeout(cargarTableros, 800);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setCambiandoFlujo(false);
    }
  };

  function elegirPdv(p: PdvPerfil) {
    setElegido(p);
    setResultado(null);
    setCategoria('');
  }

  async function pedirSugerencia() {
    if (!elegido) return;
    setSugiriendo(true);
    setResultado(null);
    try {
      const r = await api.lakebaseSugerir({
        store_id: elegido.store_id,
        categoria: categoria || undefined,
        n: 4,
      });
      setResultado(r);
      setTimeout(cargarTableros, 600);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setSugiriendo(false);
    }
  }

  async function abrirDetalle(id: number) {
    setDetalleCargando(true);
    setDetalle(null);
    try {
      setDetalle(await api.lakebaseSugerencia(id));
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setDetalleCargando(false);
    }
  }

  if (sinConfigurar) {
    return (
      <div className="px-6 py-16 max-w-2xl mx-auto text-center">
        <div className="text-[10px] uppercase tracking-[0.22em] text-dn-600 mb-2 flex items-center justify-center gap-2">
          <Database className="w-3.5 h-3.5" /> Copiloto de campo · Lakebase
        </div>
        <h1 className="text-2xl font-semibold text-tinta mb-3">
          Lakebase no está configurado en este app
        </h1>
        <p className="text-grafito text-sm leading-relaxed">
          El copiloto de campo usa <strong>Lakebase (Postgres)</strong> para servir el plan de la
          visita en menos de 100 ms. Si ves este mensaje, el app se desplegó sin{' '}
          <span className="font-mono text-dn-600">LAKEBASE_HOST</span> — suele pasar si se hizo un{' '}
          <span className="font-mono text-dn-600">bundle deploy</span> manual sin las variables que
          pasa <span className="font-mono text-dn-600">instalar.sh</span>.
        </p>
        <p className="text-grafito text-sm leading-relaxed mt-3">
          Vuelve a correr{' '}
          <span className="font-mono text-dn-600">./instalar.sh</span> (es idempotente) o despliega
          con{' '}
          <span className="font-mono text-dn-600">--var lakebase_host=&lt;host de la instancia&gt;</span>.
          Ver <span className="font-mono text-dn-600">docs/LAKEBASE.md</span>.
        </p>
        <p className="text-humo text-xs mt-6">
          Las demás pestañas funcionan normalmente sin Lakebase.
        </p>
      </div>
    );
  }

  return (
    <div className="px-6 py-6 space-y-6 max-w-[1600px] mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-dn-600 mb-1 flex items-center gap-2">
            <Radar className="w-3.5 h-3.5" /> Copiloto de campo
          </div>
          <h1 className="text-2xl font-semibold text-tinta">
            El plan de la visita, servido en el celular
          </h1>
          <p className="text-grafito text-sm mt-1 max-w-3xl">
            El mercaderista abre la app frente al anaquel y el copiloto ya sabe qué reponer, qué
            planograma corregir y dónde pelear espacio. El perfil del PDV vive en Lakebase, así que
            la respuesta llega antes de que termine de caminar el pasillo.
          </p>
        </div>
        {status && (
          <div className="text-right text-[10px] text-humo font-mono leading-relaxed">
            <div>
              <span className="text-dn-600">●</span> {status.host?.split('.')[0]}
            </div>
            <div>
              {status.database} · {status.schema}
            </div>
            <div>{status.postgres_version}</div>
          </div>
        )}
      </header>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-red-600 text-sm">
          ⚠ {error}
        </div>
      )}

      <section className="rounded-xl border border-emerald-500/40 bg-gradient-to-br from-emerald-500/10 via-dn-500/5 to-nieve overflow-hidden">
        <div className="px-5 py-3 border-b border-emerald-500/30 flex items-center justify-between">
          <div>
            <h2 className="text-[11px] uppercase tracking-[0.22em] text-emerald-600 font-semibold flex items-center gap-2">
              <Target className="w-3.5 h-3.5" /> Venta en riesgo recuperable · estimado
            </h2>
            <p className="text-[10.5px] text-humo mt-0.5">
              {impacto?.supuesto ??
                'aplica la tasa de ejecución en campo sobre el valor identificado en las sugerencias servidas'}
            </p>
          </div>
          <span className="text-[10px] text-humo">actualiza cada 2.5s</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-0">
          <HeroKpi
            Icon={PackageCheck}
            label="quiebre identificado (24h)"
            value={fmtUSDCompacto(impacto?.impacto_identificado_24h_usd ?? 0)}
            sub={`${fmtNumber(impacto?.sugerencias_24h ?? 0)} planes de visita servidos`}
            accent="text-emerald-600"
          />
          <HeroKpi
            Icon={ArrowUpRight}
            label="recuperación estimada"
            value={fmtUSDCompacto(impacto?.recuperacion_estimada_usd ?? 0)}
            sub={`vs ${fmtUSDCompacto(impacto?.recuperacion_base_usd ?? 0)} sin priorización`}
            accent="text-emerald-600"
          />
          <HeroKpi
            Icon={Sparkles}
            label="uplift sobre la ruta ciega"
            value={`+${fmtUSDCompacto(impacto?.uplift_usd ?? 0)}`}
            sub={
              impacto?.tasa_ejecucion_campo_pct == null
                ? 'esperando la primera visita cerrada para medir la tasa'
                : `ejecución medida ${fmtDecimal(impacto.tasa_ejecucion_campo_pct)}% vs ${fmtDecimal(impacto.tasa_base_pct)}% de línea base`
            }
            accent="text-dn-600"
          />
          <HeroKpi
            Icon={MapPin}
            label="PDV atendidos"
            value={fmtNumber(impacto?.pdv_atendidos ?? 0)}
            sub={`${fmtNumber(impacto?.sugerencias_5min ?? 0)} planes en los últimos 5 min`}
            accent="text-tinta"
          />
        </div>
      </section>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi
          label="perfiles de PDV"
          value={fmtNumber(status?.counts.pdv_perfiles ?? 0)}
          Icon={MapPin}
          accent="text-tinta"
        />
        <Kpi
          label="planes servidos"
          value={fmtNumber(status?.counts.sugerencias_servidas ?? 0)}
          Icon={Sparkles}
          accent="text-dn-600"
        />
        <Kpi
          label="latencia p50"
          value={stats?.p50_ms != null ? `${stats.p50_ms} ms` : '—'}
          Icon={Timer}
          accent={latenciaColor(stats?.p50_ms)}
        />
        <Kpi
          label="latencia p95"
          value={stats?.p95_ms != null ? `${stats.p95_ms} ms` : '—'}
          Icon={Zap}
          accent={latenciaColor(stats?.p95_ms)}
        />
      </div>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-marco bg-white overflow-hidden">
          <header className="px-5 py-3 border-b border-marco flex items-start justify-between gap-3">
            <div>
              <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
                Jornada en vivo
              </h2>
              <p className="text-[11px] text-humo mt-0.5">
                cada línea es una visita: el plan llega en milisegundos y vuelve cerrado con
                lo que el mercaderista corrigió
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <select
                value={ritmo}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setRitmo(v);
                  if (flujo?.activo) cambiarFlujo(true, v);
                }}
                className="bg-nieve border border-marco rounded px-2 py-1 text-[11px] text-tinta"
                title="visitas por minuto"
              >
                <option value={2}>2/min · ruta lenta</option>
                <option value={6}>6/min · jornada normal</option>
                <option value={15}>15/min · cierre de mes</option>
                <option value={30}>30/min · censo nacional</option>
              </select>
              <button
                onClick={() => cambiarFlujo(!flujo?.activo)}
                disabled={cambiandoFlujo}
                className={[
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11.5px] font-semibold border transition-colors disabled:opacity-50',
                  flujo?.activo
                    ? 'border-red-400/50 bg-red-500/15 text-red-700 hover:bg-red-500/25'
                    : 'border-emerald-400/50 bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/25',
                ].join(' ')}
              >
                {cambiandoFlujo ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : flujo?.activo ? (
                  <Pause className="w-3.5 h-3.5" />
                ) : (
                  <Play className="w-3.5 h-3.5" />
                )}
                {flujo?.activo ? 'pausar jornada' : 'arrancar jornada'}
              </button>
            </div>
          </header>
          {flujo?.activo && (
            <div className="px-5 py-1.5 bg-emerald-500/10 border-b border-emerald-500/30 text-[10.5px] text-emerald-600 flex items-center gap-2 flex-wrap">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              ~{flujo.ritmo_por_min} visitas/min · {fmtNumber(flujo.servidas)} planes servidos y{' '}
              {fmtNumber(flujo.cerradas)} visitas cerradas desde el arranque
              {flujo.errores > 0 && (
                <span className="text-orange-600">· {flujo.errores} errores</span>
              )}
              <span className="text-humo ml-auto">corre en el servidor</span>
            </div>
          )}
          {!flujo?.activo && (
            <div className="px-5 py-1.5 bg-nieve border-b border-marco text-[10.5px] text-humo">
              Jornada pausada. El hilo vive en el servidor, así que sigue corriendo aunque
              cambies de pestaña o cierres el navegador.
            </div>
          )}
          <div className="p-4 max-h-[420px] overflow-y-auto">
            {recientes.length === 0 ? (
              <p className="text-[11.5px] text-humo italic">
                Sin actividad todavía. Arranca la jornada o pide un plan abajo.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {recientes.map((r) => (
                  <FilaVisita key={r.id} r={r} onAbrir={() => abrirDetalle(r.id)} />
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-marco bg-white overflow-hidden">
          <header className="px-5 py-3 border-b border-marco">
            <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
              SLA de latencia
            </h2>
            <p className="text-[11px] text-humo mt-0.5">
              presupuesto de respuesta en anaquel &lt;100 ms · ventana móvil de{' '}
              {stats?.window_min ?? 30} min
            </p>
          </header>
          <div className="p-5">
            {stats && stats.n > 0 ? (
              <div className="space-y-3 text-[12px]">
                <StatLine label="mediana (p50)" target={50} actual={stats.p50_ms} />
                <StatLine label="cola 95 (p95)" target={100} actual={stats.p95_ms} />
                <StatLine label="cola 99 (p99)" target={200} actual={stats.p99_ms} />
                <div className="text-[11px] text-humo mt-3">
                  {fmtNumber(stats.n)} llamadas · min {stats.min_ms}ms · max {stats.max_ms}ms ·
                  media {stats.mean_ms}ms
                </div>
              </div>
            ) : (
              <p className="text-humo text-[11.5px] italic">
                Sirve algunos planes para poblar las métricas.
              </p>
            )}
          </div>
        </div>
      </section>

      {impacto && <CicloCerrado impacto={impacto} />}

      <section className="rounded-xl border border-marco bg-white overflow-hidden">
        <header className="px-5 py-3 border-b border-marco">
          <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
            <Radar className="w-3.5 h-3.5 text-dn-600" />
            Simulador de visita
          </h2>
          <p className="text-[11px] text-humo mt-0.5">
            elige el punto de venta · fija la categoría a trabajar (opcional) · recibe el plan
          </p>
        </header>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-0">
          <div className="p-4 border-r border-marco max-h-[480px] overflow-y-auto">
            <div className="flex items-center gap-2 mb-3">
              <input
                type="text"
                value={filtro.q}
                onChange={(e) => setFiltro((f) => ({ ...f, q: e.target.value }))}
                placeholder="buscar PDV, cadena o ciudad..."
                className="flex-1 bg-nieve border border-marco rounded px-2.5 py-1.5 text-[12px] text-tinta placeholder:text-humo focus:outline-none focus:ring-1 focus:ring-dn-400/40"
              />
              <select
                value={filtro.canal}
                onChange={(e) => setFiltro((f) => ({ ...f, canal: e.target.value }))}
                className="bg-nieve border border-marco rounded px-2 py-1.5 text-[12px] text-tinta"
              >
                <option value="">todos los canales</option>
                {CANALES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <ul className="space-y-1">
              {pdv.map((p) => (
                <li key={p.store_id}>
                  <button
                    onClick={() => elegirPdv(p)}
                    className={[
                      'w-full text-left px-2.5 py-1.5 rounded text-[11.5px] transition-colors',
                      elegido?.store_id === p.store_id
                        ? 'border border-dn-400/60 bg-dn-400/10 text-tinta'
                        : 'border border-marco bg-nieve hover:bg-white text-tinta',
                    ].join(' ')}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold truncate">
                        {bandera(p.country_code)} {p.nombre}
                      </span>
                      <span className="text-[10px] text-humo">{p.store_id}</span>
                    </div>
                    <div className="text-[10px] text-humo mt-0.5">
                      {p.canal} · {p.cadena} · {p.ciudad} · riesgo de quiebre{' '}
                      {(p.riesgo_quiebre * 100).toFixed(0)}%
                    </div>
                  </button>
                </li>
              ))}
              {pdv.length === 0 && (
                <li className="text-humo text-[11.5px] italic">ningún PDV encontrado</li>
              )}
            </ul>
          </div>

          <div className="p-5 bg-nieve">
            {!elegido && (
              <div className="text-humo text-[12px] italic">
                ← elige un punto de venta para empezar
              </div>
            )}
            {elegido && (
              <>
                <div className="min-w-0">
                  <div className="text-[10px] uppercase tracking-wider text-humo">
                    Punto de venta seleccionado
                  </div>
                  <div className="text-lg font-semibold text-tinta truncate">
                    {bandera(elegido.country_code)} {elegido.nombre}
                  </div>
                  <div className="text-[11px] text-grafito mt-0.5 flex gap-2 flex-wrap">
                    <span>{elegido.store_id}</span>
                    <span>·</span>
                    <span>
                      {elegido.canal} · {elegido.cadena}
                    </span>
                    <span>·</span>
                    <span>{elegido.mercaderista ?? 'sin mercaderista asignado'}</span>
                    <span>·</span>
                    <span>hist. disp {fmtDecimal(elegido.disponibilidad_hist)}%</span>
                  </div>
                </div>

                <div className="mt-4 rounded-lg border border-marco bg-nieve px-3 py-2.5">
                  <div className="text-[10px] uppercase tracking-wider text-humo mb-1.5 flex items-center gap-1.5">
                    <PackageCheck className="w-3 h-3" /> Categoría a trabajar en esta visita
                    (opcional)
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={categoria}
                      onChange={(e) => setCategoria(e.target.value)}
                      className="flex-1 bg-white border border-marco rounded px-2.5 py-1.5 text-[12px] text-tinta"
                    >
                      <option value="">dejar que el copiloto decida por el perfil</option>
                      {elegido.categorias_prioritarias.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={pedirSugerencia}
                      disabled={sugiriendo}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-semibold border border-dn-400/40 bg-dn-400/10 hover:bg-dn-400/20 text-tinta disabled:opacity-60"
                    >
                      {sugiriendo ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Sparkles className="w-3.5 h-3.5" />
                      )}
                      pedir plan
                    </button>
                  </div>
                  <div className="text-[10.5px] text-humo italic mt-1.5">
                    {categoria
                      ? `El copiloto priorizará ${categoria} para este PDV.`
                      : 'Sin categoría fija, el copiloto elige la de mayor riesgo según el histórico del PDV.'}
                  </div>
                </div>

                {resultado && (
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-3 text-[12px] flex-wrap">
                      <span className="px-2 py-1 rounded font-mono bg-dn-400/15 text-dn-700 font-semibold">
                        servido en {resultado.latency_ms} ms
                      </span>
                      <span className="text-humo">
                        plan #{resultado.sugerencia_id} · {relTime(resultado.served_at ?? undefined)}
                      </span>
                      <span className="text-emerald-600 font-semibold tabular-nums ml-auto">
                        {fmtUSD(resultado.impacto_usd)} en juego
                      </span>
                    </div>
                    <EscenarioBox escenario={resultado.escenario} />
                    <div className="text-[11px] text-grafito italic">{resultado.rationale}</div>
                    <div className="text-[10px] uppercase tracking-wider text-humo">
                      Orden de trabajo · lo más urgente primero
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {resultado.acciones.map((a, i) => (
                        <AccionCard key={a.sku} accion={a} rank={i + 1} />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </section>

      {(detalle || detalleCargando) && (
        <DetalleModal
          detalle={detalle}
          cargando={detalleCargando}
          onClose={() => {
            setDetalle(null);
            setDetalleCargando(false);
          }}
        />
      )}
    </div>
  );
}

// ---- subcomponentes ------------------------------------------------------

const ESTADO_META: Record<
  EstadoSugerencia,
  { texto: string; clase: string; ayuda: string }
> = {
  servida: {
    texto: 'en visita',
    clase: 'bg-dn-400/15 text-dn-700 border-dn-400/40',
    ayuda: 'el plan llegó al celular y el mercaderista está en el pasillo',
  },
  ejecutada: {
    texto: 'ejecutada',
    clase: 'bg-emerald-500/15 text-emerald-700 border-emerald-500/40',
    ayuda: 'corrigió todo lo que el copiloto pidió',
  },
  parcial: {
    texto: 'parcial',
    clase: 'bg-amber-500/15 text-amber-700 border-amber-500/40',
    ayuda: 'corrigió parte del plan: lo normal cuando falta producto en bodega',
  },
  omitida: {
    texto: 'omitida',
    clase: 'bg-red-500/10 text-red-700 border-red-500/30',
    ayuda: 'cerró la visita sin ejecutar nada del plan',
  },
};

/**
 * Una visita del feed. Muestra las dos mitades del ciclo en la misma línea: la
 * latencia con la que llegó el plan y qué se hizo con él, que es lo único que
 * al final convierte una recomendación en plata.
 */
function FilaVisita({ r, onAbrir }: { r: SugerenciaReciente; onAbrir: () => void }) {
  const lento = r.latency_ms >= 100;
  const meta = ESTADO_META[r.estado] ?? ESTADO_META.servida;
  const cerrada = r.estado !== 'servida';

  return (
    <li>
      <button
        onClick={onAbrir}
        className="w-full px-2.5 py-1.5 rounded border border-marco bg-nieve hover:bg-white text-[11.5px] text-left transition-colors"
      >
        <div className="flex items-center gap-2">
          <span
            className={[
              'px-1.5 py-0.5 rounded font-mono text-[10px] tabular-nums shrink-0',
              lento ? 'bg-red-500/20 text-red-600' : 'bg-dn-400/15 text-dn-600',
            ].join(' ')}
          >
            {r.latency_ms}ms
          </span>
          <div className="min-w-0 flex-1 truncate">
            <span className="text-tinta font-semibold">{r.nombre}</span>
            <span className="text-humo"> · {r.cadena} · {r.ciudad}</span>
            {r.categoria_foco && <span className="text-dn-600"> · {r.categoria_foco}</span>}
          </div>
          <span
            title={meta.ayuda}
            className={`px-1.5 py-0.5 rounded border text-[9.5px] font-bold uppercase tracking-wider shrink-0 ${meta.clase}`}
          >
            {meta.texto}
          </span>
          <span className="text-humo text-[10px] shrink-0 w-14 text-right">
            {relTime((cerrada ? r.ejecutado_at : r.served_at) ?? undefined)}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-1 pl-[46px] text-[10px]">
          <span className="text-grafito truncate flex-1">
            {r.skus.slice(0, 3).join(', ')}
            {r.skus.length > 3 && ` +${r.skus.length - 3}`}
          </span>
          {cerrada ? (
            <span className="shrink-0 tabular-nums">
              <span className="text-humo">
                {r.skus_ejecutados.length}/{r.skus.length} corregidos ·{' '}
              </span>
              <span
                className={
                  r.impacto_ejecutado_usd > 0 ? 'text-emerald-600 font-semibold' : 'text-humo'
                }
              >
                {fmtUSDCompacto(r.impacto_ejecutado_usd)}
              </span>
              <span className="text-humo"> de {fmtUSDCompacto(r.impacto_usd)}</span>
            </span>
          ) : (
            <span className="shrink-0 text-humo tabular-nums">
              {fmtUSDCompacto(r.impacto_usd)} en juego
            </span>
          )}
        </div>
      </button>
    </li>
  );
}

/** Cierre del ciclo: de lo que el copiloto pidió, cuánto se hizo de verdad. */
function CicloCerrado({ impacto }: { impacto: LakebaseImpacto }) {
  const cerradas = impacto.visitas_cerradas;
  const tasa = impacto.tasa_ejecucion_campo_pct;
  const partes: Array<{ label: string; n: number; clase: string }> = [
    { label: 'ejecutadas', n: impacto.ejecutadas, clase: 'bg-emerald-500' },
    { label: 'parciales', n: impacto.parciales, clase: 'bg-amber-400' },
    { label: 'omitidas', n: impacto.omitidas, clase: 'bg-red-400' },
  ];

  return (
    <div className="rounded-xl border border-marco bg-white overflow-hidden">
      <header className="px-5 py-3 border-b border-marco">
        <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
          <PackageCheck className="w-3.5 h-3.5 text-emerald-600" />
          Ciclo cerrado · qué se ejecutó de lo que se sugirió
        </h2>
        <p className="text-[11px] text-humo mt-0.5">
          {cerradas === 0
            ? 'todavía no cierra ninguna visita: sin cierres no hay tasa que medir'
            : `${fmtNumber(cerradas)} visitas cerradas · ${fmtNumber(impacto.visitas_pendientes)} en curso`}
        </p>
      </header>
      <div className="p-5 space-y-4">
        <div className="flex items-end gap-4">
          <div>
            <div className="text-[9.5px] uppercase tracking-wider text-humo">
              tasa de ejecución medida
            </div>
            <div className="text-3xl font-bold tabular-nums text-emerald-600 leading-none">
              {tasa == null ? '—' : `${fmtDecimal(tasa)}%`}
            </div>
          </div>
          <div className="text-[11px] text-humo pb-1">
            contra <strong className="text-grafito">{fmtDecimal(impacto.tasa_base_pct)}%</strong>{' '}
            de la ruta sin priorización
          </div>
        </div>

        {cerradas > 0 && (
          <>
            <div className="h-2.5 rounded-full overflow-hidden flex bg-nieve">
              {partes.map((p) => (
                <div
                  key={p.label}
                  className={p.clase}
                  style={{ width: `${(p.n / cerradas) * 100}%` }}
                  title={`${p.label}: ${p.n}`}
                />
              ))}
            </div>
            <div className="flex gap-4 text-[10.5px]">
              {partes.map((p) => (
                <span key={p.label} className="flex items-center gap-1.5 text-grafito">
                  <span className={`w-2 h-2 rounded-full ${p.clase}`} />
                  {p.label} <span className="tabular-nums text-humo">{fmtNumber(p.n)}</span>
                </span>
              ))}
            </div>
            <div className="text-[11px] text-grafito border-t border-marco pt-3">
              De {fmtUSD(impacto.impacto_cerrado_usd)} sugeridos en visitas ya cerradas, el
              mercaderista corrigió{' '}
              <strong className="text-emerald-600">
                {fmtUSD(impacto.impacto_ejecutado_usd)}
              </strong>
              . Esa división es la tasa de arriba: es una medición del log, no un supuesto.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function HeroKpi({
  Icon,
  label,
  value,
  sub,
  accent,
}: {
  Icon: any;
  label: string;
  value: string;
  sub: string;
  accent: string;
}) {
  return (
    <div className="px-5 py-4 border-r border-marco last:border-r-0">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9.5px] uppercase tracking-wider text-grafito">{label}</span>
        <Icon className={`w-3.5 h-3.5 ${accent}`} strokeWidth={2} />
      </div>
      <div className={`text-2xl font-bold tabular-nums ${accent}`}>{value}</div>
      <div className="text-[10px] text-humo mt-0.5">{sub}</div>
    </div>
  );
}

function Kpi({
  label,
  value,
  Icon,
  accent,
}: {
  label: string;
  value: string;
  Icon: any;
  accent: string;
}) {
  return (
    <div className="rounded-lg border border-marco bg-white px-4 py-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9.5px] uppercase tracking-wider text-humo">{label}</span>
        <Icon className={`w-3.5 h-3.5 ${accent}`} strokeWidth={2} />
      </div>
      <div className={`text-xl font-bold tabular-nums ${accent}`}>{value}</div>
    </div>
  );
}

function EscenarioBox({ escenario }: { escenario: SugerirResult['escenario'] }) {
  const c = escenarioColor(escenario.code);
  return (
    <div className={`rounded-lg border p-2.5 ${c.border} ${c.bg}`}>
      <div className={`text-[10px] uppercase tracking-wider mb-1 ${c.text}`}>
        {escenario.headline}
      </div>
      <div className="text-[11.5px] text-tinta leading-relaxed">{escenario.narrative}</div>
    </div>
  );
}

function AccionCard({ accion, rank }: { accion: AccionSugerida; rank: number }) {
  return (
    <div className="rounded-lg border border-marco bg-white p-3 relative">
      <span className="absolute top-1.5 right-2 text-[9px] font-bold text-humo">#{rank}</span>
      <div className="flex items-start gap-2">
        <span className="text-2xl leading-none">{accion.emoji ?? '📦'}</span>
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-semibold text-tinta truncate">
            {accion.nombre ?? accion.sku}
          </div>
          <div className="text-[10px] text-humo truncate">
            {accion.sku} · {accion.marca ?? '—'}
            {accion.presentacion ? ` · ${accion.presentacion}` : ''}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between mt-2 gap-2">
        <span
          className={`text-[9.5px] font-bold uppercase tracking-wider rounded px-1.5 py-0.5 border ${ACCION_STYLE[accion.tipo_accion]}`}
        >
          {ACCION_LABEL[accion.tipo_accion]}
        </span>
        <span className="text-[11px] text-emerald-600 font-semibold tabular-nums">
          {fmtUSD(accion.impacto_usd)}
        </span>
      </div>
      {accion.en_foco && (
        <div className="text-[9.5px] text-dn-600 mt-1.5">SKU foco del cliente en este PDV</div>
      )}
    </div>
  );
}

function StatLine({ label, target, actual }: { label: string; target: number; actual: number }) {
  const pct = Math.min(100, (actual / (target * 2)) * 100);
  const color =
    actual <= target ? 'bg-emerald-500' : actual <= target * 1.5 ? 'bg-orange-400' : 'bg-red-500';
  return (
    <div>
      <div className="flex items-baseline justify-between text-grafito">
        <span>{label}</span>
        <span className="font-semibold tabular-nums">{actual} ms</span>
      </div>
      <div className="h-1.5 mt-1 rounded-full bg-nieve overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex justify-between text-[9.5px] text-humo mt-0.5">
        <span>objetivo ≤ {target}ms</span>
        <span>{actual > target ? `+${actual - target}ms` : `${target - actual}ms por debajo`}</span>
      </div>
    </div>
  );
}

function latenciaColor(ms?: number): string {
  if (ms == null) return 'text-grafito';
  if (ms <= 50) return 'text-emerald-600';
  if (ms <= 100) return 'text-dn-600';
  return 'text-red-600';
}

function escenarioColor(code?: string) {
  switch (code) {
    case 'critico':
      return { border: 'border-red-500/50', bg: 'bg-red-500/10', text: 'text-red-600' };
    case 'riesgo':
      return { border: 'border-orange-500/50', bg: 'bg-orange-500/10', text: 'text-orange-600' };
    case 'espacio':
      return { border: 'border-dn-400/50', bg: 'bg-dn-400/10', text: 'text-dn-600' };
    default:
      return { border: 'border-marco', bg: 'bg-nieve', text: 'text-grafito' };
  }
}

function DetalleModal({
  detalle,
  cargando,
  onClose,
}: {
  detalle: SugerenciaDetalle | null;
  cargando: boolean;
  onClose: () => void;
}) {
  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-6 pointer-events-none">
        <div className="bg-nieve border border-marco rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto pointer-events-auto shadow-2xl">
          {cargando && (
            <div className="p-10 flex items-center justify-center text-grafito">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> cargando plan...
            </div>
          )}
          {detalle && (
            <>
              <header className="px-5 py-4 border-b border-marco flex items-start justify-between gap-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.22em] text-dn-600 mb-1">
                    Plan #{detalle.id} · {relTime(detalle.served_at ?? undefined)}
                  </div>
                  <h3 className="text-xl font-semibold text-tinta">
                    {bandera(detalle.pdv.country_code)} {detalle.pdv.nombre}
                  </h3>
                  <div className="text-[11px] text-grafito mt-1 flex gap-2 flex-wrap">
                    <span>{detalle.pdv.store_id}</span>
                    <span>·</span>
                    <span>
                      {detalle.pdv.canal} · {detalle.pdv.cadena}
                    </span>
                    <span>·</span>
                    <span>{detalle.pdv.ciudad}</span>
                    <span>·</span>
                    <span>{detalle.pdv.mercaderista ?? 'sin asignar'}</span>
                  </div>
                </div>
                <button onClick={onClose} className="text-humo hover:text-tinta p-1">
                  <X className="w-5 h-5" />
                </button>
              </header>
              <div className="px-5 py-4 space-y-4">
                <EscenarioBox escenario={detalle.escenario} />

                {detalle.rationale && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-humo mb-1">
                      Lectura del copiloto
                    </div>
                    <div className="text-[12px] text-grafito italic">{detalle.rationale}</div>
                  </div>
                )}

                <div>
                  <div className="text-[10px] uppercase tracking-wider text-humo mb-2 flex items-center justify-between">
                    <span>Orden de trabajo servido</span>
                    <span className="px-2 py-0.5 rounded font-mono bg-dn-400/15 text-dn-600 text-[10px]">
                      {detalle.latency_ms}ms
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {detalle.acciones.map((a, i) => (
                      <AccionCard key={a.sku} accion={a} rank={i + 1} />
                    ))}
                  </div>
                </div>

                {detalle.pdv.categorias_prioritarias.length > 0 && (
                  <div className="text-[11px] text-humo">
                    Categorías prioritarias del PDV:{' '}
                    {detalle.pdv.categorias_prioritarias.map((c) => (
                      <span
                        key={c}
                        className="inline-block bg-white text-grafito px-1.5 py-0.5 rounded mr-1"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
