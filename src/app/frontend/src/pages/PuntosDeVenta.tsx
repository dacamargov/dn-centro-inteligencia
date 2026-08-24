import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import PdvDetailPanel from '../components/PdvDetailPanel';
import AgenteEnContexto from '../components/v2/AgenteEnContexto';
import NetworkStatusHero from '../components/v2/NetworkStatusHero';
import TrasladosPanel from '../components/v2/TrasladosPanel';
import { api, Pdv, Traslado } from '../lib/api';
import { bandera, fmtDecimal, fmtNumber } from '../lib/format';
import { arcoDeTraslado, limitesDeTraslado } from '../lib/rutas';

// Centroamérica + Caribe, la huella real de dichter & neira.
// La red va desde Guatemala hasta el sur de Perú, pasando por el Caribe: el
// encuadre tiene que abarcar Centroamérica, República Dominicana y la región andina.
const REGION_CENTER: [number, number] = [4, -80];
const REGION_ZOOM = 4;
const REGION_BOUNDS: L.LatLngBoundsExpression = [
  [-20, -95],
  [25, -62],
];

const CATEGORIAS = [
  'Bebidas Calientes',
  'Lácteos',
  'Culinarios',
  'Confitería y Snacks',
  'Bebidas No Alcohólicas',
];

const ESTADO_COLOR: Record<Pdv['estado'], string> = {
  ok: '#34d399',
  riesgo: '#fb923c',
  critico: '#ef4444',
  sin_medicion: '#9AAABB',
};

// El radio comunica volumen de medición: un PDV con muchas lecturas pesa más
// en los indicadores y merece más presencia visual.
function pdvRadius(p: Pdv, maxObs: number): number {
  if (maxObs === 0) return 5;
  // Rango contenido a propósito: con los PDV de una misma ciudad encimados, un
  // radio grande los funde en una mancha y tapa las rutas de traslado.
  return 5 + (p.observaciones / maxObs) * 11;
}

function MapFlyTo({ target }: { target: Pdv | null }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    map.flyTo([target.latitude, target.longitude], 7, { duration: 0.9 });
  }, [target?.store_id]);
  return null;
}

/**
 * Las rutas van en un plano propio por encima de los marcadores (600). Sin esto
 * los círculos de PDV —que crecen hasta 23 px de radio con el volumen medido—
 * tapan por completo un arco de quince kilómetros.
 */
function PanelDeRutas() {
  const map = useMap();
  useEffect(() => {
    if (!map.getPane('rutas')) {
      const pane = map.createPane('rutas');
      pane.style.zIndex = '650';
      pane.style.pointerEvents = 'none';
    }
  }, [map]);
  return null;
}

