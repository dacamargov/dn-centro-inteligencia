"""Control del ciclo de vida de la demo — arranca y detiene los jobs desde la UI.

El botón "Iniciar demo" del frontend llama a estos endpoints. Dentro de
Databricks Apps corren como el service principal del app, que necesita
CAN_MANAGE sobre los jobs de generación y de agentes (se otorga al desplegar).

Los jobs se descubren por nombre, sin IDs quemados:
  * define JOB_PREFIX en app.yaml para hacer match por prefijo, o
  * déjalo vacío y se toma cualquier job cuyo nombre contenga "dncentro".
Un job es generador si su nombre contiene "datagen", y agente si contiene
"agent".
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException

from ..config import FQ, get_workspace_client
from ..uc import execute as uc_execute
from ..uc import query as uc_query

log = logging.getLogger(__name__)
router = APIRouter()

JOB_PREFIX = (os.environ.get("JOB_PREFIX") or "").strip()

# Tablas transitorias y su ventana viva, en minutos.
#
# Cada generador poda lo suyo, pero solo lo suyo: `visitas`, `ejecucion_realtime`
# y `social_posts` tenían retención y el resto crecía sin techo. `traslados` llegó
# a 5.600 filas en una noche. Esta tabla es la fuente única de verdad de qué se
# considera transitorio y cuánto tiempo vale cada cosa, y la usan tanto la limpieza
# por ventana como el vaciado total.
#
# Los maestros (paises, fabricantes, productos, tiendas, metas_categoria) no
# aparecen acá a propósito: volver a sembrarlos toma minutos y no cambian entre
# sesiones.
#
# `None` en la columna de tiempo significa que la tabla solo se puede vaciar
# entera, porque no tiene una marca temporal con la que decidir qué es viejo.
TRANSIENT_TABLES: list[tuple[str, str | None, int]] = [
    # tabla                  columna de tiempo   ventana viva (min)
    ("visitas",              "visit_ts",          90),
    ("ejecucion_realtime",   "minute_ts",         90),
    ("precios_competencia",  "snapshot_ts",      240),
    ("social_posts",         "posted_at",        240),
    ("recomendaciones",      "created_at",       120),
    ("runs",                 "started_at",       240),
    ("action_log",           "occurred_at",      240),
    ("acciones_campo",       "created_at",       240),
    ("campanas",             "creada_en",        240),
    ("promociones_gondola",  "lanzada_en",       240),
    # Una propuesta de traslado se apoya en una lectura de anaquel: pasada la
    # ventana no describe ninguna realidad y solo engorda la cola.
    ("traslados",            "propuesto_en",      60),
]

TRANSIENT_NAMES = [t for t, _, _ in TRANSIENT_TABLES]


def _matches(name: str) -> bool:
    if not name:
        return False
    if JOB_PREFIX:
        return name.startswith(JOB_PREFIX)
    return "dncentro" in name.lower().replace(" ", "")


def _classify(name: str):
    low = name.lower()
    if "agent" in low:
        return "agent"
    if "datagen" in low:
        return "datagen"
    return None


def _row_from_job(j) -> dict | None:
    s = j.settings
    name = (s.name if s else "") or ""
    if not _matches(name):
        return None
    kind = _classify(name)
    if kind is None:
        return None
    pause = None
    if s and s.schedule and s.schedule.pause_status:
        pause = s.schedule.pause_status.value
    return {"job_id": j.job_id, "name": name, "pause_status": pause, "kind": kind}


def _dedupe_jobs(rows: list[dict]) -> list[dict]:
    """Un job por nombre: el bundle puede dejar huérfanos con el mismo título.

    Si hay dos copias del mismo job, el estado de la demo miente (una pausada y otra
    activa) y Detener solo alcanza a la mitad. Nos quedamos con el job_id más alto,
    que suele ser el del último deploy.
    """
    by_name: dict[str, dict] = {}
    for row in rows:
        name = row["name"]
        prev = by_name.get(name)
        if prev is None or row["job_id"] > prev["job_id"]:
            by_name[name] = row
    return list(by_name.values())


def _discover_all() -> list[dict]:
    """Todos los jobs datagen/agent del prefijo, incluidos duplicados huérfanos."""
    w = get_workspace_client()
    rows: list[dict] = []
    for j in w.jobs.list():
        row = _row_from_job(j)
        if row:
            rows.append(row)
    return rows


def _discover():
    """Return (datagen, agents) deduped lists of {job_id, name, pause_status}."""
    all_rows = _discover_all()
    deduped = _dedupe_jobs(all_rows)
    datagen, agents = [], []
    for row in deduped:
        entry = {k: row[k] for k in ("job_id", "name", "pause_status")}
        (datagen if row["kind"] == "datagen" else agents).append(entry)
    return datagen, agents


def _set_pause(w, job_id: int, unpaused: bool) -> bool:
    """Flip a job's schedule pause_status. Returns False if it has no schedule."""
    from databricks.sdk.service.jobs import CronSchedule, JobSettings, PauseStatus

    j = w.jobs.get(job_id)
    sched = j.settings.schedule if j.settings else None
    if not sched or not sched.quartz_cron_expression:
        return False
    w.jobs.update(
        job_id=job_id,
        new_settings=JobSettings(
            schedule=CronSchedule(
                quartz_cron_expression=sched.quartz_cron_expression,
                timezone_id=sched.timezone_id or "UTC",
                pause_status=PauseStatus.UNPAUSED if unpaused else PauseStatus.PAUSED,
            )
        ),
    )
    return True


