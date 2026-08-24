import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import AgentAlertToasts from './components/AgentAlertToasts';
import GenieChatWidget from './components/GenieChatWidget';
import Header from './components/Header';
import TabNav from './components/TabNav';
import Agentes from './pages/Agentes';
import Campo from './pages/Campo';
import Ejecucion from './pages/Ejecucion';
import Landing from './pages/Landing';
import Marca from './pages/Marca';
import PuntosDeVenta from './pages/PuntosDeVenta';
import Precios from './pages/Precios';

export default function App() {
  const [connected, setConnected] = useState(true);
  const location = useLocation();
  const isLanding = location.pathname === '/';
  // Los toasts sobran en la portada y en Ejecución, que ya tiene su propio
  // banner de acción destacada arriba.
  const showToasts = !isLanding && location.pathname !== '/ejecucion';

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const r = await fetch('/healthz');
        if (active) setConnected(r.ok);
      } catch {
        if (active) setConnected(false);
      }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-lienzo">
      <Header connected={connected} />
      {!isLanding && <TabNav />}
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/ejecucion" element={<Ejecucion />} />
          <Route path="/agentes" element={<Agentes />} />
          <Route path="/pdv" element={<PuntosDeVenta />} />
          <Route path="/precios" element={<Precios />} />
          <Route path="/marca" element={<Marca />} />
          <Route path="/campo" element={<Campo />} />
          {/* El chat de Genie es flotante; la ruta vieja vuelve a la portada. */}
          <Route path="/genie" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      {showToasts && <AgentAlertToasts />}
      {!isLanding && <GenieChatWidget />}
    </div>
  );
}