/** Publica el zoom para que la comba de los arcos se mida siempre en píxeles. */
function ZoomWatcher({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvents({ zoomend: () => onZoom(map.getZoom()) });
  useEffect(() => { onZoom(map.getZoom()); }, [map]);
  return null;
}

/** Lleva el mapa al traslado que el usuario quiere mirar de cerca. */
function MapFitRuta({ ruta }: { ruta: Traslado | null }) {
  const map = useMap();
  useEffect(() => {
    if (!ruta) return;
    const limites = limitesDeTraslado(ruta);
    if (!limites) return;
    map.flyToBounds(limites, { duration: 0.9, maxZoom: 10 });
  }, [ruta?.traslado_id]);
  return null;
}

// Leaflet necesita un invalidateSize() explícito cuando su contenedor cambia de
// tamaño; sin eso quedan franjas grises donde deberían ir los tiles.
function MapResizeFix({ pdv }: { pdv: Pdv[] }) {
  const map = useMap();
  const fittedRef = useRef(false);

  useEffect(() => {
    if (fittedRef.current || pdv.length === 0) return;
    const bounds = L.latLngBounds(pdv.map((p) => [p.latitude, p.longitude] as [number, number]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 6 });
    fittedRef.current = true;
  }, [pdv, map]);

  useEffect(() => {
    const t0 = setTimeout(() => map.invalidateSize(), 0);
    const t1 = setTimeout(() => map.invalidateSize(), 300);
    const onResize = () => map.invalidateSize();
    window.addEventListener('resize', onResize);
    const ro = new ResizeObserver(() => map.invalidateSize());
    const container = map.getContainer();
    if (container) ro.observe(container);
    return () => {
      clearTimeout(t0);
      clearTimeout(t1);
      window.removeEventListener('resize', onResize);
      ro.disconnect();
    };
  }, [map]);

  return null;
}

export default function PuntosDeVenta() {
  const [pdv, setPdv] = useState<Pdv[]>([]);
  const [categoria, setCategoria] = useState('');
  const [pais, setPais] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [traslados, setTraslados] = useState<Traslado[]>([]);
  const [rutaActiva, setRutaActiva] = useState<Traslado | null>(null);
  const [rutaEnfocada, setRutaEnfocada] = useState<Traslado | null>(null);
  const [zoom, setZoom] = useState(5);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [p, tr] = await Promise.all([
          api.pdv({
            categoria: categoria || undefined,
            country_code: pais || undefined,
          }),
          api.traslados({ country_code: pais || undefined }).catch(() => [] as Traslado[]),
        ]);
        if (!active) return;
        setPdv(p);
        setTraslados(tr);
        setError(null);
      } catch (e: any) {
        if (active) setError(e?.message ?? String(e));
      }
    };
    tick();
    const id = setInterval(tick, 20000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [categoria, pais]);

  const maxObs = useMemo(() => Math.max(0, ...pdv.map((p) => p.observaciones)), [pdv]);
  const porId = useMemo(() => {
    const m: Record<string, Pdv> = {};
    pdv.forEach((p) => {
      m[p.store_id] = p;
    });
    return m;
  }, [pdv]);
  const selected = selectedId ? porId[selectedId] : null;

  const paises = useMemo(() => {
    const set = new Set(pdv.map((p) => p.country_code));
    return [...set].sort();
  }, [pdv]);

  const criticos = pdv.filter((p) => p.estado === 'critico').length;
  const enRiesgo = pdv.filter((p) => p.estado === 'riesgo').length;

  // El backend ya devuelve solo lo vivo (propuesto y aprobado); acá se descartan
  // las filas sin geometría, que no se pueden dibujar.
  const rutasVisibles = useMemo(
    () =>
      traslados
        .map((t) => ({ t, arco: arcoDeTraslado(t, zoom) }))
        .filter((r): r is { t: Traslado; arco: [number, number][] } => r.arco !== null),
    [traslados, zoom],
  );

  const onTrasladoDecidido = (t: Traslado) => {
    setTraslados((cur) => cur.map((x) => (x.traslado_id === t.traslado_id ? t : x)));
    // Al aprobar, el mapa salta a la ruta recién despachada: es la confirmación
    // de que algo pasó, que es justo lo que faltaba al aprobar a ciegas.
    if (t.estado === 'aprobado') setRutaEnfocada(t);
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-5">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.25em] text-dn-600/80 font-bold mb-1">
            Red de medición
          </div>
          <h1 className="text-2xl font-semibold text-tinta leading-tight">Puntos de venta</h1>
          <p className="text-xs text-humo mt-0.5">
            {pdv.length} PDV auditados · {criticos} críticos · {enRiesgo} en riesgo
          </p>
        </div>
        <div className="flex items-end gap-3 flex-wrap">
          <Filtro
            label="País"
            value={pais}
            onChange={setPais}
            options={[
              { value: '', label: 'Todos los países' },
              ...paises.map((c) => ({ value: c, label: `${bandera(c)} ${c}` })),
            ]}
          />
          <Filtro
            label="Categoría"
            value={categoria}
            onChange={setCategoria}
            options={[
              { value: '', label: 'Todas las categorías' },
              ...CATEGORIAS.map((c) => ({ value: c, label: c })),
            ]}
          />
        </div>
      </header>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-600 text-sm rounded p-3">
          {error}
        </div>
      )}

      <NetworkStatusHero pdv={pdv} categoria={categoria || undefined} />

      <AgenteEnContexto agente="red_abastecimiento" limite={1} />

      <div className="grid grid-cols-12 gap-4">
        <section className="col-span-12 lg:col-span-8 bg-white border border-marco rounded-xl overflow-hidden">
          <header className="px-5 py-3 border-b border-marco flex items-center justify-between">
            <div>
              <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
                Mapa de auditoría
              </h2>
              <p className="text-[11px] text-humo mt-0.5">
                tamaño = lecturas en la ventana · color = estado de ejecución
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse-slow" />
              en vivo
            </span>
          </header>
          <div className="relative" style={{ height: 540 }}>
            <MapContainer
              center={REGION_CENTER}
              zoom={REGION_ZOOM}
              minZoom={3}
              maxZoom={10}
              maxBounds={REGION_BOUNDS}
              maxBoundsViscosity={1.0}
              scrollWheelZoom
              style={{ height: '100%', width: '100%', backgroundColor: '#0C1420' }}
              attributionControl={false}
            >
              <MapResizeFix pdv={pdv} />
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png" />
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png" />

              {pdv.map((p) => {
                const isSelected = p.store_id === selectedId;
                const base = pdvRadius(p, maxObs);
                const color = ESTADO_COLOR[p.estado];
                return (
                  <CircleMarker
                    key={p.store_id}
                    center={[p.latitude, p.longitude]}
                    radius={isSelected ? base + 6 : base}
                    pathOptions={{
                      color: isSelected ? '#33bdee' : color,
                      weight: isSelected ? 3 : 2,
                      fillColor: color,
                      fillOpacity: isSelected ? 0.85 : 0.55,
                    }}
                    eventHandlers={{ click: () => setSelectedId(p.store_id) }}
                  >
                    <Popup>
                      <PdvPopup p={p} />
                    </Popup>
                  </CircleMarker>
                );
              })}

              {/* La malla: cada traslado es un arco entre el PDV que cede y el
                  que está en quiebre. Punteado mientras espera aprobación,
                  sólido una vez aprobado — se ve de un vistazo qué ya se movió.
                  Va en su propio plano por encima de los círculos de PDV, que
                  si no lo tapan. */}
              <PanelDeRutas />
              {rutasVisibles.map(({ t, arco }) => {
                const activa = rutaActiva?.traslado_id === t.traslado_id;
                const aprobada = t.estado === 'aprobado';
                const color = aprobada ? '#0F9D63' : '#0D5CAB';
                const grosor = activa ? 4.5 : aprobada ? 3.4 : 2.6;
                return (
                  <Fragment key={`ruta-${t.traslado_id}`}>
                    {/* Filete blanco: el arco cruza por encima de los círculos
                        verdes de PDV y sin contraste se pierde contra ellos. */}
                    <Polyline
                      pane="rutas"
                      positions={arco}
                      pathOptions={{
                        color: '#ffffff', weight: grosor + 3,
                        opacity: 0.85, lineCap: 'round',
                      }}
                      interactive={false}
                    />
                    <Polyline
                      pane="rutas"
                      positions={arco}
                      pathOptions={{
                        color,
                        weight: grosor,
                        opacity: 1,
                        dashArray: aprobada ? undefined : '7 6',
                        lineCap: 'round',
                      }}
                      interactive={false}
                    />
                  </Fragment>
                );
              })}

              {/* Las dos puntas de la ruta activa, para que se lea de dónde sale
                  y a dónde llega sin buscar los puntos entre los otros PDV. */}
              {rutaActiva?.origen_lat != null && rutaActiva.destino_lat != null && (
                <>
                  <CircleMarker
                    pane="rutas"
                    center={[rutaActiva.origen_lat, rutaActiva.origen_lon as number]}
                    radius={7}
                    pathOptions={{ color: '#0F9D63', weight: 3, fillColor: '#ffffff', fillOpacity: 1 }}
                    interactive={false}
                  />
                  <CircleMarker
                    pane="rutas"
                    center={[rutaActiva.destino_lat, rutaActiva.destino_lon as number]}
                    radius={7}
                    pathOptions={{ color: '#ef4444', weight: 3, fillColor: '#ffffff', fillOpacity: 1 }}
                    interactive={false}
                  />
                </>
              )}

              {selected && (
                <CircleMarker
                  key={`ring-${selected.store_id}`}
                  center={[selected.latitude, selected.longitude]}
                  radius={pdvRadius(selected, maxObs) + 14}
                  pathOptions={{
                    color: '#33bdee',
                    weight: 1.5,
                    opacity: 0.7,
                    fillOpacity: 0,
                    dashArray: '4 4',
                  }}
                  interactive={false}
                />
              )}

              <MapFlyTo target={selected} />
              <MapFitRuta ruta={rutaEnfocada} />
              <ZoomWatcher onZoom={setZoom} />
            </MapContainer>

            <div className="absolute bottom-3 left-3 z-[400] bg-nieve border border-marco rounded-md backdrop-blur-md px-3 py-2 text-[11px] text-grafito">
              <div className="font-bold text-[10px] uppercase tracking-widest text-humo mb-1">
                Leyenda
              </div>
              <div className="space-y-1">
                <Legend dot={ESTADO_COLOR.ok} text="ejecución en meta" />
                <Legend dot={ESTADO_COLOR.riesgo} text="en riesgo" />
                <Legend dot={ESTADO_COLOR.critico} text="crítico · quiebres activos" />
                <Legend dot={ESTADO_COLOR.sin_medicion} text="sin medición en la ventana" />
                <div className="flex items-center gap-2 pt-1 mt-1 border-t border-marco">
                  <span
                    className="w-4 h-0 border-t-2 border-dashed"
                    style={{ borderColor: '#33bdee' }}
                  />
                  traslado propuesto
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-4 h-0 border-t-2" style={{ borderColor: '#34d399' }} />
                  traslado aprobado
                </div>
              </div>
            </div>
          </div>
        </section>

        <aside className="col-span-12 lg:col-span-4 space-y-4">
          <TrasladosPanel
            traslados={traslados}
            onHover={setRutaActiva}
            onEnfocar={setRutaEnfocada}
            onDecidido={onTrasladoDecidido}
          />
          <PdvRanking
            pdv={pdv}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
          />
        </aside>
      </div>

      <PdvDetailPanel pdv={selected} onClose={() => setSelectedId(null)} />
    </div>
  );
}