def _cancel_active_runs(w, job_id: int) -> None:
    """Corta corridas en vuelo; pausar la agenda no cancela lo que ya arrancó."""
    try:
        w.jobs.cancel_all_runs(job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("cancel_all_runs job %s: %s", job_id, exc)


@router.get("/api/demo/status")
def demo_status():
    try:
        datagen, agents = _discover()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"jobs list failed: {exc}") from exc
    all_jobs = datagen + agents
    running = any(j["pause_status"] == "UNPAUSED" for j in all_jobs)
    return {
        "running": running,
        "found": len(all_jobs),
        "datagen": datagen,
        "agents": agents,
    }


@router.post("/api/demo/start")
def demo_start():
    w = get_workspace_client()
    try:
        datagen, agents = _discover()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"jobs list failed: {exc}") from exc
    if not (datagen or agents):
        raise HTTPException(status_code=404, detail="No encontré jobs del Centro de Inteligencia.")

    started, errors = [], []
    # Unpause everything so the schedules keep the demo alive.
    for j in datagen + agents:
        try:
            _set_pause(w, j["job_id"], True)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"unpause {j['name']}: {exc}")
    # Trigger an immediate run (data-gen first so agents have fresh data).
    for j in datagen + agents:
        try:
            run = w.jobs.run_now(job_id=j["job_id"])
            started.append({"job_id": j["job_id"], "name": j["name"], "run_id": run.run_id})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"run {j['name']}: {exc}")

    if not started and errors:
        raise HTTPException(status_code=502, detail="; ".join(errors[:4]))

    flujo_campo = _flujo_campo(True)
    return {"ok": True, "started": started, "errors": errors, "flujo_campo": flujo_campo}


def _flujo_campo(encender: bool) -> bool:
    """Enciende o apaga la jornada del copiloto junto con el resto de la demo.

    El copiloto no vive de jobs sino de un hilo del app, así que sin esto habría
    que acordarse de arrancarlo aparte y la pestaña Campo aparecería muerta
    mientras todo lo demás late. Best-effort: si Lakebase no está configurado,
    simplemente no hay flujo que mover.
    """
    try:
        from ..campo_flujo import flujo
        from ..lakebase import is_configured

        if not is_configured():
            return False
        if encender:
            flujo.arrancar(ritmo=6.0)
        else:
            flujo.detener()
        return flujo.activo
    except Exception as exc:  # noqa: BLE001
        log.warning("no pude %s el flujo de campo: %s",
                    "arrancar" if encender else "detener", exc)
        return False


