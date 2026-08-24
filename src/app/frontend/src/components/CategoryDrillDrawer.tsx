import {
  AlertTriangle,
  ChevronDown,
  LayoutGrid,
  Loader2,
  MessageCircle,
  PackageX,
  Sparkles,
  Tag,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api, type DiagnosticoCategoria, type SkuDetalle } from '../lib/api';
import { bandera, fmtDecimal, fmtNumber, fmtPP, fmtPrecio, relTime } from '../lib/format';
import { CATEGORY_ICON } from '../lib/icons';

type Props = {
  categoria: string | null;
  onClose: () => void;
};

const STATUS_LABEL: Record<DiagnosticoCategoria['totales']['status'], string> = {
  above: 'SOBRE LA META',
  on: 'EN META',
  behind: 'BAJO LA META',
};

const STATUS_COLOR: Record<DiagnosticoCategoria['totales']['status'], string> = {
  above: 'text-emerald-600 bg-emerald-500/15 border-emerald-500/40',
  on: 'text-dn-600 bg-dn-400/15 border-dn-400/40',
  behind: 'text-red-600 bg-red-500/15 border-red-500/40',
};

export default function CategoryDrillDrawer({ categoria, onClose }: Props) {
  const [diagnostico, setDiagnostico] = useState<DiagnosticoCategoria | null>(null);
  const [explicacion, setExplicacion] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!categoria) {
      abortRef.current?.abort();
      return;
    }
    setDiagnostico(null);
    setExplicacion('');
    setElapsedMs(null);
    setError(null);
    setStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    (async () => {
      try {
        for await (const ev of api.streamExplicarCategoria(categoria, ctrl.signal)) {
          if (ctrl.signal.aborted) return;
          if (ev.type === 'diagnosis') setDiagnostico(ev.data);
          else if (ev.type === 'delta') setExplicacion((s) => s + ev.data.text);
          else if (ev.type === 'done') setElapsedMs(ev.data.elapsed_ms);
          else if (ev.type === 'error') setError(ev.data.detail);
        }
      } catch (e: any) {
        if (!ctrl.signal.aborted) setError(e?.message ?? String(e));
      } finally {
        if (!ctrl.signal.aborted) setStreaming(false);
      }
    })();

    return () => ctrl.abort();
  }, [categoria]);

  useEffect(() => {
    if (!categoria) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [categoria, onClose]);

  const open = categoria !== null;

  return (
    <>
      <div
        onClick={onClose}
        className={[
          'fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity duration-200',
          open ? 'opacity-100' : 'opacity-0 pointer-events-none',
        ].join(' ')}
      />
      <aside
        className={[
          'fixed top-0 right-0 z-50 h-screen w-full max-w-[560px]',
          'bg-nieve border-l border-marco shadow-2xl',
          'transform transition-transform duration-300 ease-out flex flex-col',
          open ? 'translate-x-0' : 'translate-x-full',
        ].join(' ')}
        aria-hidden={!open}
      >
        {categoria && (
          <DrawerBody
            categoria={categoria}
            diagnostico={diagnostico}
            explicacion={explicacion}
            streaming={streaming}
            elapsedMs={elapsedMs}
            error={error}
            onClose={onClose}
          />
        )}
      </aside>
    </>
  );
}