// ---- Auxiliares -------------------------------------------------------------

function Filtro({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div className="flex flex-col">
      <label className="text-[10px] uppercase tracking-widest text-humo mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-white border border-marco text-tinta text-sm rounded-md px-3 py-1.5 focus:border-dn-400 focus:outline-none min-w-[180px]"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function Legend({ dot, text }: { dot: string; text: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: dot }} />
      {text}
    </div>
  );
}

function PdvPopup({ p }: { p: Pdv }) {
  return (
    <div style={{ minWidth: 230 }}>
      <div style={{ fontSize: 11, color: '#999', textTransform: 'uppercase', letterSpacing: 1 }}>
        {p.cadena} · {p.canal}
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, color: '#111' }}>{p.nombre}</div>
      <div style={{ marginTop: 6, color: '#333' }}>
        <div>{p.ciudad}</div>
        <div>
          Disponibilidad:{' '}
          <b>{p.disponibilidad_pct == null ? '—' : `${fmtDecimal(p.disponibilidad_pct)}%`}</b>
        </div>
        <div>
          Ejecución: <b>{p.ejecucion_pct == null ? '—' : `${fmtDecimal(p.ejecucion_pct)}%`}</b>
        </div>
        <div>Lecturas: <b>{fmtNumber(p.observaciones)}</b></div>
        {p.quiebres > 0 && (
          <div style={{ color: '#dc2626' }}>
            Quiebres: <b>{p.quiebres}</b>
          </div>
        )}
      </div>
    </div>
  );
}

