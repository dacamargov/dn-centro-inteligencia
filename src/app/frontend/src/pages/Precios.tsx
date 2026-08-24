import { Sparkles, Tag, TrendingDown, TrendingUp } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import AgenteEnContexto from '../components/v2/AgenteEnContexto';
import SkuPrecioCard from '../components/v2/SkuPrecioCard';
import { api, BrechaPrecio, PrecioCadena, PrecioCategoria } from '../lib/api';
import { bandera, fmtDecimal } from '../lib/format';
import { peorPorSku } from '../lib/precio';

// El índice se lee siempre contra 100 = promedio de la subcategoría, ya
// normalizado por contenido. Estas bandas son las que D&N usa en sus informes.
const BANDA = {
  caro: 108,
  barato: 95,
};

// Cuántos SKUs suben al simulador. La página es el simulador, así que la lista
// tiene que dar para una conversación entera y no para dos ejemplos.
const CUPO_SIMULADOR = 8;

function indiceColor(idx: number): string {
  if (idx >= BANDA.caro) return '#ef4444';
  if (idx <= BANDA.barato) return '#34d399';
  return '#33bdee';
}

export default function Precios() {
  const [brechas, setBrechas] = useState<BrechaPrecio[]>([]);
  const [porCategoria, setPorCategoria] = useState<PrecioCategoria[]>([]);
  const [porCadena, setPorCadena] = useState<PrecioCadena[]>([]);
  const [categoria, setCategoria] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [b, c, ca] = await Promise.all([
          api.brechasPrecio(categoria || undefined),
          api.preciosPorCategoria(),
          api.preciosPorCadena(categoria || undefined),
        ]);
        if (!active) return;
        setBrechas(b);
        setPorCategoria(c);
        setPorCadena(ca);
        setError(null);
      } catch (e: any) {
        if (active) setError(e?.message ?? String(e));
      }
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [categoria]);

  const categorias = useMemo(
    () => porCategoria.map((c) => c.categoria).sort(),
    [porCategoria],
  );

  // El titular es el índice ponderado por número de SKUs medidos.
  const resumen = useMemo(() => {
    const base = categoria
      ? porCategoria.filter((c) => c.categoria === categoria)
      : porCategoria;
    const skus = base.reduce((a, c) => a + c.skus_cliente, 0);
    if (!skus) return null;
    const idx = base.reduce((a, c) => a + c.indice_cliente * c.skus_cliente, 0) / skus;
    return { idx, skus };
  }, [porCategoria, categoria]);

  const peorCadena = useMemo(
    () => [...porCadena].sort((a, b) => b.indice_cliente - a.indice_cliente)[0] ?? null,
    [porCadena],
  );

  // Un SKU caro suele estarlo en todas las cadenas, así que sin deduplicar el
  // mismo producto ocupa toda la lista. Cada tarjeta es un producto distinto,
  // en la cadena donde peor está.
  const paraSimular = useMemo(
    () => peorPorSku(brechas).slice(0, CUPO_SIMULADOR),
    [brechas],
  );

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.25em] text-dn-600/80 font-bold mb-1">
            Precio
          </div>
          <h1 className="text-2xl font-semibold text-tinta leading-tight">
            Dónde el precio nos está costando el anaquel
          </h1>
          <p className="text-xs text-humo mt-0.5">
            índice normalizado por contenido dentro de cada subcategoría · 100 = promedio del
            mercado
            {categoria && <span className="ml-2 text-dn-600">· {categoria}</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={categoria}
            onChange={(e) => setCategoria(e.target.value)}
            className="bg-white border border-marco text-tinta text-sm rounded-md px-3 py-1.5 focus:border-dn-400 focus:outline-none"
          >
            <option value="">Todas las categorías</option>
            {categorias.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {categoria && (
            <button
              onClick={() => setCategoria('')}
              className="text-[11px] text-dn-600 hover:text-dn-600"
            >
              ↺ limpiar
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-600 text-sm rounded p-3">
          {error}
        </div>
      )}

      {resumen && (
        <PrecioHero
          resumen={resumen}
          peorCadena={peorCadena}
          brechas={paraSimular.length}
        />
      )}

      <AgenteEnContexto agente="price_promo" />

      <section className="space-y-3">
        <header>
          <h2 className="text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-dn-600" strokeWidth={2} />
            Simulador de precio · los SKUs más caros del anaquel
          </h2>
          <p className="text-[11px] text-humo mt-0.5">
            abre el agente en cualquier SKU para mover el PVP dentro de la ventana óptima y
            ver qué le pasa al margen, al volumen y al resultado
          </p>
        </header>
        {paraSimular.length === 0 ? (
          <div className="rounded-xl border border-marco bg-white p-10 text-center text-humo text-sm">
            Ningún SKU por encima de la banda. El precio está alineado con el mercado.
          </div>
        ) : (
          paraSimular.map((b, i) => (
            <SkuPrecioCard
              key={`${b.sku}-${b.cadena}-${b.country_code}`}
              sku={b}
              rank={i + 1}
            />
          ))
        )}
      </section>
    </div>
  );
}

