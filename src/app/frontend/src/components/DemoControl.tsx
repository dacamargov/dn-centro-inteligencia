import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Play, Square } from 'lucide-react';
import { api, DemoStatus } from '../lib/api';
import LimpiezaDatos from './LimpiezaDatos';

/**
 * Global demo lifecycle control shown in the header.
 * - When the jobs are paused: a prominent "Iniciar demo" button.
 * - When running: a green "Demo activa" pill with una acción "Detener".
 * Starting unpauses + triggers the data-gen and agent jobs (data lands in ~1 min).
 */
export default function DemoControl() {
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [busy, setBusy] = useState<null | 'start' | 'stop'>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.demoStatus());
    } catch {
      /* keep last known state on transient failures */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 12000);
    pollRef.current = id;
    return () => window.clearInterval(id);
  }, [refresh]);

  const start = async () => {
    setBusy('start');
    setMsg(null);
    try {
      const r = await api.demoStart();
      const n = r.started?.length ?? 0;
      setMsg(
        r.errors?.length
          ? `Iniciada con avisos (${r.errors.length}).`
          : `Demo iniciada · ${n} jobs · dato en ~1 min`,
      );
      await refresh();
      // El generador tarda en aterrizar el primer lote: reconsultamos unas veces más.
      [15000, 35000, 60000].forEach((t) => window.setTimeout(refresh, t));
    } catch (e: any) {
      setMsg(`No se pudo iniciar: ${String(e?.message ?? e).slice(0, 120)}`);
    } finally {
      setBusy(null);
      window.setTimeout(() => setMsg(null), 8000);
    }
  };

  const stop = async () => {
    if (!window.confirm('¿Detener la demo? Se pausan los seis jobs.')) return;
    // Limpiar es la segunda pregunta a propósito. Borrar el dato deja las
    // gráficas en blanco durante varios minutos tras el siguiente arranque, y
    // eso no es lo que espera quien solo quiere pausar entre reuniones.
    const limpiar = window.confirm(
      '¿Limpiar además el dato de esta presentación?\n\n' +
        'Aceptar pone en cero visitas, precios, posts, recomendaciones y campañas ' +
        '(productos, puntos de venta y metas se conservan).\n\n' +
        'Cancelar deja el dato como está para retomar donde ibas.',
    );
    setBusy('stop');
    setMsg(null);
    try {
      const r = await api.demoStop(limpiar);
      const n = r.wiped?.length ?? 0;
      setMsg(
        r.errors?.length
          ? `Pausada con avisos (${r.errors.length}).`
          : limpiar
            ? `Demo pausada · ${n} tablas limpiadas`
            : 'Demo pausada · dato conservado',
      );
      await refresh();
    } catch (e: any) {
      setMsg(`No se pudo detener: ${String(e?.message ?? e).slice(0, 120)}`);
    } finally {
      setBusy(null);
      window.setTimeout(() => setMsg(null), 6000);
    }
  };

  // Sin jobs de la demo en este workspace, el control no tiene nada que manejar.
  if (status && status.found === 0) return null;

  const running = status?.running ?? false;

  return (
    <div className="flex items-center gap-3">
      {msg && (
        <span className="hidden lg:inline text-[11px] text-dn-200 max-w-[240px] truncate">
          {msg}
        </span>
      )}

      <LimpiezaDatos />

      {running ? (
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 text-emerald-600 text-[10px] uppercase tracking-[0.18em] font-semibold">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Demo activa
          </span>
          <button
            onClick={stop}
            disabled={busy !== null}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-white/25 bg-white/[0.07] text-dn-100 hover:bg-white/15 hover:text-white text-[11px] font-medium transition-colors disabled:opacity-50"
          >
            {busy === 'stop' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Square className="w-3.5 h-3.5" />
            )}
            Detener
          </button>
        </div>
      ) : (
        <button
          onClick={start}
          disabled={busy !== null || status === null}
          className="group inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg font-semibold text-[12px] text-amber-950 bg-gradient-to-r from-amber-300 via-amber-400 to-orange-500 hover:from-amber-200 hover:to-orange-400 shadow-[0_6px_20px_-6px_rgba(51,189,238,0.6)] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {busy === 'start' ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Iniciando…
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              Iniciar demo
            </>
          )}
        </button>
      )}
    </div>
  );
}