// Por qué cada PDV está en la lista. La ejecución perfecta es disponibilidad Y
// planograma a la vez, así que el motivo dice cuál de las dos falló — y eso
// decide quién tiene que ir: el distribuidor repone, el mercaderista acomoda.
const MOTIVO: Record<
  Pdv['motivo'],
  { texto: string; ayuda: string; clase: string } | null
> = {
  quiebre_y_planograma: {
    texto: 'quiebre + planograma',
    ayuda: 'falta producto y además el que hay está mal exhibido',
    clase: 'bg-red-50 text-red-700 border-red-200',
  },
  quiebre: {
    texto: 'quiebre de stock',
    ayuda: 'el producto no está en el anaquel: es reposición',
    clase: 'bg-orange-50 text-orange-700 border-orange-200',
  },
  planograma: {
    texto: 'planograma',
    ayuda: 'el producto está pero fuera de su lugar: es mercaderismo',
    clase: 'bg-amber-50 text-amber-700 border-amber-200',
  },
  sin_medicion: {
    texto: 'sin medición',
    ayuda: 'ningún auditor pasó por acá en la ventana',
    clase: 'bg-nieve text-humo border-marco',
  },
  en_meta: null,
};

const FILTROS = [
  { id: 'atender', label: 'Por atender' },
  { id: 'critico', label: 'Críticos' },
  { id: 'quiebre', label: 'Con quiebre' },
  { id: 'sin_medicion', label: 'Sin medición' },
  { id: 'todos', label: 'Todos' },
] as const;

