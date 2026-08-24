import { Bot, ChevronRight } from 'lucide-react';
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import RecommendationCard from '../RecommendationCard';
import { api, Kpis, Recomendacion, Severity } from '../../lib/api';
import { AGENT_META } from '../../lib/icons';

const SEV_RANK: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1 };

interface Props {
  /** Nombre del agente tal como lo escribe en `recomendaciones.agent_name`. */
  agente: string;
  /** Cuántas recomendaciones pendientes mostrar antes de mandar a la sala. */
  limite?: number;
  /**
   * Tipos de `suggested_action.type` admitidos. Cada pantalla vive en su
   * dominio: la de marca no muestra una acción de reposición aunque la haya
   * escrito su propio agente.
   */
  acciones?: string[];
  /** Botón para ejecutar la recomendación ahí mismo, si la pantalla sabe cómo. */
  accionPrimaria?: (rec: Recomendacion) => ReactNode;
}

/**
 * El agente, trabajando dentro de la pantalla que analiza.
 *
 * La sala de agentes muestra a los tres juntos, que sirve para presentarlos pero
 * no para trabajar: quien está mirando precios quiere decidir sobre precios sin
 * cambiar de pestaña. Este panel trae al agente al contexto y deja aprobar o
 * descartar ahí mismo.
 */
export default function AgenteEnContexto({
  agente,
  limite = 2,
  acciones,
  accionPrimaria,
}: Props) {
  const [recs, setRecs] = useState<Recomendacion[]>([]);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const meta = AGENT_META[agente] ?? {
    Icon: Bot,
    color: '#0D5CAB',
    name: agente,
    tagline: '',
  };

  const clave = acciones?.join(',');
  const cargar = useCallback(async () => {
    try {
      const [r, k] = await Promise.all([
        api.recomendaciones(undefined, 20, agente, clave),
        api.kpis().catch(() => null),
      ]);
      setRecs(r);
      setKpis(k);
    } catch {
      /* el panel es accesorio: si falla, la pantalla sigue sirviendo */
    }
  }, [agente, clave]);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 15000);
    return () => clearInterval(id);
  }, [cargar]);

  const decidir = async (id: string, action: 'APPROVED' | 'REJECTED') => {
    await api.decidir(id, action);
    setRecs((cur) =>
      cur.map((r) =>
        r.id === id
          ? {
              ...r,
              status: action.toLowerCase() as 'approved' | 'rejected',
              decision: { action, actor: 'tú', occurred_at: new Date().toISOString() },
            }
          : r,
      ),
    );
  };

  const pendientes = useMemo(
    () =>
      recs
        .filter((r) => r.status === 'pending')
        .sort((a, b) => {
          const s = (SEV_RANK[b.severity] ?? 0) - (SEV_RANK[a.severity] ?? 0);
          if (s !== 0) return s;
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        }),
    [recs],
  );

  const decididas = recs.length - pendientes.length;
  const visibles = pendientes.slice(0, limite);

  return (
    <section className="rounded-xl border border-marco bg-white overflow-hidden">
      <header className="px-5 py-3.5 border-b border-marco flex items-center gap-3 flex-wrap">
        <span
          className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            backgroundColor: `${meta.color}18`,
            border: `1px solid ${meta.color}55`,
            color: meta.color,
          }}
        >
          <meta.Icon className="w-4.5 h-4.5" strokeWidth={2} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[13px] font-semibold text-tinta leading-tight flex items-center gap-2">
            {meta.name}
            {pendientes.length > 0 && (
              <span
                className="px-1.5 py-px rounded-full text-[10px] font-bold tabular-nums text-white"
                style={{ backgroundColor: meta.color }}
              >
                {pendientes.length}
              </span>
            )}
          </h2>
          <p className="text-[11px] text-humo leading-snug">{meta.tagline}</p>
        </div>
        <Link
          to="/agentes"
          className="inline-flex items-center gap-1 text-[11px] text-dn-600 hover:text-dn-700 font-medium"
        >
          Sala de agentes
          <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </header>

      <div className="p-4 space-y-3">
        {pendientes.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-[13px] text-grafito">
              {decididas > 0
                ? 'Sin pendientes: ya decidiste todo lo que trajo este agente.'
                : 'El agente está analizando. Publica su próxima lectura en 2 minutos.'}
            </div>
            {decididas > 0 && (
              <div className="text-[11px] text-humo mt-1 tabular-nums">
                {decididas} decisión{decididas === 1 ? '' : 'es'} en esta sesión
              </div>
            )}
          </div>
        ) : (
          visibles.map((r) => (
            <RecommendationCard
              key={r.id}
              rec={r}
              kpis={kpis}
              onDecide={decidir}
              accionPrimaria={accionPrimaria?.(r)}
            />
          ))
        )}
        {pendientes.length > visibles.length && (
          <Link
            to="/agentes"
            className="block text-center text-[11px] text-dn-600 hover:text-dn-700 py-1"
          >
            Ver las {pendientes.length - visibles.length} restantes en la sala de agentes →
          </Link>
        )}
      </div>
    </section>
  );
}
