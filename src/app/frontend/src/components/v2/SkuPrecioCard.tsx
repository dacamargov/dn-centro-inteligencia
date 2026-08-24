import {
  AlertTriangle, ArrowRight, Check, ChevronDown, Megaphone, Sparkles, TrendingUp, X, Zap,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { BrechaPrecio } from '../../lib/api';
import { bandera, fmtDecimal, fmtPrecio } from '../../lib/format';

// Supuestos del simulador. Son reglas de dedo de categoría, no un modelo
// entrenado: sirven para que la conversación de precio tenga números, y están
// declarados acá arriba para que se puedan discutir con el cliente.
const RATIO_COSTO = 0.68;   // margen bruto de partida sobre PVP: 32%
const ELASTICIDAD = 1.4;    // sensibilidad del volumen al precio propio

// La banda justa que usa D&N en sus informes: índice 100 es el promedio de la
// subcategoría por unidad de contenido. La ventana óptima se queda adentro con
// un premium chico, que es lo que sostiene una marca líder sin salirse del set.
const BANDA_OPTIMA = { min: 98, max: 106 };

type AccionTomada =
  | null
  | { tipo: 'precio'; precio: number }
  | { tipo: 'promo'; descuentoPct: number; duracion: string; precio: number }
  | { tipo: 'escalar' }
  | { tipo: 'descartar' };

function simular(P: number, P0: number, C: number) {
  const volRel = Math.pow(P0 / P, ELASTICIDAD);
  const ingresoRel = (P * volRel) / P0;
  const resultadoBase = P0 - C;
  const resultadoNuevo = (P - C) * volRel;
  return {
    volumenDeltaPct: (volRel - 1) * 100,
    ingresoDeltaPct: (ingresoRel - 1) * 100,
    resultadoDeltaPct: (resultadoNuevo / resultadoBase - 1) * 100,
    margenPct: ((P - C) / P) * 100,
  };
}

function Metrica({
  label,
  valor,
  bueno,
  ayuda,
}: {
  label: string;
  valor: number;
  bueno: boolean;
  ayuda?: string;
}) {
  const color = bueno ? '#059669' : '#dc2626';
  return (
    <div className="flex-1 min-w-0" title={ayuda}>
      <div className="text-[9px] uppercase tracking-widest text-humo mb-1 truncate">{label}</div>
      <div className="text-base font-semibold tabular-nums" style={{ color }}>
        {valor > 0 ? '+' : ''}
        {valor.toFixed(1)}%
      </div>
    </div>
  );
}

interface Props {
  sku: BrechaPrecio;
  rank: number;
}

export default function SkuPrecioCard({ sku, rank }: Props) {
  const P0 = sku.precio_usd;
  const Pr = sku.precio_rival_usd;
  const C = RATIO_COSTO * P0;

  // El índice ya viene calculado contra el promedio de la subcategoría, así que
  // el precio de paridad se despeja de ahí en vez de volver a pedirlo al backend.
  const paridad = sku.indice_precio > 0 ? (P0 / sku.indice_precio) * 100 : P0;
  const optimoLo = paridad * (BANDA_OPTIMA.min / 100);
  const optimoHi = paridad * (BANDA_OPTIMA.max / 100);

  const min = Math.min(optimoLo * 0.94, Pr ? Pr * 0.94 : P0 * 0.8, P0 * 0.8);
  const max = Math.max(P0 * 1.08, optimoHi * 1.04);
  const paso = Math.max(0.01, Number(((max - min) / 200).toFixed(2)));

  const [abierto, setAbierto] = useState(false);
  const [precio, setPrecio] = useState<number>(() =>
    Math.min(P0, Math.max(optimoLo, Math.min(optimoHi, P0))),
  );
  const [promoAbierta, setPromoAbierta] = useState(false);
  const [tomada, setTomada] = useState<AccionTomada>(null);

  const sim = useMemo(() => simular(precio, P0, C), [precio, P0, C]);
  const indice = paridad > 0 ? (precio / paridad) * 100 : 0;
  const enVentana = indice >= BANDA_OPTIMA.min && indice <= BANDA_OPTIMA.max;

  const simBanda = useMemo(() => simular(optimoHi, P0, C), [optimoHi, P0, C]);
  const simRival = useMemo(() => (Pr ? simular(Pr, P0, C) : null), [Pr, P0, C]);

  const pos = (v: number) => ((v - min) / (max - min)) * 100;
  const sev = sku.indice_precio >= 115 ? '#dc2626' : sku.indice_precio >= 108 ? '#ea580c' : '#0D5CAB';

  return (
    <article
      className="relative rounded-xl border border-marco bg-white overflow-hidden"
      style={{ boxShadow: `inset 4px 0 0 0 ${sev}` }}
    >
      <div className="px-5 py-4">
        <div className="flex items-start gap-3">
          <div className="text-[10px] uppercase tracking-[0.22em] text-humo font-bold tabular-nums pt-1">
            #{rank}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-[11px] mb-1 flex-wrap">
              <span className="font-mono text-humo bg-nieve px-1.5 py-0.5 rounded">{sku.sku}</span>
              <span className="text-humo uppercase tracking-widest text-[10px]">
                {sku.subcategoria}
              </span>
              <span className="text-humo text-[10px]">
                {bandera(sku.country_code)} {sku.cadena}
              </span>
              {sku.en_promo && (
                <span className="text-[10px] uppercase tracking-widest text-emerald-700 font-semibold">
                  en promo
                </span>
              )}
            </div>
            <h3 className="text-[15px] font-semibold text-tinta leading-snug line-clamp-1 mb-3">
              {sku.emoji ? `${sku.emoji} ` : ''}
              {sku.producto ?? sku.sku}
            </h3>

            <div className="flex items-center gap-2 text-[13px] flex-wrap">
              <div className="rounded-md bg-dn-50 border border-dn-600/30 px-2.5 py-1">
                <div className="text-[9px] uppercase tracking-widest text-dn-600/80">
                  {sku.marca}
                </div>
                <div className="text-dn-600 font-semibold tabular-nums leading-none mt-0.5">
                  {fmtPrecio(P0)}
                </div>
              </div>
              {Pr != null && (
                <>
                  <ArrowRight className="w-4 h-4 text-humo" strokeWidth={2} />
                  <div className="rounded-md border border-marco bg-nieve px-2.5 py-1">
                    <div className="text-[9px] uppercase tracking-widest text-humo">
                      {sku.marca_rival ?? 'rival'}
                    </div>
                    <div className="text-grafito font-semibold tabular-nums leading-none mt-0.5">
                      {fmtPrecio(Pr)}
                    </div>
                  </div>
                </>
              )}
              <div className="rounded-md border border-marco bg-nieve px-2.5 py-1">
                <div className="text-[9px] uppercase tracking-widest text-humo">paridad</div>
                <div className="text-grafito font-semibold tabular-nums leading-none mt-0.5">
                  {fmtPrecio(paridad)}
                </div>
              </div>
            </div>

            {!tomada ? (
              <div className="mt-3 text-[12px] text-grafito leading-snug">
                Está{' '}
                <span className="font-semibold tabular-nums text-red-600">
                  {fmtDecimal(sku.indice_precio - 100)}%
                </span>{' '}
                por encima del promedio de {sku.subcategoria} por unidad de contenido
                {sku.fabricante_rival ? ` · rival directo ${sku.fabricante_rival}` : ''}.
              </div>
            ) : (
              <div className="mt-3 flex items-center gap-2 text-[12px] text-emerald-700 leading-snug flex-wrap">
                <Check className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={2.5} />
                {tomada.tipo === 'precio' && (
                  <>
                    PVP sugerido a{' '}
                    <span className="font-semibold tabular-nums">{fmtPrecio(tomada.precio)}</span> —
                    enviado a la cadena.
                  </>
                )}
                {tomada.tipo === 'promo' && (
                  <>
                    Promoción <span className="font-semibold">{tomada.descuentoPct}% off</span> ·{' '}
                    {tomada.duracion} · góndola a{' '}
                    <span className="font-semibold tabular-nums">{fmtPrecio(tomada.precio)}</span> —
                    en cola de activación.
                  </>
                )}
                {tomada.tipo === 'escalar' && <>Escalado al KAM de la cadena.</>}
                {tomada.tipo === 'descartar' && (
                  <>SKU marcado como premium aceptable — fuera de alertas por 24 h.</>
                )}
                <button
                  onClick={() => setTomada(null)}
                  className="ml-auto text-humo hover:text-tinta text-[11px]"
                >
                  deshacer
                </button>
              </div>
            )}
          </div>

          <div className="flex flex-col items-end text-right shrink-0">
            <TrendingUp className="w-4 h-4" strokeWidth={2.5} style={{ color: sev }} />
            <div className="text-3xl font-bold tabular-nums leading-none" style={{ color: sev }}>
              {fmtDecimal(sku.indice_precio)}
            </div>
            <div className="text-[10px] uppercase tracking-widest text-humo mt-1">
              índice de precio
            </div>
            {abierto ? (
              <button
                onClick={() => setAbierto(false)}
                className="mt-2 inline-flex items-center gap-1 text-[10px] uppercase tracking-widest text-humo hover:text-tinta font-semibold"
              >
                <X className="w-3 h-3" strokeWidth={2.5} />
                cerrar
              </button>
            ) : (
              <button
                onClick={() => setAbierto(true)}
                className="mt-2 group relative inline-flex items-center gap-1.5 pl-2.5 pr-2 py-1.5 rounded-full
                           bg-dn-600 hover:bg-dn-700 text-white text-[10px] uppercase tracking-[0.18em]
                           font-black animate-agent-glow transition-colors overflow-hidden"
                aria-label="Abrir el simulador del agente de precio"
              >
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 bg-gradient-to-r
                             from-transparent via-white/40 to-transparent skew-x-[-20deg]
                             group-hover:translate-x-[400%] translate-x-0 transition-transform duration-700"
                />
                <Sparkles className="w-3.5 h-3.5 animate-agent-sparkle" strokeWidth={2.75} />
                Agente de precio
                <ChevronDown className="w-3 h-3" strokeWidth={2.75} />
              </button>
            )}
          </div>
        </div>
      </div>

      {abierto && (
        <div className="border-t border-marco bg-nieve px-5 py-4 space-y-4">
          <div>
            <div className="flex items-baseline justify-between mb-2 gap-3 flex-wrap">
              <div className="text-[10px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-dn-600" strokeWidth={2.5} />
                Simular PVP
              </div>
              <div className="text-grafito text-[11px]">
                ventana óptima · índice {BANDA_OPTIMA.min}–{BANDA_OPTIMA.max} ·{' '}
                <span className="text-dn-600 font-semibold tabular-nums">
                  {fmtPrecio(optimoLo)}–{fmtPrecio(optimoHi)}
                </span>
              </div>
            </div>

            <div className="relative h-10">
              <div
                className="absolute top-3 h-4 rounded-sm bg-emerald-500/15 border border-emerald-600/40 pointer-events-none"
                style={{
                  left: `${pos(optimoLo)}%`,
                  width: `${Math.max(0.5, pos(optimoHi) - pos(optimoLo))}%`,
                }}
              />
              {Pr != null && (
                <div
                  className="absolute top-1 bottom-1 w-px bg-grafito pointer-events-none"
                  style={{ left: `${pos(Pr)}%` }}
                />
              )}
              <div
                className="absolute top-1 bottom-1 w-px bg-dn-600 pointer-events-none"
                style={{ left: `${pos(P0)}%` }}
              />
              <input
                type="range"
                min={min}
                max={max}
                step={paso}
                value={precio}
                onChange={(e) => setPrecio(parseFloat(e.target.value))}
                className="absolute inset-x-0 top-3 h-4 w-full appearance-none bg-transparent cursor-pointer
                  [&::-webkit-slider-runnable-track]:h-1
                  [&::-webkit-slider-runnable-track]:rounded-full
                  [&::-webkit-slider-runnable-track]:bg-marco
                  [&::-webkit-slider-thumb]:appearance-none
                  [&::-webkit-slider-thumb]:h-4
                  [&::-webkit-slider-thumb]:w-4
                  [&::-webkit-slider-thumb]:rounded-full
                  [&::-webkit-slider-thumb]:bg-dn-600
                  [&::-webkit-slider-thumb]:shadow-[0_0_0_4px_rgba(13,92,171,0.18)]
                  [&::-webkit-slider-thumb]:-mt-1.5
                  [&::-webkit-slider-thumb]:cursor-grab
                  [&::-webkit-slider-thumb]:active:cursor-grabbing"
              />
            </div>

            <div className="flex items-center justify-between mt-1 text-[10px] tabular-nums text-humo">
              <span>{fmtPrecio(min)}</span>
              <span className="flex items-center gap-2">
                <span className="text-dn-600 text-base font-semibold tabular-nums">
                  {fmtPrecio(precio)}
                </span>
                <span
                  className={`text-[10px] uppercase tracking-widest font-semibold ${
                    enVentana ? 'text-emerald-700' : 'text-humo'
                  }`}
                >
                  índice {fmtDecimal(indice)}
                  {enVentana ? ' · en ventana' : ''}
                </span>
              </span>
              <span>{fmtPrecio(max)}</span>
            </div>

            <div className="flex items-center justify-end gap-3 mt-1 text-[9px] uppercase tracking-widest text-humo flex-wrap">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-3 h-2 rounded-sm bg-emerald-500/25 border border-emerald-600/40" />
                ventana óptima
              </span>
              {Pr != null && (
                <span className="inline-flex items-center gap-1">
                  <span className="inline-block w-2 h-px bg-grafito" />
                  rival {fmtPrecio(Pr)}
                </span>
              )}
              <span className="inline-flex items-center gap-1">
                <span className="inline-block w-2 h-px bg-dn-600" />
                actual {fmtPrecio(P0)}
              </span>
            </div>
          </div>

          {/* Todos los deltas comparan el escenario del slider contra sostener
              el PVP de hoy. */}
          <div className="flex items-center gap-4 px-4 py-3 rounded-lg bg-white border border-marco">
            <div
              className="flex-1 min-w-0"
              title="Margen bruto sobre el PVP simulado, con costo al 68% del precio de hoy"
            >
              <div className="text-[9px] uppercase tracking-widest text-humo mb-1 truncate">
                margen
              </div>
              <div className="text-base font-semibold tabular-nums text-tinta">
                {sim.margenPct.toFixed(1)}%
              </div>
            </div>
            <div className="w-px h-8 bg-marco" />
            <Metrica
              label="Δ volumen"
              valor={sim.volumenDeltaPct}
              bueno={sim.volumenDeltaPct >= 0}
              ayuda="Unidades proyectadas con elasticidad ε=1.4 frente al PVP actual."
            />
            <div className="w-px h-8 bg-marco" />
            <Metrica
              label="Δ ingreso"
              valor={sim.ingresoDeltaPct}
              bueno={sim.ingresoDeltaPct >= 0}
              ayuda="Ingreso (precio × volumen) proyectado contra el escenario actual."
            />
            <div className="w-px h-8 bg-marco" />
            <Metrica
              label="Δ resultado"
              valor={sim.resultadoDeltaPct}
              bueno={sim.resultadoDeltaPct >= 0}
              ayuda="Resultado (margen × volumen) proyectado. Negativo = se pierde plata contra sostener el precio."
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setPrecio(optimoHi)}
              className="px-3 py-2 rounded-lg border border-emerald-600/40 bg-emerald-50 hover:bg-emerald-100 transition-colors text-left"
              title="Techo de la ventana: entra en banda conservando todo el premium que la banda permite."
            >
              <div className="text-[9px] uppercase tracking-widest text-emerald-700 mb-0.5">
                entrar en banda {fmtPrecio(optimoHi)}
              </div>
              <div className="text-xs font-semibold tabular-nums text-tinta">
                margen {simBanda.margenPct.toFixed(1)}% ·{' '}
                <span
                  style={{ color: simBanda.resultadoDeltaPct >= 0 ? '#059669' : '#dc2626' }}
                >
                  resultado {simBanda.resultadoDeltaPct >= 0 ? '+' : ''}
                  {simBanda.resultadoDeltaPct.toFixed(1)}%
                </span>
              </div>
            </button>
            <button
              onClick={() => Pr != null && setPrecio(Pr)}
              disabled={Pr == null}
              className="px-3 py-2 rounded-lg border border-marco bg-white hover:bg-nieve transition-colors text-left disabled:opacity-50"
              title="Igualar al rival directo: recupera share ya mismo, pero es el escenario que más margen cede."
            >
              <div className="text-[9px] uppercase tracking-widest text-humo mb-0.5">
                igualar rival {Pr != null ? fmtPrecio(Pr) : '—'}
              </div>
              <div className="text-xs font-semibold tabular-nums text-tinta">
                {simRival ? (
                  <>
                    margen {simRival.margenPct.toFixed(1)}% ·{' '}
                    <span
                      style={{ color: simRival.resultadoDeltaPct >= 0 ? '#059669' : '#dc2626' }}
                    >
                      resultado {simRival.resultadoDeltaPct >= 0 ? '+' : ''}
                      {simRival.resultadoDeltaPct.toFixed(1)}%
                    </span>
                  </>
                ) : (
                  <span className="text-humo font-normal">sin rival medido en esta cadena</span>
                )}
              </div>
            </button>
          </div>

          <div className="text-[10px] text-humo italic px-1 -mt-1">
            ⓘ Elasticidad ε=1.4 contra el precio propio y costo al 68% del PVP. Modelo
            simplificado: no captura la fuga hacia el rival cuando la brecha se sostiene
            varios ciclos.
          </div>

          {promoAbierta ? (
            <FormularioPromo
              precioBase={P0}
              onCancelar={() => setPromoAbierta(false)}
              onConfirmar={(descuentoPct, duracion) => {
                setTomada({
                  tipo: 'promo',
                  descuentoPct,
                  duracion,
                  precio: P0 * (1 - descuentoPct / 100),
                });
                setPromoAbierta(false);
              }}
            />
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setTomada({ tipo: 'precio', precio })}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-dn-600 hover:bg-dn-700 text-white text-xs font-semibold transition-colors"
              >
                <Zap className="w-3.5 h-3.5" strokeWidth={2.5} />
                Aplicar {fmtPrecio(precio)}
              </button>
              <button
                onClick={() => setPromoAbierta(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-dn-600/40 bg-dn-50 text-dn-600 text-xs font-medium hover:bg-dn-100 transition-colors"
              >
                <Megaphone className="w-3.5 h-3.5" strokeWidth={2} />
                Generar promoción
              </button>
              <button
                onClick={() => setTomada({ tipo: 'escalar' })}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-marco text-grafito text-xs hover:border-humo hover:text-tinta transition-colors"
              >
                <AlertTriangle className="w-3.5 h-3.5" strokeWidth={2} />
                Escalar al KAM
              </button>
              <button
                onClick={() => setTomada({ tipo: 'descartar' })}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-humo text-xs hover:text-grafito ml-auto transition-colors"
              >
                <X className="w-3.5 h-3.5" strokeWidth={2} />
                Descartar
              </button>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function FormularioPromo({
  precioBase,
  onCancelar,
  onConfirmar,
}: {
  precioBase: number;
  onCancelar: () => void;
  onConfirmar: (descuentoPct: number, duracion: string) => void;
}) {
  const [descuento, setDescuento] = useState(15);
  const [duracion, setDuracion] = useState('2 semanas');
  // La medición de anaquel es semanal, así que una promo de horas no se vería
  // en ningún ciclo. Las duraciones son las que negocia trade marketing.
  const duraciones = ['1 semana', '2 semanas', '1 mes', 'temporada'];
  const descuentos = [10, 15, 20, 30];
  const precioGondola = precioBase * (1 - descuento / 100);

  return (
    <div className="rounded-lg border border-dn-600/30 bg-dn-50 px-4 py-3 space-y-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-dn-600 font-semibold">
        <Megaphone className="w-3 h-3" strokeWidth={2.5} />
        Nueva promoción en góndola
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-widest text-humo mr-1">descuento</span>
          {descuentos.map((d) => (
            <button
              key={d}
              onClick={() => setDescuento(d)}
              className={[
                'px-2.5 py-1 rounded text-xs tabular-nums font-semibold transition-colors',
                descuento === d
                  ? 'bg-dn-600 text-white'
                  : 'bg-white border border-marco text-grafito hover:text-tinta hover:border-dn-300',
              ].join(' ')}
            >
              {d}%
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] uppercase tracking-widest text-humo mr-1">duración</span>
          {duraciones.map((d) => (
            <button
              key={d}
              onClick={() => setDuracion(d)}
              className={[
                'px-2.5 py-1 rounded text-xs font-medium transition-colors',
                duracion === d
                  ? 'bg-tinta text-white'
                  : 'bg-white border border-marco text-grafito hover:text-tinta hover:border-dn-300',
              ].join(' ')}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="text-[11px] text-grafito">
        Góndola a{' '}
        <span className="font-semibold tabular-nums text-dn-600">{fmtPrecio(precioGondola)}</span>{' '}
        durante {duracion} · el cliente ahorra{' '}
        <span className="font-semibold tabular-nums">
          {fmtPrecio(precioBase - precioGondola)}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => onConfirmar(descuento, duracion)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-dn-600 hover:bg-dn-700 text-white text-xs font-semibold"
        >
          <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
          Lanzar promoción
        </button>
        <button onClick={onCancelar} className="text-humo hover:text-grafito text-xs">
          cancelar
        </button>
      </div>
    </div>
  );
}