type FiltroId = (typeof FILTROS)[number]['id'];

function PdvRanking({
  pdv,
  selectedId,
  onSelect,
}: {
  pdv: Pdv[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [filtro, setFiltro] = useState<FiltroId>('atender');
  const [despachados, setDespachados] = useState<Record<string, string>>({});

  const ordenados = useMemo(() => {
    const pasa = (p: Pdv) => {
      switch (filtro) {
        // Por defecto se esconden los que están en meta: la lista es de trabajo
        // pendiente, no el censo de la red.
        case 'atender': return p.estado !== 'ok';
        case 'critico': return p.estado === 'critico';
        case 'quiebre': return p.quiebres > 0;
        case 'sin_medicion': return p.estado === 'sin_medicion';
        default: return true;
      }
    };
    return pdv.filter(pasa).sort((a, b) => {
      if (a.ejecucion_pct == null) return 1;
      if (b.ejecucion_pct == null) return -1;
      return a.ejecucion_pct - b.ejecucion_pct;
    });
  }, [pdv, filtro]);

  const despachar = async (p: Pdv) => {
    setDespachados((cur) => ({ ...cur, [p.store_id]: 'enviando' }));
    try {
      await api.despacharAccion({
        store_id: p.store_id,
        sku: p.sku_critico ?? '—',
        tipo_accion: p.motivo === 'planograma' ? 'corregir_planograma' : 'reponer',
        tienda: p.nombre,
        producto: p.producto_critico ?? undefined,
        categoria: p.categoria_critica ?? undefined,
        country_code: p.country_code,
        motivo: `ejecución ${p.ejecucion_pct ?? 0}% · ${p.quiebres} quiebres en la ventana`,
        urgencia: p.estado === 'critico' ? 'alta' : 'media',
      });
      setDespachados((cur) => ({ ...cur, [p.store_id]: 'ok' }));
    } catch {
      setDespachados((cur) => ({ ...cur, [p.store_id]: 'error' }));
    }
  };

  return (
    <section className="bg-white border border-marco rounded-xl overflow-hidden">
      <header className="px-5 py-3 border-b border-marco">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold">
            PDV por atender
          </h2>
          <span className="text-[10px] tabular-nums text-humo">{ordenados.length}</span>
        </div>
        <p className="text-[11px] text-humo mt-0.5 leading-snug">
          las tiendas de la red que en la última hora quedaron más lejos de su meta de
          ejecución. El % es ejecución perfecta —producto en anaquel y bien exhibido— y la
          flecha compara la última media hora contra la anterior.
        </p>
        <div className="flex flex-wrap gap-1 mt-2">
          {FILTROS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFiltro(f.id)}
              className={[
                'px-2 py-0.5 rounded-full text-[10px] border transition-colors',
                filtro === f.id
                  ? 'bg-dn-600 border-dn-600 text-white font-semibold'
                  : 'bg-white border-marco text-humo hover:text-grafito hover:border-humo',
              ].join(' ')}
            >
              {f.label}
            </button>
          ))}
        </div>
      </header>
      <ol className="divide-y divide-marco max-h-[540px] overflow-y-auto">
        {ordenados.length === 0 && (
          <li className="px-5 py-10 text-center text-humo text-[13px]">
            Ninguna tienda cae en este filtro ahora mismo.
          </li>
        )}
        {ordenados.map((p, i) => (
          <PdvFila
            key={p.store_id}
            p={p}
            rank={i + 1}
            activo={selectedId === p.store_id}
            estadoDespacho={despachados[p.store_id]}
            onSelect={() => onSelect(p.store_id)}
            onDespachar={() => despachar(p)}
          />
        ))}
      </ol>
    </section>
  );
}