function DrawerBody({
  categoria,
  diagnostico,
  explicacion,
  streaming,
  elapsedMs,
  error,
  onClose,
}: {
  categoria: string;
  diagnostico: DiagnosticoCategoria | null;
  explicacion: string;
  streaming: boolean;
  elapsedMs: number | null;
  error: string | null;
  onClose: () => void;
}) {
  const CI = CATEGORY_ICON[categoria];
  const t = diagnostico?.totales;
  const s = diagnostico?.senales;

  return (
    <>
      <header className="flex items-start justify-between gap-3 px-5 py-4 border-b border-marco">
        <div className="flex items-start gap-3 min-w-0">
          {CI && (
            <span className="mt-0.5 inline-flex items-center justify-center w-9 h-9 rounded-lg bg-white border border-marco">
              <CI className="w-5 h-5 text-tinta" strokeWidth={1.8} />
            </span>
          )}
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-[0.22em] text-humo mb-0.5">
              Detalle de categoría
            </div>
            <h2 className="text-xl font-bold text-tinta truncate">{categoria}</h2>
            {t && (
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <span
                  className={[
                    'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-widest',
                    STATUS_COLOR[t.status],
                  ].join(' ')}
                >
                  {STATUS_LABEL[t.status]} · {Math.round(t.cumplimiento_pct)}%
                </span>
                <span className="text-[11px] text-grafito">
                  brecha de ejecución:{' '}
                  <span className="text-tinta tabular-nums">
                    {fmtPP(t.brecha_ejecucion_pp)}
                  </span>
                </span>
              </div>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-humo hover:text-tinta transition-colors p-1 rounded hover:bg-white"
          aria-label="Cerrar"
        >
          <X className="w-5 h-5" />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {error && (
          <div className="text-red-600 text-xs bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {t && (
          <section className="grid grid-cols-3 gap-2">
            <MetricaVsMeta
              label="Disponibilidad"
              valor={t.disponibilidad_pct}
              meta={t.meta_disponibilidad_pct}
            />
            <MetricaVsMeta
              label="Ejecución"
              valor={t.ejecucion_pct}
              meta={t.meta_ejecucion_pct}
            />
            <MetricaVsMeta label="Share of shelf" valor={t.sos_pct} meta={t.meta_sos_pct} />
          </section>
        )}

        <section>
          <h3 className="text-[10px] uppercase tracking-[0.22em] text-humo mb-2">
            Señales ahora
          </h3>
          {s ? (
            <div className="grid grid-cols-2 gap-2">
              <SignalChip
                Icon={Tag}
                label="SKUs caros vs rival"
                value={s.skus_caros}
                hint={
                  s.skus_caros > 0
                    ? `índice promedio ${fmtDecimal(s.indice_promedio)}`
                    : 'precio alineado'
                }
                tone={s.skus_caros > 0 ? 'warn' : 'ok'}
              />
              <SignalChip
                Icon={MessageCircle}
                label="Posts negativos (60 min)"
                value={s.posts_negativos}
                hint="escucha social"
                tone={s.posts_negativos > 5 ? 'warn' : 'neutral'}
              />
              <SignalChip
                Icon={PackageX}
                label="PDV con quiebre"
                value={s.pdv_con_quiebre}
                hint="al menos un SKU agotado"
                tone={s.pdv_con_quiebre > 0 ? 'warn' : 'ok'}
              />
              <SignalChip
                Icon={Sparkles}
                label="Recs pendientes"
                value={s.recs_pendientes}
                hint="de los agentes"
                tone={s.recs_pendientes > 0 ? 'info' : 'neutral'}
              />
            </div>
          ) : (
            <div className="text-humo text-xs">Cargando señales…</div>
          )}
        </section>

        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] uppercase tracking-[0.22em] text-humo">
              Lectura del analista IA
            </h3>
            {streaming && (
              <span className="text-[10px] text-dn-600 inline-flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" /> Claude Sonnet 4.6 razonando
              </span>
            )}
            {elapsedMs !== null && !streaming && (
              <span className="text-[10px] text-humo">{(elapsedMs / 1000).toFixed(1)}s</span>
            )}
          </div>
          <div className="rounded-lg border border-marco bg-white p-4 min-h-[120px]">
            {explicacion ? (
              <ExplanationRender markdown={explicacion} streaming={streaming} />
            ) : (
              <div className="text-humo text-xs">
                {streaming ? 'Recolectando datos y razonando…' : 'Sin análisis.'}
              </div>
            )}
          </div>
        </section>

        {diagnostico && diagnostico.top_skus.length > 0 && (
          <section>
            <h3 className="text-[10px] uppercase tracking-[0.22em] text-humo mb-2">
              SKUs que más pesan en la brecha
            </h3>
            <div className="space-y-1.5">
              {diagnostico.top_skus.map((sku) => (
                <SkuRow key={sku.sku} sku={sku} categoria={categoria} />
              ))}
            </div>
          </section>
        )}

        {diagnostico && diagnostico.recomendaciones_activas.length > 0 && (
          <section>
            <h3 className="text-[10px] uppercase tracking-[0.22em] text-humo mb-2">
              Recomendaciones activas de los agentes
            </h3>
            <div className="space-y-1.5">
              {diagnostico.recomendaciones_activas.slice(0, 3).map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between rounded border border-marco bg-white px-3 py-2 text-[11.5px]"
                >
                  <div className="min-w-0">
                    <div className="text-tinta truncate">{r.title}</div>
                    <div className="text-humo text-[10px]">
                      {r.agent_name} · {r.severity}
                    </div>
                  </div>
                  <span
                    className={[
                      'text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded',
                      r.decidida ? 'bg-dn-100/40 text-grafito' : 'bg-dn-600/15 text-dn-600',
                    ].join(' ')}
                  >
                    {r.decidida ? 'decidida' : 'pendiente'}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      <ActionFooter categoria={categoria} diagnostico={diagnostico} />
    </>
  );
}

type ActionType =
  | 'priorizar_visitas'
  | 'corregir_planograma'
  | 'negociar_espacio'
  | 'revisar_precio'
  | 'escalar_equipo';

function ActionFooter({
  categoria,
  diagnostico,
}: {
  categoria: string;
  diagnostico: DiagnosticoCategoria | null;
}) {
  const [status, setStatus] = useState<Record<ActionType, 'idle' | 'pending' | 'done' | 'error'>>({
    priorizar_visitas: 'idle',
    corregir_planograma: 'idle',
    negociar_espacio: 'idle',
    revisar_precio: 'idle',
    escalar_equipo: 'idle',
  });
  const [toast, setToast] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null);

  // Para "revisar precio" tomamos el SKU con mayor sobreprecio; para el resto,
  // el que más pesa en la brecha de disponibilidad.
  const skuPrecio = useMemo(() => {
    if (!diagnostico) return null;
    return (
      [...diagnostico.top_skus].sort(
        (a, b) => b.precio_sugerido_usd - a.precio_sugerido_usd,
      )[0] ?? null
    );
  }, [diagnostico]);

  const skuQuiebre = useMemo(() => {
    if (!diagnostico) return null;
    return (
      [...diagnostico.top_skus].sort((a, b) => a.disponibilidad_pct - b.disponibilidad_pct)[0] ??
      null
    );
  }, [diagnostico]);

  async function submit(action: ActionType, params: Record<string, any>) {
    setStatus((s) => ({ ...s, [action]: 'pending' }));
    try {
      const r = await api.accionCategoria(categoria, { action_type: action, params });
      setStatus((s) => ({ ...s, [action]: 'done' }));
      setToast({ kind: 'ok', msg: `Acción registrada (${r.log_id.slice(0, 10)}…)` });
      setTimeout(() => setToast(null), 3500);
    } catch (e: any) {
      setStatus((s) => ({ ...s, [action]: 'error' }));
      setToast({ kind: 'err', msg: e?.message ?? String(e) });
      setTimeout(() => setToast(null), 5000);
    }
  }

  return (
    <footer className="border-t border-marco px-5 py-3 bg-nieve">
      {toast && (
        <div
          className={[
            'mb-2 px-3 py-2 rounded-lg text-[11.5px] font-semibold border',
            toast.kind === 'ok'
              ? 'bg-emerald-500/20 text-emerald-700 border-emerald-400/40'
              : 'bg-red-500/20 text-red-700 border-red-400/40',
          ].join(' ')}
        >
          {toast.msg}
        </div>
      )}
      <div className="text-[10px] text-humo uppercase tracking-[0.22em] mb-2">
        Acciones sobre la categoría
      </div>
      <div className="grid grid-cols-2 gap-2">
        <ActionButton
          label={skuQuiebre ? `Priorizar ruta · ${skuQuiebre.sku}` : 'Priorizar ruta de campo'}
          state={status.priorizar_visitas}
          onClick={() =>
            submit('priorizar_visitas', {
              categoria,
              sku: skuQuiebre?.sku,
              pdv: skuQuiebre?.pdv_afectados,
            })
          }
        />
        <ActionButton
          label="Brief de planograma"
          state={status.corregir_planograma}
          onClick={() => submit('corregir_planograma', { categoria })}
        />
        <ActionButton
          label="Negociar espacio"
          state={status.negociar_espacio}
          onClick={() =>
            submit('negociar_espacio', {
              categoria,
              brecha_sos_pp: diagnostico?.totales.brecha_sos_pp,
            })
          }
        />
        <ActionButton
          label={skuPrecio ? `Revisar precio · ${skuPrecio.sku}` : 'Revisar precio'}
          state={status.revisar_precio}
          disabled={!skuPrecio}
          onClick={() =>
            skuPrecio &&
            submit('revisar_precio', {
              categoria,
              sku: skuPrecio.sku,
              precio_sugerido: skuPrecio.precio_sugerido_usd,
            })
          }
        />
        <ActionButton
          label="Escalar al comité de marca"
          state={status.escalar_equipo}
          onClick={() => submit('escalar_equipo', { categoria })}
        />
      </div>
    </footer>
  );
}

function ActionButton({
  label,
  state,
  onClick,
  disabled,
}: {
  label: string;
  state: 'idle' | 'pending' | 'done' | 'error';
  onClick: () => void;
  disabled?: boolean;
}) {
  const styles =
    state === 'done'
      ? 'border-emerald-400/50 bg-emerald-500/15 text-emerald-700'
      : state === 'error'
        ? 'border-red-400/50 bg-red-500/15 text-red-700'
        : 'border-dn-400/40 bg-dn-400/10 text-dn-600 hover:bg-dn-400/20';
  const pendingOrDisabled = state === 'pending' || disabled;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pendingOrDisabled}
      className={[
        'text-[11.5px] font-semibold px-3 py-2 rounded border transition-colors',
        styles,
        pendingOrDisabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
        'flex items-center justify-center gap-1.5',
      ].join(' ')}
    >
      {state === 'pending' && <Loader2 className="w-3 h-3 animate-spin" />}
      {state === 'done' && <span>✓</span>}
      <span className="truncate">{label}</span>
    </button>
  );
}

// ---------- subcomponentes ---------------------------------------------------

function MetricaVsMeta({ label, valor, meta }: { label: string; valor: number; meta: number }) {
  const brecha = valor - meta;
  const ok = brecha >= 0;
  return (
    <div className="rounded-lg border border-marco bg-white px-3 py-2">
      <div className="text-[9.5px] uppercase tracking-wider text-humo">{label}</div>
      <div className="text-lg font-bold tabular-nums text-tinta leading-tight">
        {fmtDecimal(valor)}%
      </div>
      <div
        className={`text-[10px] tabular-nums ${ok ? 'text-emerald-600' : 'text-red-600'}`}
      >
        {fmtPP(brecha)} vs meta {meta}%
      </div>
    </div>
  );
}

function SignalChip({
  Icon,
  label,
  value,
  hint,
  tone,
}: {
  Icon: any;
  label: string;
  value: number;
  hint: string;
  tone: 'ok' | 'warn' | 'info' | 'neutral';
}) {
  const TONE = {
    ok: 'border-marco bg-white text-grafito',
    warn: 'border-red-500/40 bg-red-500/10 text-red-600',
    info: 'border-dn-400/40 bg-dn-400/10 text-dn-600',
    neutral: 'border-marco bg-white text-grafito',
  }[tone];

  return (
    <div className={`rounded-lg border px-3 py-2 ${TONE}`}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider opacity-80">
        <Icon className="w-3 h-3" strokeWidth={2} />
        {label}
      </div>
      <div className="text-xl font-bold tabular-nums mt-0.5">{value}</div>
      <div className="text-[10px] opacity-70">{hint}</div>
    </div>
  );
}

function SkuRow({
  sku,
  categoria,
}: {
  sku: DiagnosticoCategoria['top_skus'][number];
  categoria: string;
}) {
  const [open, setOpen] = useState(false);
  const [detalle, setDetalle] = useState<SkuDetalle | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setErr(null);
    setDetalle(null);
    api
      .skuDetalle(categoria, sku.sku)
      .then((d: SkuDetalle) => {
        if (active) setDetalle(d);
      })
      .catch((e: any) => {
        if (active) setErr(e?.message ?? String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [open, categoria, sku.sku]);

  return (
    <div className="rounded-lg border border-marco bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-3 py-2 flex items-center gap-3 text-left hover:bg-white transition-colors"
        aria-expanded={open}
      >
        <span className="text-lg leading-none">{sku.emoji ?? '📦'}</span>
        <div className="min-w-0 flex-1">
          <div className="text-tinta text-[12px] font-semibold truncate">
            {sku.producto ?? sku.sku}
          </div>
          <div className="text-[10px] text-humo truncate">
            {sku.sku} · {sku.marca ?? '—'} · {sku.pdv_afectados} PDV
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[10px] text-humo">disponibilidad</div>
          <div className="text-[12px] text-red-600 font-bold tabular-nums">
            {fmtDecimal(sku.disponibilidad_pct)}%
          </div>
          <div className="text-[10px] text-dn-600">{fmtPP(sku.brecha_pp)} vs meta</div>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-humo transition-transform shrink-0 ${open ? 'rotate-180' : ''}`}
          strokeWidth={1.8}
        />
      </button>

      {open && (
        <div className="border-t border-marco bg-nieve px-3 py-3">
          {loading && (
            <div className="flex items-center gap-2 text-grafito text-[11px]">
              <Loader2 className="w-3 h-3 animate-spin" /> Cargando detalle del SKU…
            </div>
          )}
          {err && <div className="text-red-600 text-xs">{err}</div>}
          {detalle && <SkuDetallePanel detalle={detalle} />}
        </div>
      )}
    </div>
  );
}

function SkuDetallePanel({ detalle }: { detalle: SkuDetalle }) {
  const a = detalle.anaquel;
  const precioMasAlto = detalle.precio.reduce(
    (max, p) => (p.indice_precio > (max?.indice_precio ?? 0) ? p : max),
    detalle.precio[0],
  );

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-2">
        <MiniStat label="Lecturas" value={fmtNumber(a.lecturas ?? 0)} />
        <MiniStat label="PDV" value={fmtNumber(a.pdv ?? 0)} />
        <MiniStat label="Planograma" value={`${fmtDecimal(a.planograma_pct ?? 0)}%`} />
        <MiniStat label="Caras prom." value={fmtDecimal(a.facings_prom ?? 0)} />
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wider text-humo mb-1">
          Índice de precio por cadena
        </div>
        <div className="space-y-1">
          {detalle.precio.slice(0, 5).map((p, i) => (
            <PrecioRow
              key={`${p.country_code}-${p.cadena}-${i}`}
              nombre={`${bandera(p.country_code)} ${p.cadena}`}
              precio={p.precio_usd}
              indice={p.indice_precio}
              enPromo={p.en_promo}
            />
          ))}
          {detalle.precio.length === 0 && (
            <div className="text-[11px] text-humo">
              Sin snapshots recientes de precio para este SKU.
            </div>
          )}
        </div>
        {precioMasAlto && precioMasAlto.indice_precio > 108 && (
          <div className="text-[11px] text-orange-600 mt-1.5">
            ⚠ En {precioMasAlto.cadena} el SKU está {Math.round(precioMasAlto.indice_precio - 100)}%
            por encima del promedio de su subcategoría.
          </div>
        )}
      </div>

      {detalle.peores_pdv.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider text-humo mb-1">
            PDV con peor disponibilidad
          </div>
          <div className="space-y-1">
            {detalle.peores_pdv.slice(0, 4).map((p) => (
              <div
                key={p.store_id}
                className="flex items-center justify-between gap-2 rounded border border-marco bg-white px-2.5 py-1.5 text-[11.5px]"
              >
                <div className="min-w-0">
                  <div className="text-tinta truncate">
                    {bandera(p.country_code ?? '')} {p.tienda ?? p.store_id}
                  </div>
                  <div className="text-[10px] text-humo truncate">
                    {p.cadena ?? '—'} · {p.ciudad ?? '—'}
                    {p.mercaderista ? ` · ${p.mercaderista}` : ''}
                  </div>
                </div>
                <span className="text-red-600 font-bold tabular-nums shrink-0">
                  {fmtDecimal(p.disponibilidad_pct)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MiniStat({
  label,
  value,
  subline,
  tone,
}: {
  label: string;
  value: string;
  subline?: string;
  tone?: 'ok' | 'warn';
}) {
  return (
    <div className="rounded border border-marco bg-white px-2 py-1.5">
      <div className="text-[9.5px] uppercase tracking-wider text-humo">{label}</div>
      <div className="text-[12.5px] font-bold tabular-nums text-tinta">{value}</div>
      {subline && (
        <div className={['text-[10px]', tone === 'warn' ? 'text-red-600' : 'text-humo'].join(' ')}>
          {subline}
        </div>
      )}
    </div>
  );
}

function PrecioRow({
  nombre,
  precio,
  indice,
  enPromo,
}: {
  nombre: string;
  precio: number;
  indice: number;
  enPromo: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded text-[11.5px] border border-marco bg-white text-tinta">
      <div className="flex items-center gap-2 min-w-0">
        <span className="truncate">{nombre}</span>
        {enPromo && (
          <span className="text-[10px] text-emerald-600 bg-emerald-500/10 rounded px-1">promo</span>
        )}
      </div>
      <div className="text-right shrink-0 flex items-baseline gap-2">
        <span className="font-bold tabular-nums">{fmtPrecio(precio)}</span>
        <span
          className={[
            'text-[10px] tabular-nums',
            indice > 108 ? 'text-red-600' : indice < 95 ? 'text-emerald-600' : 'text-humo',
          ].join(' ')}
        >
          idx {Math.round(indice)}
        </span>
      </div>
    </div>
  );
}

/** Markdown mínimo: `## títulos` y párrafos. Tolera texto a medio llegar. */
function ExplanationRender({ markdown, streaming }: { markdown: string; streaming: boolean }) {
  const blocks = useMemo(() => splitBlocks(markdown), [markdown]);
  return (
    <div className="text-[13px] leading-relaxed text-tinta space-y-3">
      {blocks.map((b, i) => {
        if (b.kind === 'h2') {
          return (
            <div
              key={i}
              className="text-[10.5px] uppercase tracking-[0.22em] text-dn-600 font-semibold pt-1"
            >
              {b.text}
            </div>
          );
        }
        return (
          <p key={i} className="whitespace-pre-wrap">
            {b.text}
            {streaming && i === blocks.length - 1 && (
              <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-dn-400 animate-pulse align-middle" />
            )}
          </p>
        );
      })}
    </div>
  );
}

function splitBlocks(md: string): Array<{ kind: 'h2' | 'p'; text: string }> {
  if (!md) return [];
  const out: Array<{ kind: 'h2' | 'p'; text: string }> = [];
  const lines = md.split('\n');
  let buf: string[] = [];
  const flush = () => {
    if (buf.length === 0) return;
    const joined = buf.join('\n').trim();
    if (joined) out.push({ kind: 'p', text: joined });
    buf = [];
  };
  for (const line of lines) {
    if (line.startsWith('## ')) {
      flush();
      out.push({ kind: 'h2', text: line.slice(3).trim() });
    } else {
      buf.push(line);
    }
  }
  flush();
  return out;
}

void AlertTriangle;
void LayoutGrid;
