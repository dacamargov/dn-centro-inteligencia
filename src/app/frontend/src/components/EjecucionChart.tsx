import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api, VisitasTimeline } from '../lib/api';
import { fmtDecimal } from '../lib/format';
import { AccionAprobada } from '../lib/impact';

// Tonos saturados a propósito: sobre lienzo claro los pasteles se pierden y
// las cinco curvas tienen que distinguirse entre sí de un vistazo.
const CATEGORY_COLORS: Record<string, string> = {
  'Bebidas Calientes': '#0891B2',
  'Lácteos': '#059669',
  'Culinarios': '#EA580C',
  'Confitería y Snacks': '#7C3AED',
  'Bebidas No Alcohólicas': '#DB2777',
};
const FALLBACK_COLOR = '#64748B';

function formatHHMM(iso: string) {
  return new Date(iso).toLocaleTimeString('es-PA', { hour: '2-digit', minute: '2-digit' });
}

interface Props {
  anotaciones?: AccionAprobada[];
}

type Metrica = 'disponibilidad_pct' | 'ejecucion_pct';

const METRICA_LABEL: Record<Metrica, string> = {
  disponibilidad_pct: 'Disponibilidad en anaquel',
  ejecucion_pct: 'Ejecución perfecta',
};

export default function EjecucionChart({ anotaciones = [] }: Props) {
  const [data, setData] = useState<VisitasTimeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metrica, setMetrica] = useState<Metrica>('disponibilidad_pct');
  // null = todas visibles; tras interacción guarda el conjunto explícito.
  const [visible, setVisible] = useState<Set<string> | null>(null);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const d = await api.visitasTimeline(30);
        if (!active) return;
        setData(d);
        setError(null);
      } catch (e: any) {
        if (active) setError(e?.message ?? String(e));
      }
    };
    tick();
    const id = setInterval(tick, 6000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const isVisible = (cat: string) => (visible === null ? true : visible.has(cat));

  function toggleCategoria(cat: string, solo: boolean) {
    if (!data) return;
    setVisible((cur) => {
      if (solo) {
        if (cur && cur.size === 1 && cur.has(cat)) return null;
        return new Set([cat]);
      }
      const base = cur ?? new Set(data.categorias);
      const next = new Set(base);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      if (next.size === 0) return null;
      if (next.size === data.categorias.length) return null;
      return next;
    });
  }

  // Cada categoría es una línea de nivel (%), y "promedio" es el ponderado del
  // minuto. Apilar no tendría sentido: son porcentajes, no montos.
  const series = useMemo(() => {
    if (!data) return [] as any[];
    return data.puntos.map((p) => {
      const row: any = { ts: p.minute_ts, promedio: p[metrica], observaciones: p.observaciones };
      for (const cat of data.categorias) {
        const c = p.por_categoria[cat];
        row[cat] = c && isVisible(cat) ? c[metrica] : null;
      }
      return row;
    });
  }, [data, visible, metrica]);

  const ultimo = series.length ? series[series.length - 1] : null;
  const promedioVentana = useMemo(() => {
    if (!series.length) return 0;
    const tot = series.reduce((a, r) => a + (r.observaciones ?? 0), 0) || 1;
    return series.reduce((a, r) => a + (r.promedio ?? 0) * (r.observaciones ?? 0), 0) / tot;
  }, [series]);
  const obsVentana = useMemo(
    () => series.reduce((a, r) => a + (r.observaciones ?? 0), 0),
    [series],
  );

  // El eje se ajusta al rango real de las series visibles. Fijarlo de 0 a 100
  // aplastaba las cinco categorías en una banda de diez puntos y parecían una
  // sola curva; con el rango ceñido se separan y se distingue quién va abajo.
  const dominio = useMemo<[number, number]>(() => {
    const vals: number[] = [];
    for (const row of series) {
      for (const [k, v] of Object.entries(row)) {
        if (k === 'ts' || k === 'observaciones') continue;
        if (typeof v === 'number' && Number.isFinite(v)) vals.push(v);
      }
    }
    if (!vals.length) return [0, 100];
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const margen = Math.max(2, (max - min) * 0.15);
    return [Math.max(0, Math.floor(min - margen)), Math.min(100, Math.ceil(max + margen))];
  }, [series]);

  return (
    <section className="relative bg-white border border-marco rounded-lg overflow-hidden">
      <header className="flex items-center justify-between px-5 py-4 border-b border-marco">
        <div>
          <h2 className="text-sm uppercase tracking-widest text-grafito font-semibold">
            {METRICA_LABEL[metrica]} · últimos 30 min
          </h2>
          <p className="text-[11px] text-humo">
            por categoría · refresh 6s · clic en la leyenda para filtrar
          </p>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex rounded-md border border-marco overflow-hidden">
            {(Object.keys(METRICA_LABEL) as Metrica[]).map((m) => (
              <button
                key={m}
                onClick={() => setMetrica(m)}
                className={[
                  'px-2.5 py-1 text-[11px] font-medium transition-colors',
                  metrica === m
                    ? 'bg-dn-400/15 text-dn-600'
                    : 'text-humo hover:text-grafito',
                ].join(' ')}
              >
                {m === 'disponibilidad_pct' ? 'Disponibilidad' : 'Ejecución'}
              </button>
            ))}
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-widest text-humo">Último minuto</div>
            <div className="text-xl font-bold text-dn-600 tabular-nums">
              {ultimo ? `${fmtDecimal(ultimo.promedio)}%` : '—'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-widest text-humo">Promedio 30 min</div>
            <div className="text-xl font-bold text-tinta tabular-nums">
              {obsVentana ? `${fmtDecimal(promedioVentana)}%` : '—'}
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600">
            <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse-slow" />
            EN VIVO
          </span>
        </div>
      </header>

      {anotaciones.length > 0 && (
        <div className="flex items-center gap-2 px-5 py-2 border-b border-marco bg-emerald-500/[0.04]">
          <span className="text-[10px] uppercase tracking-widest text-emerald-600 font-medium">
            ✓ {anotaciones.length}{' '}
            {anotaciones.length === 1 ? 'acción despachada' : 'acciones despachadas'} · impacto en
            seguimiento
          </span>
          <div className="flex flex-wrap gap-2 ml-auto">
            {anotaciones.slice(-4).map((a) => {
              const min = Math.max(
                0,
                Math.floor((Date.now() - new Date(a.aprobada_en).getTime()) / 60000),
              );
              return (
                <span
                  key={a.rec_id}
                  title={a.title}
                  className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600 bg-emerald-500/10 border border-emerald-500/30 rounded-full px-2 py-0.5 max-w-[240px]"
                >
                  <span className="truncate">{a.title}</span>
                  <span className="text-emerald-600/70 ml-1">
                    +{fmtDecimal(a.impacto_pp)} pp
                  </span>
                  <span className="text-emerald-600/50">· hace {min} min</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="px-2 pt-4 pb-2 h-[340px]">
        {error && <div className="text-red-600 text-xs px-4 py-2">Error: {error}</div>}
        {!data && !error && (
          <div className="text-humo text-sm py-12 text-center">cargando…</div>
        )}
        {data && data.puntos.length === 0 && (
          <div className="text-humo text-sm py-12 text-center">
            sin lecturas en los últimos 30 minutos · usa el botón "Iniciar demo" arriba
          </div>
        )}
        {data && data.puntos.length > 0 && (
          <ResponsiveContainer width="100%" height="100%">
            {/* ComposedChart y no AreaChart: este gráfico mezcla un área (el
                promedio) con cinco líneas (las categorías), y AreaChart
                descarta silenciosamente los hijos que no son <Area>. */}
            <ComposedChart data={series} margin={{ top: 10, right: 16, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="grad-promedio" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0D5CAB" stopOpacity={0.16} />
                  <stop offset="100%" stopColor="#0D5CAB" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 6" stroke="#D8E3EE" vertical={false} />
              <XAxis
                dataKey="ts"
                tickFormatter={formatHHMM}
                stroke="#9AAABB"
                tick={{ fontSize: 11, fill: '#5A6E85' }}
                axisLine={{ stroke: '#D8E3EE' }}
                tickLine={false}
              />
              <YAxis
                stroke="#9AAABB"
                tick={{ fontSize: 11, fill: '#5A6E85' }}
                axisLine={{ stroke: '#D8E3EE' }}
                tickLine={false}
                domain={dominio}
                tickFormatter={(v: any) => `${Math.round(Number(v))}%`}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #24374d',
                  borderRadius: 6,
                  fontSize: 12,
                  color: '#14263B',
                }}
                labelFormatter={(label: any) => formatHHMM(String(label))}
                formatter={(value: any, name: any) => [`${fmtDecimal(Number(value))}%`, name]}
                cursor={{ stroke: '#D8E3EE', strokeDasharray: '3 3' }}
              />

              {/* El promedio queda como telón de fondo: las protagonistas son
                  las categorías, porque la conversación es sobre cuál se cae. */}
              <Area
                type="monotone"
                dataKey="promedio"
                name="Promedio ponderado"
                stroke="#0D5CAB"
                strokeWidth={2.4}
                strokeDasharray="5 4"
                fill="url(#grad-promedio)"
                isAnimationActive={false}
              />

              {data.categorias.map((cat) => {
                if (!isVisible(cat)) return null;
                return (
                  <Line
                    key={cat}
                    type="monotone"
                    dataKey={cat}
                    name={cat}
                    stroke={CATEGORY_COLORS[cat] ?? FALLBACK_COLOR}
                    strokeWidth={2.1}
                    dot={false}
                    connectNulls
                    isAnimationActive={false}
                  />
                );
              })}

              {anotaciones.map((a) => {
                const ms = new Date(a.aprobada_en).getTime();
                let cercano: string | null = null;
                let mejor = Infinity;
                for (const row of series) {
                  const diff = Math.abs(new Date(row.ts).getTime() - ms);
                  if (diff < mejor) {
                    mejor = diff;
                    cercano = row.ts;
                  }
                }
                if (!cercano) return null;
                return (
                  <ReferenceLine
                    key={a.rec_id}
                    x={cercano}
                    stroke="#10b981"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                    label={{ value: '✓', position: 'top', fill: '#34d399', fontSize: 12 }}
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {data && (
        <div className="flex flex-wrap gap-2 px-5 pb-4 pt-1">
          {data.categorias.map((cat) => {
            const on = isVisible(cat);
            const color = CATEGORY_COLORS[cat] ?? FALLBACK_COLOR;
            return (
              <button
                key={cat}
                onClick={(e) => toggleCategoria(cat, e.altKey || e.shiftKey)}
                title="Clic para alternar · Alt/Shift-clic para aislar"
                className={[
                  'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px]',
                  'transition-all duration-150',
                  on
                    ? 'border-marco bg-white text-tinta'
                    : 'border-marco bg-transparent text-humo line-through hover:text-grafito',
                ].join(' ')}
              >
                <span
                  className="w-2 h-2 rounded-sm"
                  style={{ backgroundColor: on ? color : '#D8E3EE' }}
                />
                {cat}
              </button>
            );
          })}
          {visible !== null && (
            <button
              onClick={() => setVisible(null)}
              className="ml-auto text-[11px] text-dn-600 hover:text-dn-600 px-2.5 py-1"
            >
              ↺ limpiar filtro
            </button>
          )}
        </div>
      )}
    </section>
  );
}