function PdvFila({
  p,
  rank,
  activo,
  estadoDespacho,
  onSelect,
  onDespachar,
}: {
  p: Pdv;
  rank: number;
  activo: boolean;
  estadoDespacho?: string;
  onSelect: () => void;
  onDespachar: () => void;
}) {
  const motivo = MOTIVO[p.motivo];
  const t = p.tendencia_pp;
  // Menos de 3 pp entre las dos mitades de la ventana es ruido de muestreo, no
  // una tendencia: marcarlo como mejora o caída sería inventar una señal.
  const tendencia = t == null || Math.abs(t) < 3 ? null : t;

  return (
    <li
      onClick={onSelect}
      className={[
        'cursor-pointer px-4 py-2.5 transition-colors',
        activo ? 'bg-dn-400/10' : 'hover:bg-nieve',
      ].join(' ')}
    >
      <div className="flex items-center gap-3">
        <span className="text-[11px] tabular-nums text-humo w-5 text-right">#{rank}</span>
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: ESTADO_COLOR[p.estado] }}
        />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-tinta truncate">
            {bandera(p.country_code)} {p.nombre}
          </div>
          <div className="text-[11px] text-humo truncate">
            {p.cadena} · {p.ciudad}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm font-bold text-dn-600 tabular-nums flex items-center gap-1 justify-end">
            {p.ejecucion_pct == null ? '—' : `${fmtDecimal(p.ejecucion_pct)}%`}
            {tendencia != null && (
              <span
                title={`${tendencia > 0 ? 'mejorando' : 'cayendo'} ${fmtDecimal(Math.abs(tendencia))} pp en la última media hora`}
                className={tendencia > 0 ? 'text-emerald-600' : 'text-red-600'}
              >
                {tendencia > 0 ? (
                  <ArrowUpRight className="w-3.5 h-3.5" strokeWidth={2.5} />
                ) : (
                  <ArrowDownRight className="w-3.5 h-3.5" strokeWidth={2.5} />
                )}
              </span>
            )}
          </div>
          <div className="text-[10px] text-humo tabular-nums">
            {fmtNumber(p.observaciones)} lecturas
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-1.5 pl-[34px] flex-wrap">
        {motivo && (
          <span
            title={motivo.ayuda}
            className={`px-1.5 py-px rounded border text-[10px] ${motivo.clase}`}
          >
            {motivo.texto}
          </span>
        )}
        {p.quiebres > 0 && (
          <span className="text-[10px] text-humo tabular-nums">
            {p.quiebres} quiebres
            {p.producto_critico && (
              <span className="text-grafito"> · sobre todo {p.producto_critico}</span>
            )}
          </span>
        )}
        {p.mercaderista && (
          <span className="text-[10px] text-humo truncate">{p.mercaderista}</span>
        )}

        {p.estado !== 'ok' && p.estado !== 'sin_medicion' && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (!estadoDespacho) onDespachar();
            }}
            disabled={!!estadoDespacho}
            className={[
              'ml-auto px-2 py-0.5 rounded text-[10px] border transition-colors',
              estadoDespacho === 'ok'
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                : estadoDespacho === 'error'
                  ? 'border-red-300 bg-red-50 text-red-700'
                  : 'border-dn-400 text-dn-600 hover:bg-dn-600 hover:text-white hover:border-dn-600',
            ].join(' ')}
          >
            {estadoDespacho === 'ok'
              ? '✓ visita despachada'
              : estadoDespacho === 'enviando'
                ? 'enviando…'
                : estadoDespacho === 'error'
                  ? 'no se pudo enviar'
                  : 'Despachar visita'}
          </button>
        )}
      </div>
    </li>
  );
}
