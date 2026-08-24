/**
 * Iconografía compartida: agentes, categorías de consumo masivo y pestañas.
 * Usamos líneas de lucide-react en lugar de emojis en toda la app.
 */
import {
  Activity,        // Ejecución en vivo
  Bot,             // Agentes
  Candy,           // Confitería y Snacks
  CookingPot,      // Culinarios
  Coffee,          // Bebidas Calientes
  CupSoda,         // Bebidas No Alcohólicas
  type LucideIcon,
  type LucideProps,
  MessageCircle,   // Marca / agente de sentimiento
  Milk,            // Lácteos
  Radar,           // Copiloto de campo
  Route,           // Agente de red de abastecimiento
  Sparkles,        // Genie
  Store,           // Puntos de venta
  Tag,             // Precio
  TrendingUp,      // Agente de pulso de ejecución
} from 'lucide-react';

// ---- Agentes ----------------------------------------------------------------
export const AGENT_ICON: Record<string, LucideIcon> = {
  pulso_ejecucion: TrendingUp,
  price_promo: Tag,
  sentimiento_marca: MessageCircle,
  red_abastecimiento: Route,
};

export const AGENT_META: Record<
  string,
  { Icon: LucideIcon; color: string; name: string; tagline: string }
> = {
  pulso_ejecucion: {
    Icon: TrendingUp,
    color: '#33bdee',
    name: 'Pulso de Ejecución',
    tagline: 'vigila disponibilidad, planograma y share of shelf visita a visita',
  },
  price_promo: {
    Icon: Tag,
    color: '#f87171',
    name: 'Precio',
    tagline: 'compara el índice de precio contra la competencia por cadena',
  },
  sentimiento_marca: {
    Icon: MessageCircle,
    color: '#a78bfa',
    name: 'Sentimiento de Marca',
    tagline: 'escucha la conversación y la cruza con lo que pasa en el anaquel',
  },
  red_abastecimiento: {
    Icon: Route,
    color: '#34d399',
    name: 'Red de Abastecimiento',
    tagline: 'cubre quiebres moviendo producto entre tiendas de la misma plaza',
  },
};

// ---- Categorías -------------------------------------------------------------
export const CATEGORY_ICON: Record<string, LucideIcon> = {
  'Bebidas Calientes': Coffee,
  'Lácteos': Milk,
  'Culinarios': CookingPot,
  'Confitería y Snacks': Candy,
  'Bebidas No Alcohólicas': CupSoda,
};

// ---- Pestañas ---------------------------------------------------------------
export const TAB_ICONS = {
  Ejecucion: Activity,
  Agentes: Bot,
  Pdv: Store,
  Precios: Tag,
  Marca: MessageCircle,
  Campo: Radar,
  Genie: Sparkles,
};

export function CategoryIcon({ category, ...props }: { category: string } & LucideProps) {
  const I = CATEGORY_ICON[category];
  if (!I) return null;
  return <I {...props} />;
}

export function AgentIcon({ agent, ...props }: { agent: string } & LucideProps) {
  const I = AGENT_ICON[agent];
  if (!I) return <Bot {...props} />;
  return <I {...props} />;
}
