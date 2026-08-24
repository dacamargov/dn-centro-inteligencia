// Formateo en español latinoamericano.
//
// La moneda de trabajo es el dólar: la red cubre diez países con monedas distintas, así
// que todo lo comparable (precio de anaquel, impacto de una acción) se normaliza
// a USD. Los montos en moneda local solo aparecen en la ficha del PDV.
const usd = new Intl.NumberFormat('es-PA', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const usdPreciso = new Intl.NumberFormat('es-PA', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const usdCompacto = new Intl.NumberFormat('es-PA', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const dec = new Intl.NumberFormat('es-PA', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const intFmt = new Intl.NumberFormat('es-PA');

export const fmtUSD = (n: number | null | undefined): string =>
  n == null ? '—' : usd.format(n);

/** Precios de anaquel: a dos decimales, porque la diferencia está en los centavos. */
export const fmtPrecio = (n: number | null | undefined): string =>
  n == null ? '—' : usdPreciso.format(n);

export const fmtUSDCompacto = (n: number | null | undefined): string =>
  n == null ? '—' : usdCompacto.format(n);

export const fmtNumber = (n: number | null | undefined): string =>
  n == null ? '—' : intFmt.format(n);

export const fmtDecimal = (n: number | null | undefined): string =>
  n == null ? '—' : dec.format(n);

export const fmtPct = (n: number | null | undefined, signed = true): string => {
  if (n == null) return '—';
  const s = `${dec.format(n)}%`;
  if (!signed) return s;
  return n > 0 ? `+${s}` : s;
};

/** Diferencia en puntos porcentuales — no es lo mismo que un porcentaje. */
export const fmtPP = (n: number | null | undefined): string => {
  if (n == null) return '—';
  const s = `${dec.format(Math.abs(n))} pp`;
  return n > 0 ? `+${s}` : n < 0 ? `−${s}` : s;
};

export function relTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const diff = Math.max(0, (Date.now() - t) / 1000);
  if (diff < 5) return 'ahora';
  if (diff < 60) return `hace ${Math.floor(diff)}s`;
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
  return `hace ${Math.floor(diff / 86400)} d`;
}

export function fmtClock(d = new Date()): string {
  return d.toLocaleTimeString('es-PA', { hour12: false });
}

const BANDERAS: Record<string, string> = {
  PA: '🇵🇦', GT: '🇬🇹', CR: '🇨🇷', SV: '🇸🇻',
  HN: '🇭🇳', NI: '🇳🇮', DO: '🇩🇴',
};

export const bandera = (code: string | null | undefined): string =>
  (code && BANDERAS[code]) || '🌎';
