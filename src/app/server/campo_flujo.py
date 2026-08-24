"""Flujo continuo del copiloto de campo — la jornada de la red, en vivo.

Simula lo que pasa en una jornada real: los mercaderistas van llegando a sus
puntos de venta, abren la app, reciben el plan priorizado desde Lakebase y al
rato cierran la visita reportando qué corrigieron.

Vive en el servidor y no en el navegador a propósito. La versión anterior movía
la rueda desde un `setInterval` de la pestaña Campo, con dos consecuencias
malas: el flujo se congelaba al cambiar de pestaña —justo cuando el presentador
recorre el resto del tablero— y cada espectador con la página abierta sumaba su
propia carga al mismo log. Acá hay un solo hilo, con un solo ritmo, y lo que se
ve es el estado del sistema y no el de un navegador.

Las dos mitades del ciclo corren desacopladas:
  * servir  → elige un PDV y pide su plan (lectura por clave + ranking).
  * cerrar  → toma planes ya servidos y reporta la ejecución tras un rato.

El desacople importa porque en la vida real tampoco son simultáneos: el plan
llega al empezar la visita y el reporte sale al terminarla.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

# Cuánto tarda una visita entre recibir el plan y cerrarlo. Sin esta demora el
# feed mostraría todo ejecutado al instante y no se vería el ciclo.
_DEMORA_CIERRE_S = (8.0, 45.0)

# Qué tanto del plan ejecuta el mercaderista. No es un número redondo porque no
# lo es en campo: a veces no hay producto en bodega, a veces el local no deja
# tocar el anaquel, a veces la visita se corta.
#
# Los pesos están calibrados para que la tasa medida sobre plata caiga cerca del
# 62%, que es el número que la demo venía afirmando como supuesto. Ojo que la
# tasa en dólares queda por encima de la tasa en conteo de SKUs, porque el
# mercaderista arranca por las acciones de mayor impacto: dejar una acción sin
# hacer casi nunca es dejar la más cara.
_REPARTO_EJECUCION = (
    ("todo",    0.16),   # ejecuta el plan completo
    ("casi",    0.31),   # deja la última acción sin hacer
    ("mitad",   0.34),   # alcanza a la mitad
    ("ninguna", 0.19),   # cierra sin ejecutar nada del plan
)


class FlujoCampo:
    """Rueda de visitas. Se arranca y se detiene; nunca corre más de un hilo."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hilo: Optional[threading.Thread] = None
        self._parar = threading.Event()
        self._ritmo = 6.0            # visitas por minuto
        self._servidas = 0
        self._cerradas = 0
        self._errores = 0
        self._ultimo_error: Optional[str] = None
        self._arrancado_en: Optional[float] = None

    # -- control ----------------------------------------------------------

    @property
    def activo(self) -> bool:
        # Se consulta la intención y no solo el hilo: `detener()` deja al hilo
        # dormido en su `wait` hasta varios segundos, y durante esa ventana
        # reportar "activo" hacía que el botón de la UI volviera a "pausar"
        # inmediatamente después de haberlo apretado.
        h = self._hilo
        return h is not None and h.is_alive() and not self._parar.is_set()

    def arrancar(self, ritmo: float) -> bool:
        """Enciende la rueda. Si ya estaba activa solo ajusta el ritmo."""
        with self._lock:
            self._ritmo = max(0.5, min(60.0, float(ritmo)))
            if self.activo:
                return False
            self._parar.clear()
            self._arrancado_en = time.time()
            self._hilo = threading.Thread(
                target=self._correr, name="campo-flujo", daemon=True
            )
            self._hilo.start()
            return True

    def detener(self) -> bool:
        with self._lock:
            if not self.activo:
                return False
            self._parar.set()
            return True

    def estado(self) -> dict:
        return {
            "activo": self.activo,
            "ritmo_por_min": round(self._ritmo, 1),
            "servidas": self._servidas,
            "cerradas": self._cerradas,
            "errores": self._errores,
            "ultimo_error": self._ultimo_error,
            "segundos_activo": (
                int(time.time() - self._arrancado_en)
                if self._arrancado_en and self.activo else 0
            ),
        }

    # -- rueda ------------------------------------------------------------

    def _correr(self) -> None:
        log.info("flujo de campo arrancado a %.1f visitas/min", self._ritmo)
        cierres = threading.Thread(target=self._correr_cierres, daemon=True)
        cierres.start()
        try:
            while not self._parar.is_set():
                try:
                    self._servir_una()
                except Exception as exc:  # noqa: BLE001
                    self._errores += 1
                    self._ultimo_error = str(exc)[:200]
                    log.warning("flujo de campo: servir falló: %s", exc)
                # Jitter: una cadencia exacta se ve sintética en el feed, y la
                # jornada real tampoco llega en intervalos parejos.
                base = 60.0 / max(0.5, self._ritmo)
                self._parar.wait(base * random.uniform(0.6, 1.5))
        finally:
            self._arrancado_en = None
            log.info("flujo de campo detenido")

    def _servir_una(self) -> None:
        """Un mercaderista abre la app en un PDV y recibe su plan."""
        from .routes.lakebase_studio import SugerirRequest, sugerir

        store_id = self._elegir_pdv()
        if not store_id:
            return
        sugerir(SugerirRequest(store_id=store_id, n=4))
        self._servidas += 1

    def _elegir_pdv(self) -> Optional[str]:
        """PDV pesado por riesgo de quiebre: la ruta prioriza lo que más duele."""
        from .lakebase import connect

        with connect() as conn:
            with conn.cursor() as cur:
                # TABLESAMPLE sería más barato pero con 140 filas cabe en una
                # página y el ORDER BY aleatorio es irrelevante en costo.
                cur.execute(
                    "SELECT store_id FROM campo.pdv_perfiles "
                    "ORDER BY random() * (1.2 - riesgo_quiebre) LIMIT 1"
                )
                row = cur.fetchone()
        return row[0] if row else None

    def _correr_cierres(self) -> None:
        """Cierra visitas servidas hace rato, reportando qué se ejecutó."""
        while not self._parar.is_set():
            try:
                self._cerrar_pendientes()
            except Exception as exc:  # noqa: BLE001
                self._errores += 1
                self._ultimo_error = str(exc)[:200]
                log.warning("flujo de campo: cierre falló: %s", exc)
            self._parar.wait(random.uniform(3.0, 7.0))

    def _cerrar_pendientes(self) -> None:
        from .lakebase import connect
        from .routes.lakebase_studio import EjecutarRequest, ejecutar

        # El umbral se sortea en cada pasada para que las visitas no cierren todas
        # con la misma edad; en el feed se nota la diferencia entre una cadencia
        # de reloj y una jornada.
        umbral = random.uniform(*_DEMORA_CIERRE_S)
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, skus FROM campo.sugerencias_log
                    WHERE estado = 'servida'
                      AND served_at < NOW() - INTERVAL '{umbral:.0f} seconds'
                    ORDER BY served_at ASC
                    LIMIT 4
                    """
                )
                pendientes = cur.fetchall()

        for sug_id, skus in pendientes:
            # Se cierra siempre, incluso un plan sin SKUs: como la cola se lee por
            # `served_at` ascendente, saltárselo lo devolvía en cada pasada y
            # bloqueaba de por vida todo lo que venía detrás.
            ejecutar(int(sug_id), EjecutarRequest(
                skus_ejecutados=self._sortear_ejecucion(list(skus or [])),
                nota="cierre de visita simulado",
            ))
            self._cerradas += 1

    @staticmethod
    def _sortear_ejecucion(skus: list[str]) -> list[str]:
        if not skus:
            return []
        r = random.random()
        acumulado = 0.0
        modo = "todo"
        for nombre, peso in _REPARTO_EJECUCION:
            acumulado += peso
            if r <= acumulado:
                modo = nombre
                break
        if modo == "todo":
            return list(skus)
        if modo == "ninguna":
            return []
        if modo == "casi":
            return skus[:-1] if len(skus) > 1 else list(skus)
        return skus[: max(1, len(skus) // 2)]


flujo = FlujoCampo()
