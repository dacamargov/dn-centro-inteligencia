import { Activity, Bot, MessageCircle, Radar, Store, Tag } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const TABS = [
  { to: '/ejecucion', label: 'Ejecución',  Icon: Activity,      end: true, iconColor: 'text-dn-600' },
  { to: '/agentes',   label: 'Agentes',    Icon: Bot,                      iconColor: 'text-sky-600' },
  { to: '/pdv',       label: 'Puntos de venta', Icon: Store,               iconColor: 'text-emerald-600' },
  { to: '/precios',   label: 'Precio',     Icon: Tag,                      iconColor: 'text-rose-600' },
  { to: '/marca',     label: 'Marca',      Icon: MessageCircle,            iconColor: 'text-violet-600' },
  { to: '/campo',     label: 'Copiloto de campo', Icon: Radar,             iconColor: 'text-teal-600' },
];

export default function TabNav() {
  return (
    <nav className="sticky top-0 z-20 border-b border-marco backdrop-blur-md bg-white">
      <div className="px-6 flex gap-1 overflow-x-auto">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              [
                'group relative px-4 py-3 text-sm tracking-wide uppercase font-medium transition-colors',
                'flex items-center gap-2 whitespace-nowrap',
                isActive ? 'text-dn-600' : 'text-grafito hover:text-tinta',
              ].join(' ')
            }
          >
            {({ isActive }) => (
              <>
                <t.Icon
                  className={[
                    'w-4 h-4 transition-all',
                    isActive
                      ? 'text-dn-600'
                      : `${t.iconColor} opacity-80 group-hover:opacity-100`,
                  ].join(' ')}
                  strokeWidth={2}
                />
                {t.label}
                {isActive && (
                  <span className="absolute left-3 right-3 -bottom-px h-0.5 bg-dn-600" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