function PrecioHero({
  resumen,
  peorCadena,
  brechas,
}: {
  resumen: { idx: number; skus: number };
  peorCadena: PrecioCadena | null;
  brechas: number;
}) {
  const caro = resumen.idx >= BANDA.caro;
  const barato = resumen.idx <= BANDA.barato;
  const color = indiceColor(resumen.idx);
  const headline = caro
    ? 'Estamos caros frente al anaquel'
    : barato
      ? 'Estamos por debajo del mercado'
      : 'Precio alineado con el mercado';
  const cuerpo = caro
    ? `El índice ponderado es ${resumen.idx.toFixed(1)} sobre ${resumen.skus} SKUs medidos${
        peorCadena
          ? `, y ${peorCadena.cadena} concentra el sobreprecio con ${peorCadena.indice_cliente.toFixed(1)}`
          : ''
      }. Con ${brechas} SKUs por encima de la banda, la exhibición no compensa el diferencial.`
    : barato
      ? `El índice ponderado es ${resumen.idx.toFixed(1)}: hay espacio para recuperar margen sin perder competitividad en el anaquel.`
      : `El índice ponderado es ${resumen.idx.toFixed(1)} sobre ${resumen.skus} SKUs. La posición de precio sostiene la propuesta de valor sin regalar margen.`;

  return (
    <section
      className="relative rounded-2xl border bg-gradient-to-br from-white via-white to-nieve overflow-hidden"
      style={{ borderColor: `${color}55`, boxShadow: `0 30px 80px -30px ${color}33` }}
    >
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, ${color}cc, transparent)` }}
      />
      <div
        className="absolute -top-32 -right-32 w-[400px] h-[400px] rounded-full blur-3xl opacity-30 pointer-events-none"
        style={{ background: color }}
      />
      <div className="relative grid grid-cols-12 gap-6 p-7 items-center">
        <div className="col-span-12 lg:col-span-2 flex flex-col items-start gap-2">
          <div
            className="text-[10px] uppercase tracking-[0.25em] font-bold flex items-center gap-1.5"
            style={{ color }}
          >
            <Tag className="w-3.5 h-3.5" strokeWidth={2.5} />
            índice de precio
          </div>
          <div
            className="w-20 h-20 rounded-2xl flex items-center justify-center"
            style={{
              backgroundColor: `${color}22`,
              border: `1.5px solid ${color}88`,
              boxShadow: `0 0 40px -8px ${color}88`,
              color,
            }}
          >
            {caro ? (
              <TrendingUp className="w-9 h-9" strokeWidth={1.6} />
            ) : (
              <TrendingDown className="w-9 h-9" strokeWidth={1.6} />
            )}
          </div>
          <div className="text-3xl font-bold tabular-nums leading-tight" style={{ color }}>
            {resumen.idx.toFixed(1)}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-7">
          <h1 className="text-[26px] leading-tight font-bold text-tinta tracking-tight mb-2.5">
            {headline}
          </h1>
          <p className="text-[14px] leading-relaxed text-grafito max-w-prose">{cuerpo}</p>
        </div>

        <div className="col-span-12 lg:col-span-3 grid grid-cols-1 gap-3">
          <div className="rounded-xl border border-marco bg-nieve px-3.5 py-2.5">
            <div className="text-[10px] uppercase tracking-widest text-humo mb-1">
              Cadena más cara
            </div>
            <div className="text-xl font-bold tabular-nums text-tinta leading-none">
              {peorCadena ? fmtDecimal(peorCadena.indice_cliente) : '—'}
            </div>
            <div className="text-[10px] text-humo mt-1 truncate">
              {peorCadena
                ? `${bandera(peorCadena.country_code)} ${peorCadena.cadena}`
                : 'sin datos por cadena'}
            </div>
          </div>
          <div className="rounded-xl border border-red-500/30 bg-red-500/[0.06] px-3.5 py-2.5">
            <div className="text-[10px] uppercase tracking-widest text-red-600/80 mb-1">
              SKUs en el simulador
            </div>
            <div className="text-xl font-bold tabular-nums text-red-600 leading-none">
              {brechas}
            </div>
            <div className="text-[10px] text-humo mt-1">índice mayor a {BANDA.caro}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