def _conteos() -> dict[str, int]:
    """Filas por tabla transitoria, en una sola consulta.

    Una consulta por tabla serían once viajes al warehouse y el panel tardaría
    más en abrirse que la limpieza en correr.
    """
    partes = [
        f"SELECT '{t}' AS tabla, COUNT(*) AS filas FROM {FQ}.{t}"
        for t in TRANSIENT_NAMES
    ]
    rows = uc_query(" UNION ALL ".join(partes))
    return {r["tabla"]: int(r["filas"] or 0) for r in rows}


def _conteos_lakebase() -> dict[str, int]:
    """Filas de las tablas transitorias de Lakebase. Vacío si no está configurado."""
    try:
        from ..lakebase import connect, is_configured

        if not is_configured():
            return {}
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT (SELECT COUNT(*) FROM campo.sugerencias_log),"
                    "       (SELECT COUNT(*) FROM public.genie_interactions)"
                )
                a, b = cur.fetchone()
        return {"campo.sugerencias_log": int(a or 0),
                "public.genie_interactions": int(b or 0)}
    except Exception as exc:  # noqa: BLE001
        log.warning("conteo de Lakebase falló: %s", exc)
        return {}


def _purgar(total: bool) -> tuple[list[dict], list[str]]:
    """Purga las tablas transitorias en UC.

    `total=True` las vacía enteras — para dejar limpio entre presentaciones.
    `total=False` borra solo lo que cayó fuera de su ventana viva, así se puede
    correr con la demo encendida sin romper ningún panel.
    """
    detalle, errores = [], []
    antes = {}
    try:
        antes = _conteos()
    except Exception as exc:  # noqa: BLE001
        errores.append(f"conteo previo: {exc}")

    for tabla, col_ts, ventana in TRANSIENT_TABLES:
        try:
            if total or col_ts is None:
                uc_execute(f"TRUNCATE TABLE {FQ}.{tabla}")
            else:
                uc_execute(
                    f"DELETE FROM {FQ}.{tabla} "
                    f"WHERE {col_ts} < current_timestamp() - INTERVAL {ventana} MINUTES"
                )
            detalle.append({
                "tabla": tabla,
                "filas_antes": antes.get(tabla),
                "modo": "vaciada" if (total or col_ts is None) else f"ventana {ventana} min",
            })
        except Exception as exc:  # noqa: BLE001
            errores.append(f"{tabla}: {exc}")

    detalle.extend(_purgar_lakebase(total, errores))
    return detalle, errores


def _purgar_lakebase(total: bool, errores: list) -> list[dict]:
    """Purga el log de sugerencias y el historial de Genie en Lakebase.

    Sin esto, los picos de latencia de una sesión vieja siguen contando en el
    panel de SLA de la siguiente. Best-effort: si Lakebase no está configurado,
    no hace nada y no es un error.
    """
    try:
        from ..lakebase import connect, is_configured

        if not is_configured():
            return []
        # El log de sugerencias es el que crece rápido: una jornada a 30 visitas
        # por minuto escribe 1.800 filas por hora.
        ventana_min = 240
        objetivos = [
            ("campo.sugerencias_log", "served_at"),
            ("public.genie_interactions", "created_at"),
        ]
        detalle = []
        with connect() as conn:
            with conn.cursor() as cur:
                for tabla, col_ts in objetivos:
                    cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                    antes = int(cur.fetchone()[0] or 0)
                    if total:
                        cur.execute(f"TRUNCATE TABLE {tabla}")
                    else:
                        cur.execute(
                            f"DELETE FROM {tabla} "
                            f"WHERE {col_ts} < NOW() - INTERVAL '{ventana_min} minutes'"
                        )
                    cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                    despues = int(cur.fetchone()[0] or 0)
                    detalle.append({
                        "tabla": tabla,
                        "modo": "vaciada" if total else f"ventana {ventana_min} min",
                        "filas_antes": antes,
                        "filas_despues": despues,
                        "filas_liberadas": max(0, antes - despues),
                    })
            conn.commit()
        return detalle
    except Exception as exc:  # noqa: BLE001
        errores.append(f"lakebase: {exc}")
        return []


