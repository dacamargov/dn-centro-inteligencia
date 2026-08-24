import { useEffect, useState } from 'react';
import { fmtClock } from '../lib/format';
import DemoControl from './DemoControl';

interface Props {
  connected: boolean;
}

export default function Header({ connected }: Props) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const dateStr = now
    .toLocaleDateString('es-PA', { weekday: 'short', day: '2-digit', month: 'short' })
    .toUpperCase();

  return (
    // La barra va en el navy de marca aunque el resto del tablero sea claro: es
    // el mismo contraste que usa dichter-neira.com, y el wordmark oficial que
    // publican es blanco, así que sobre fondo claro no habría logo que poner.
    <header className="relative bg-dn-800 h-16 flex items-center justify-between px-6 overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-dn-400/70 to-transparent" />
      <div className="pointer-events-none absolute -inset-x-32 -top-32 h-64 bg-dn-400/[0.07] blur-3xl" />

      <div className="flex items-center gap-3 z-10">
        <img
          src="/dn-logo-blanco.webp"
          alt="dichter & neira"
          className="h-7 w-auto object-contain"
        />
        <div className="h-8 w-px bg-white/20" />
        <div className="leading-tight">
          <div className="text-white font-semibold tracking-tight text-[15px]">
            Centro de Inteligencia
          </div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-dn-300 mt-0.5">
            Medición continua de mercado · LATAM
          </div>
        </div>
      </div>

      <div className="flex items-center gap-5 z-10">
        <DemoControl />
        <div className="hidden md:block text-[11px] tracking-widest text-dn-300/70 font-mono">
          {dateStr}
        </div>
        <div className="font-mono text-base tabular-nums text-white tracking-wide">
          {fmtClock(now)}
        </div>
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full border border-white/20 bg-white/[0.07]">
          <span className="relative flex h-2 w-2">
            <span
              className={`absolute inset-0 rounded-full ${
                connected ? 'bg-emerald-400 animate-ping opacity-60' : ''
              }`}
            />
            <span
              className={`relative inline-block w-2 h-2 rounded-full ${
                connected ? 'bg-emerald-400' : 'bg-red-500'
              }`}
            />
          </span>
          <span className="text-[10px] uppercase tracking-[0.2em] text-dn-200 font-medium">
            {connected ? 'EN VIVO' : 'SIN SEÑAL'}
          </span>
        </div>
      </div>
    </header>
  );
}
