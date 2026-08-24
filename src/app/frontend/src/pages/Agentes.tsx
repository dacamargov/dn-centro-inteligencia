import { useEffect, useMemo, useState } from 'react';
import AgentPersona from '../components/v2/AgentPersona';
import PrecioPromoDetail from '../components/v2/PrecioPromoDetail';
import QueueStrip from '../components/v2/QueueStrip';
import PulsoEjecucionDetail from '../components/v2/PulsoEjecucionDetail';
import RedAbastecimientoDetail from '../components/v2/RedAbastecimientoDetail';
import SentimientoMarcaDetail from '../components/v2/SentimientoMarcaDetail';
import DecisionTimeline from '../components/DecisionTimeline';
import HeroRecommendation from '../components/HeroRecommendation';
import { api, Kpis, Recomendacion, Severity } from '../lib/api';
import { AGENT_META } from '../lib/icons';

const AGENTS = [
  'pulso_ejecucion',
  'price_promo',
  'sentimiento_marca',
  'red_abastecimiento',
] as const;

const SEV_RANK: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1 };

export default function Agents() {
  const [recs, setRecs] = useState<Recomendacion[]>([]);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [agentFilter, setAgentFilter] = useState<string>('');
  const [overrideHeroId, setOverrideHeroId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [r, k] = await Promise.all([
          api.recomendaciones(undefined, 80),
          api.kpis().catch(() => null),
        ]);
        if (!active) return;
        setRecs(r);
        setKpis(k);
        setError(null);
      } catch (e: any) {
        if (active) setError(e?.message ?? String(e));
      }
    };
    tick();
    const id = setInterval(tick, 10000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const decide = async (id: string, action: 'APPROVED' | 'REJECTED') => {
    try {
      await api.decidir(id, action);
      setRecs((cur) =>
        cur.map((r) =>
          r.id === id
            ? { ...r, status: action.toLowerCase() as 'approved' | 'rejected',
                decision: { action, actor: 'tú', occurred_at: new Date().toISOString() } }
            : r,
        ),
      );
      if (overrideHeroId === id) setOverrideHeroId(null);
    } catch (e: any) {
      alert(`Error al registrar la decisión: ${e?.message ?? e}`);
    }
  };

  const recsByAgent = useMemo(() => {
    const m: Record<string, Recomendacion[]> = {};
    for (const a of AGENTS) m[a] = [];
    for (const r of recs) {
      if (m[r.agent_name]) m[r.agent_name].push(r);
    }
    return m;
  }, [recs]);

  const pending = useMemo(() => {
    const items = recs.filter((r) => r.status === 'pending');
    return agentFilter ? items.filter((r) => r.agent_name === agentFilter) : items;
  }, [recs, agentFilter]);

  const hero = useMemo<Recomendacion | null>(() => {
    if (overrideHeroId) {
      const o = pending.find((r) => r.id === overrideHeroId);
      if (o) return o;
    }
    if (pending.length === 0) return null;
    return [...pending].sort((a, b) => {
      const s = (SEV_RANK[b.severity] ?? 0) - (SEV_RANK[a.severity] ?? 0);
      if (s !== 0) return s;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    })[0];
  }, [pending, overrideHeroId]);

  const queue = useMemo(() => {
    if (!hero) return pending;
    return pending.filter((r) => r.id !== hero.id);
  }, [pending, hero]);

  const decided = useMemo(() => {
    return recs
      .filter((r) => r.status !== 'pending')
      .sort((a, b) => {
        const ta = new Date(a.decision?.occurred_at ?? a.created_at).getTime();
        const tb = new Date(b.decision?.occurred_at ?? b.created_at).getTime();
        return tb - ta;
      });
  }, [recs]);

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      {/* Header */}
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[10px] uppercase tracking-[0.25em] text-dn-600/80 font-bold mb-1">
            Sala de agentes
          </div>
          <h1 className="text-2xl font-semibold text-tinta leading-tight">
            Tu equipo de IA trabajando ahora
          </h1>
          <p className="text-xs text-humo mt-0.5">
            {AGENTS.length} agentes Mosaic AI analizando datos cada 2 min · {pending.length} acciones
            esperando decisión
          </p>
        </div>
        {agentFilter && (
          <button
            onClick={() => setAgentFilter('')}
            className="text-[11px] text-dn-600 hover:text-dn-600 self-center"
          >
            ↺ limpiar filtro
          </button>
        )}
      </header>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-600 text-sm rounded p-3">
          {error}
        </div>
      )}

      {/* AGENT PERSONAS — 3 cards side by side, click filters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {AGENTS.map((a) => {
          const meta = AGENT_META[a];
          return (
            <AgentPersona
              key={a}
              name={meta.name}
              Icon={meta.Icon}
              color={meta.color}
              tagline={meta.tagline}
              recs={recsByAgent[a] ?? []}
              active={agentFilter === a}
              onClick={() => setAgentFilter(agentFilter === a ? '' : a)}
            />
          );
        })}
      </div>

      {/* HERO — single most-urgent rec to act on now */}
      {hero ? (
        <HeroRecommendation rec={hero} kpis={kpis} onDecide={decide} />
      ) : (
        <section className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-12 text-center">
          <div className="text-4xl mb-3">🟢</div>
          <div className="text-emerald-700 text-base font-semibold">
            Todo bajo control
          </div>
          <div className="text-[12px] text-emerald-600/70 mt-1">
            Sin acciones pendientes · los agentes analizan el próximo ciclo (2 min)
          </div>
        </section>
      )}

      {/* AGENT-SPECIFIC DRILL-DOWN — appears when an agent is selected */}
      {agentFilter === 'pulso_ejecucion' && <PulsoEjecucionDetail />}
      {agentFilter === 'price_promo' && <PrecioPromoDetail />}
      {agentFilter === 'sentimiento_marca' && <SentimientoMarcaDetail />}
      {agentFilter === 'red_abastecimiento' && <RedAbastecimientoDetail />}

      {/* QUEUE — horizontal strip, not a list */}
      <QueueStrip items={queue} kpis={kpis} onPromote={setOverrideHeroId} />

      {/* DECIDED — collapsed by default */}
      {decided.length > 0 && (
        <details className="group rounded-xl border border-marco bg-white overflow-hidden">
          <summary className="px-5 py-3 cursor-pointer flex items-center justify-between text-[11px] uppercase tracking-[0.22em] text-grafito font-semibold list-none hover:bg-white">
            <span>
              Decisiones ya tomadas{' '}
              <span className="text-humo normal-case font-normal tracking-normal">· {decided.length} en esta sesión</span>
            </span>
            <span className="text-humo group-open:rotate-180 transition-transform">▾</span>
          </summary>
          <div className="border-t border-marco [&_section]:border-0 [&_section]:rounded-none [&_section_header]:hidden">
            <DecisionTimeline decided={decided} />
          </div>
        </details>
      )}
    </div>
  );
}
