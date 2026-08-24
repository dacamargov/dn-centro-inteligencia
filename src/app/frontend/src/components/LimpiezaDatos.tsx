import { AlertTriangle, Check, Database, Loader2, Trash2, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api, DemoVolumen, LimpiezaResult, TablaVolumen } from '../lib/api';
import { fmtNumber } from '../lib/format';

const ANCHO_PANEL = 420;

/**
 * Purga de datos simulados, desde el header.
 *
 * Cada generador podaba lo suyo y nada más, así que la mitad de las tablas
 * crecía sin techo entre presentaciones. Este panel muestra el volumen real
 * tabla por tabla y ofrece las dos purgas que tienen sentido: borrar lo que ya
 * salió de la ventana viva —se puede correr con la demo encendida— o vaciar
 * todo para dejar el workspace limpio.
 *
 * El panel se dibuja en un portal sobre el body y no como hijo del botón: la
 * barra del header mide 64 px de alto y es `overflow-hidden` —lo necesita para
 * contener el degradado de fondo—, así que un desplegable absoluto quedaba
 * recortado a la altura de la barra y era imposible verlo ni usarlo.
 */
export default function LimpiezaDatos() {
  const [abierto, setAbierto] = useState(false);
  const [vol, setVol] = useState<DemoVolumen | null>(null);
  const [ocupado, setOcupado] = useState<null | 'ventana' | 'total'>(null);
  const [resultado, setResultado] = useState<LimpiezaResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number; maxHeight: number } | null>(null);
  const ancla = useRef<HTMLButtonElement | null>(null);
  const panel = useRef<HTMLDivElement | null>(null);

  const cargar = useCallback(async () => {
    try {
      setVol(await api.demoVolumen());
      setError(null);
    } catch (e: any) {
      setError(String(e?.message ?? e).slice(0, 140));
    }
  }, []);

  // Al vivir en un portal, la posición hay que calcularla: se ancla al botón y se
  // recalcula si la ventana cambia, para que no quede flotando en el aire.
  const ubicar = useCallback(() => {
    const b = ancla.current?.getBoundingClientRect();
    if (!b) return;
    const margen = 12;
    const left = Math.max(margen, Math.min(b.right - ANCHO_PANEL, window.innerWidth - ANCHO_PANEL - margen));
    setPos({
      top: b.bottom + 8,
      left,
      maxHeight: window.innerHeight - b.bottom - 8 - margen,
    });
  }, []);

  useEffect(() => {
    if (!abierto) return;
    cargar();
    ubicar();
    window.addEventListener('resize', ubicar);
    window.addEventListener('scroll', ubicar, true);
    return () => {
      window.removeEventListener('resize', ubicar);
      window.removeEventListener('scroll', ubicar, true);
    };
  }, [abierto, cargar, ubicar]);

  useEffect(() => {
    if (!abierto) return;
    // El panel ya no es descendiente del botón, así que hay que preguntar por los
    // dos por separado o un clic dentro del propio panel lo cerraría.
    const fuera = (e: MouseEvent) => {
      const t = e.target as Node;
      if (panel.current?.contains(t) || ancla.current?.contains(t)) return;
      setAbierto(false);
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAbierto(false);
    };
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', fuera);
      document.removeEventListener('keydown', escape);
    };
  }, [abierto]);

  const limpiar = async (total: boolean) => {
    if (total && !window.confirm(
      'Vaciar TODAS las tablas simuladas.\n\n' +
      'Los maestros (productos, puntos de venta, metas) se conservan, pero los ' +
      'paneles quedan en blanco hasta que el generador aterrice el próximo lote.\n\n' +
      '¿Continuar?',
    )) return;

    setOcupado(total ? 'total' : 'ventana');
    setResultado(null);
    setError(null);
    try {
      const r = await api.demoLimpiar(total);
      setResultado(r);
      await cargar();
    } catch (e: any) {
      setError(String(e?.message ?? e).slice(0, 140));
    } finally {
      setOcupado(null);
    }
  };

  const total = vol?.filas_total ?? null;

  return (
    <>
      <button
        ref={ancla}
        onClick={() => setAbierto((v) => !v)}
        title="Datos simulados guardados y purga"
        className={[
          'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-medium transition-colors',
          abierto
            ? 'border-white/40 bg-white/20 text-white'
            : 'border-white/25 bg-white/[0.07] text-dn-100 hover:bg-white/15 hover:text-white',
        ].join(' ')}
      >
        <Trash2 className="w-3.5 h-3.5" />
        <span className="hidden md:inline">Limpiar datos</span>
      </button>

      {abierto && pos && createPortal(
        <div
          ref={panel}
          style={{
            top: pos.top,
            left: pos.left,
            width: ANCHO_PANEL,
            maxHeight: pos.maxHeight,
          }}
          className="fixed z-[1000] rounded-xl border border-marco bg-white shadow-2xl overflow-hidden text-left flex flex-col"
        >
          <header className="px-4 py-3 border-b border-marco flex items-start justify-between gap-2 shrink-0">
            <div>
              <h3 className="text-[11px] uppercase tracking-[0.2em] text-grafito font-semibold flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-dn-600" />
                Datos simulados guardados
              </h3>
              <p className="text-[11px] text-humo mt-0.5 leading-snug">
                {total == null
                  ? 'consultando volumen…'
                  : `${fmtNumber(total)} filas en las tablas transitorias. Los maestros no se tocan.`}
              </p>
            </div>
            <button onClick={() => setAbierto(false)} className="text-humo hover:text-tinta p-0.5">
              <X className="w-4 h-4" />
            </button>
          </header>

          {error && (
            <div className="px-4 py-2 bg-red-50 border-b border-red-200 text-[11px] text-red-700 flex items-start gap-1.5 shrink-0">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
              {error}
            </div>
          )}

          <div className="overflow-y-auto flex-1 min-h-[80px]">
            {vol == null ? (
              <div className="px-4 py-8 flex items-center justify-center text-humo text-[12px]">
                <Loader2 className="w-4 h-4 animate-spin mr-2" /> leyendo tablas…
              </div>
            ) : (
              <>
                <Grupo titulo="Unity Catalog · Delta" filas={vol.unity_catalog} />
                {vol.lakebase.length > 0 && (
                  <Grupo titulo="Lakebase · Postgres" filas={vol.lakebase} />
                )}
              </>
            )}
          </div>

          {resultado && (
            <div className="px-4 py-2 bg-emerald-50 border-t border-emerald-200 text-[11px] text-emerald-800 flex items-start gap-1.5 shrink-0">
              <Check className="w-3.5 h-3.5 shrink-0 mt-px" strokeWidth={2.5} />
              <span>
                Purga {resultado.modo === 'total' ? 'total' : 'por ventana'}:{' '}
                <strong>{fmtNumber(resultado.filas_liberadas)}</strong> filas liberadas
                {resultado.filas_restantes != null && (
                  <> · quedan {fmtNumber(resultado.filas_restantes)}</>
                )}
                {resultado.errors.length > 0 && (
                  <span className="text-orange-700"> · {resultado.errors.length} avisos</span>
                )}
              </span>
            </div>
          )}

          <footer className="px-4 py-3 border-t border-marco flex items-center gap-2 shrink-0">
            <button
              onClick={() => limpiar(false)}
              disabled={ocupado !== null}
              className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-dn-600 hover:bg-dn-700 text-white text-[11.5px] font-semibold transition-colors disabled:opacity-50"
            >
              {ocupado === 'ventana' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5" />
              )}
              Purgar lo vencido
            </button>
            <button
              onClick={() => limpiar(true)}
              disabled={ocupado !== null}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-red-300 text-red-700 hover:bg-red-50 text-[11.5px] font-semibold transition-colors disabled:opacity-50"
            >
              {ocupado === 'total' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <AlertTriangle className="w-3.5 h-3.5" />
              )}
              Vaciar todo
            </button>
          </footer>
          <div className="px-4 pb-3 text-[10.5px] text-humo leading-snug shrink-0">
            <strong className="text-grafito">Purgar lo vencido</strong> borra solo las filas
            fuera de su ventana viva; se puede correr con la demo encendida y es lo que conviene
            dejar corriendo entre sesiones. <strong className="text-grafito">Vaciar todo</strong>{' '}
            deja los paneles en blanco hasta el próximo lote del generador. Detener la demo
            también vacía, si aceptas la limpieza.
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}

function Grupo({ titulo, filas }: { titulo: string; filas: TablaVolumen[] }) {
  const total = filas.reduce((a, f) => a + f.filas, 0);
  return (
    <div>
      <div className="px-4 py-1.5 bg-nieve border-y border-marco flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-humo font-semibold">
          {titulo}
        </span>
        <span className="text-[10px] tabular-nums text-humo">{fmtNumber(total)}</span>
      </div>
      <ul className="divide-y divide-marco">
        {filas.map((f) => (
          <li key={f.tabla} className="px-4 py-1.5 flex items-center justify-between gap-2">
            <span className="font-mono text-[11px] text-grafito truncate">{f.tabla}</span>
            <span className="flex items-center gap-2 shrink-0">
              <span className="text-[10px] text-humo">
                {f.ventana_min ? `${f.ventana_min} min` : 'sin ventana'}
              </span>
              <span
                className={[
                  'text-[11.5px] tabular-nums font-semibold w-16 text-right',
                  f.filas === 0 ? 'text-humo' : 'text-tinta',
                ].join(' ')}
              >
                {fmtNumber(f.filas)}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