def _wipe_transient():
    """Vaciado total, que es lo que corresponde al detener la demo."""
    detalle, errores = _purgar(total=True)
    return [d["tabla"] for d in detalle], errores


@router.get("/api/demo/volumen")
def demo_volumen():
    """Cuántas filas simuladas hay guardadas ahora mismo, tabla por tabla.

    Existe para poder contestar "¿cómo se están purgando los datos?" sin abrir
    un notebook: muestra el volumen y qué retención tiene cada tabla.
    """
    try:
        uc = _conteos()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"conteo falló: {exc}") from exc

    tablas = [
        {
            "tabla": tabla,
            "filas": uc.get(tabla, 0),
            "ventana_min": ventana if col_ts else None,
            "columna_tiempo": col_ts,
        }
        for tabla, col_ts, ventana in TRANSIENT_TABLES
    ]
    lb = [
        {"tabla": t, "filas": n, "ventana_min": 240, "columna_tiempo": None}
        for t, n in _conteos_lakebase().items()
    ]
    return {
        "unity_catalog": tablas,
        "lakebase": lb,
        "filas_total": sum(t["filas"] for t in tablas) + sum(t["filas"] for t in lb),
    }


@router.post("/api/demo/limpiar")
def demo_limpiar(total: bool = False):
    """Purga los datos simulados sin tocar los maestros ni los jobs.

    `total=false` (por defecto) borra solo lo que quedó fuera de la ventana viva,
    así se puede correr con la demo encendida. `total=true` vacía todo, para
    dejar el workspace limpio entre presentaciones.
    """
    detalle, errores = _purgar(total=total)
    if not detalle and errores:
        raise HTTPException(status_code=502, detail="; ".join(errores[:4]))

    despues = {}
    try:
        despues = _conteos()
    except Exception as exc:  # noqa: BLE001
        errores.append(f"conteo posterior: {exc}")
    for d in detalle:
        if d["tabla"] in despues:
            d["filas_despues"] = despues[d["tabla"]]
            antes = d.get("filas_antes")
            if antes is not None:
                d["filas_liberadas"] = max(0, antes - despues[d["tabla"]])

    return {
        "ok": True,
        "modo": "total" if total else "ventana",
        "detalle": detalle,
        "filas_liberadas": sum(d.get("filas_liberadas", 0) for d in detalle),
        "filas_restantes": sum(despues.values()) if despues else None,
        "errors": errores,
    }


@router.post("/api/demo/stop")
def demo_stop(wipe: bool = True):
    """Pausa todos los jobs y (por defecto) vacía las tablas transitorias para
    dejar la demo limpia entre presentaciones. Pasa ?wipe=false para solo pausar
    y conservar los datos."""
    w = get_workspace_client()
    try:
        todos = _discover_all()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"jobs list failed: {exc}") from exc

    paused, errors = [], []
    # Pausar TODAS las copias (huérfanas y actuales) y cancelar corridas en vuelo.
    for j in todos:
        try:
            _cancel_active_runs(w, j["job_id"])
            if _set_pause(w, j["job_id"], False):
                paused.append(j["name"])
            else:
                errors.append(f"{j['name']}: sin agenda programada")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{j['name']}: {exc}")

    # El flujo se apaga antes de vaciar: si siguiera escribiendo, el log de
    # sugerencias volvería a poblarse a los dos segundos de truncarlo.
    _flujo_campo(False)

    wiped = []
    if wipe:
        wiped, wipe_errors = _wipe_transient()
        errors.extend(wipe_errors)

    return {"ok": True, "paused": paused, "wiped": wiped, "errors": errors}
