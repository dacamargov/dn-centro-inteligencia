"""Escucha social (Brand & Ad Insight) — feed, virales, termómetro y campañas."""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..config import CLIENTE, FQ, get_current_user_email
from ..uc import execute, query

router = APIRouter()


def _q(s: str) -> str:
    return "'" + (s or "").replace("'", "''") + "'"


def _row_to_post(r: dict) -> dict:
    return {
        "post_id": r.get("post_id"),
        "platform": r.get("platform"),
        "author_handle": r.get("author_handle"),
        "author_followers": (
            int(r["author_followers"]) if r.get("author_followers") is not None else None
        ),
        "content": r.get("content"),
        "marca": r.get("marca"),
        "fabricante": r.get("fabricante"),
        "country_code": r.get("country_code"),
        "sentiment": r.get("sentiment"),
        "sentiment_score": (
            float(r["sentiment_score"]) if r.get("sentiment_score") is not None else None
        ),
        "engagement": int(r["engagement"]) if r.get("engagement") is not None else 0,
        "is_viral": bool(r.get("is_viral")),
        "posted_at": r["posted_at"].isoformat() if r.get("posted_at") else None,
    }


_POST_COLS = """post_id, platform, author_handle, author_followers, content,
                marca, fabricante, country_code, sentiment, sentiment_score,
                engagement, is_viral, posted_at"""


@router.get("/api/social/recent")
def recent(
    platform: Optional[str] = Query(None),
    marca: Optional[str] = Query(None),
    solo_cliente: bool = Query(False, description="solo marcas del fabricante cliente"),
    limit: int = Query(30, ge=1, le=200),
):
    where = ["1=1"]
    if marca:
        where.append(f"marca = {_q(marca)}")
    if solo_cliente:
        where.append(f"fabricante = {_q(CLIENTE)}")
    if platform:
        where.append(f"platform = {_q(platform)}")

    sql = f"""
        SELECT {_POST_COLS}
        FROM {FQ}.social_posts
        WHERE {" AND ".join(where)}
        ORDER BY posted_at DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [_row_to_post(r) for r in rows]


@router.get("/api/social/viral")
def viral(window_min: int = Query(30, ge=1, le=180)):
    sql = f"""
        SELECT {_POST_COLS}
        FROM {FQ}.social_posts
        WHERE posted_at >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
          AND (is_viral OR engagement >= 1000)
        ORDER BY engagement DESC
        LIMIT 10
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [_row_to_post(r) for r in rows]


@router.get("/api/social/post/{post_id}")
def post_por_id(post_id: str):
    """Un post puntual. Lo necesita la acción de viralizar cuando el agente
    señala una publicación que ya salió de la ventana del feed."""
    try:
        rows = query(f"""
            SELECT {_POST_COLS}
            FROM {FQ}.social_posts
            WHERE post_id = {_q(post_id)}
            LIMIT 1
        """)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=404, detail=f"no existe el post {post_id}")
    return _row_to_post(rows[0])


@router.get("/api/social/termometro")
def termometro(window_min: int = Query(60, ge=5, le=240)):
    """Score neto por marca del cliente vs sus competidoras directas.

    Score = promedio del sentiment_score, escala -1..1. Es el número que abre la
    pestaña de marca y el que los agentes cruzan contra la ejecución en anaquel.
    """
    sql = f"""
        SELECT
          marca,
          MAX(fabricante)                                        AS fabricante,
          COUNT(*)                                               AS menciones,
          ROUND(AVG(sentiment_score), 3)                         AS score,
          ROUND(AVG(CASE WHEN sentiment = 'negativo' THEN 1.0 ELSE 0.0 END) * 100, 1)
                                                                 AS negativos_pct,
          ROUND(AVG(CASE WHEN sentiment = 'positivo' THEN 1.0 ELSE 0.0 END) * 100, 1)
                                                                 AS positivos_pct,
          SUM(engagement)                                        AS engagement,
          SUM(CASE WHEN is_viral THEN 1 ELSE 0 END)              AS virales
        FROM {FQ}.social_posts
        WHERE posted_at >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
          AND marca IS NOT NULL
        GROUP BY marca
        HAVING COUNT(*) >= 3
        ORDER BY score ASC
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "marca": r["marca"],
            "fabricante": r.get("fabricante"),
            "es_cliente": (r.get("fabricante") == CLIENTE),
            "menciones": int(r["menciones"] or 0),
            "score": float(r["score"] or 0),
            "negativos_pct": float(r["negativos_pct"] or 0),
            "positivos_pct": float(r["positivos_pct"] or 0),
            "engagement": int(r["engagement"] or 0),
            "virales": int(r["virales"] or 0),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Amplificación: convertir un post en campaña
# ---------------------------------------------------------------------------

# Alcance pagado por dólar invertido, por plataforma. Son CPM típicos de la
# región convertidos a impresiones por dólar; sirven para que el número que ve
# el cliente en pantalla tenga un orden de magnitud defendible, no para facturar.
ALCANCE_POR_USD = {
    "tiktok": 420,
    "instagram": 260,
    "facebook": 310,
    "x": 190,
}

OBJETIVOS = {
    "amplificar": "Amplificar conversación positiva",
    "defender": "Defender la marca frente a una crisis",
    "lanzar": "Empujar lanzamiento o promoción",
}


class AmplificarRequest(BaseModel):
    objetivo: str = Field(default="amplificar")
    presupuesto_usd: float = Field(default=5000, ge=100, le=250_000)
    plataformas: list[str] = Field(default_factory=list)
    nombre: Optional[str] = None


@router.post("/api/social/{post_id}/amplificar")
def amplificar(post_id: str, body: AmplificarRequest, request: Request):
    """Pone plata detrás de un post que ya funciona y registra la campaña.

    El post queda marcado como viral y se le suma el alcance pagado al engagement
    orgánico, así que el efecto se ve en el mismo feed donde se tomó la decisión.
    Es el cierre del ciclo del agente de sentimiento: detecta, recomienda, y acá
    alguien ejecuta.
    """
    if body.objetivo not in OBJETIVOS:
        raise HTTPException(status_code=400, detail=f"objetivo inválido: {body.objetivo}")

    try:
        rows = query(f"""
            SELECT {_POST_COLS}
            FROM {FQ}.social_posts
            WHERE post_id = {_q(post_id)}
            LIMIT 1
        """)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=404, detail=f"no existe el post {post_id}")

    post = _row_to_post(rows[0])

    ya = query(f"""
        SELECT campana_id FROM {FQ}.campanas WHERE post_id = {_q(post_id)} LIMIT 1
    """)
    if ya:
        raise HTTPException(
            status_code=409,
            detail="Ese post ya tiene una campaña activa.",
        )

    plataformas = [p for p in body.plataformas if p in ALCANCE_POR_USD]
    if not plataformas:
        plataformas = [post["platform"]] if post["platform"] in ALCANCE_POR_USD else ["instagram"]

    # El presupuesto se reparte parejo y cada plataforma rinde distinto.
    por_plataforma = body.presupuesto_usd / len(plataformas)
    alcance = int(sum(por_plataforma * ALCANCE_POR_USD[p] for p in plataformas))

    categoria = None
    try:
        cat = query(f"""
            SELECT categoria FROM {FQ}.productos
            WHERE marca = {_q(post['marca'] or '')}
            LIMIT 1
        """)
        categoria = cat[0]["categoria"] if cat else None
    except Exception:  # noqa: BLE001
        pass

    campana_id = f"cmp_{uuid.uuid4().hex[:12]}"
    nombre = body.nombre or f"{OBJETIVOS[body.objetivo]} · {post['marca'] or 'marca'}"
    actor = get_current_user_email(request)

    try:
        execute(f"""
            INSERT INTO {FQ}.campanas VALUES (
              {_q(campana_id)}, {_q(post_id)}, {_q(nombre)},
              {_q(post['marca'] or '')}, {_q(post['fabricante'] or '')},
              {_q(categoria or '')}, {_q(post['country_code'] or '')},
              {_q(body.objetivo)}, {_q(','.join(plataformas))},
              CAST({body.presupuesto_usd} AS DECIMAL(12,2)), {alcance},
              {post['engagement']}, 'activa', {_q(actor)}, current_timestamp()
            )
        """)
        # El engagement pagado se suma al orgánico: sin esto la campaña sería un
        # registro en una tabla y el post en pantalla no cambiaría en nada.
        execute(f"""
            UPDATE {FQ}.social_posts
            SET is_viral = true,
                engagement = engagement + {int(alcance * 0.012)}
            WHERE post_id = {_q(post_id)}
        """)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"no se pudo crear la campaña: {exc}") from exc

    return {
        "campana_id": campana_id,
        "post_id": post_id,
        "nombre": nombre,
        "marca": post["marca"],
        "fabricante": post["fabricante"],
        "categoria": categoria,
        "country_code": post["country_code"],
        "objetivo": body.objetivo,
        "plataformas": plataformas,
        "presupuesto_usd": body.presupuesto_usd,
        "alcance_estimado": alcance,
        "engagement_base": post["engagement"],
        "estado": "activa",
        "creada_por": actor,
    }


@router.get("/api/campanas")
def campanas(limit: int = Query(20, ge=1, le=100)):
    """Campañas lanzadas desde el centro de mando, la más reciente primero."""
    sql = f"""
        SELECT c.campana_id, c.post_id, c.nombre, c.marca, c.fabricante, c.categoria,
               c.country_code, c.objetivo, c.plataformas, c.presupuesto_usd,
               c.alcance_estimado, c.engagement_base, c.estado, c.creada_por, c.creada_en,
               p.content, p.engagement AS engagement_actual
        FROM {FQ}.campanas c
        LEFT JOIN {FQ}.social_posts p ON p.post_id = c.post_id
        ORDER BY c.creada_en DESC
        LIMIT {int(limit)}
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "campana_id": r["campana_id"],
            "post_id": r["post_id"],
            "nombre": r["nombre"],
            "marca": r.get("marca"),
            "fabricante": r.get("fabricante"),
            "categoria": r.get("categoria"),
            "country_code": r.get("country_code"),
            "objetivo": r["objetivo"],
            "plataformas": [p for p in (r.get("plataformas") or "").split(",") if p],
            "presupuesto_usd": float(r["presupuesto_usd"] or 0),
            "alcance_estimado": int(r["alcance_estimado"] or 0),
            "engagement_base": int(r["engagement_base"] or 0),
            "engagement_actual": int(r["engagement_actual"] or 0),
            "estado": r["estado"],
            "creada_por": r.get("creada_por"),
            "creada_en": r["creada_en"].isoformat() if r.get("creada_en") else None,
            "contenido": r.get("content"),
        }
        for r in rows
    ]


@router.get("/api/social/por-categoria")
def por_categoria(window_min: int = Query(60, ge=5, le=240)):
    """Sentimiento por categoría, cruzado contra la disponibilidad de esa categoría.

    Es el corte más útil de la pestaña: cuando una categoría acumula menciones
    negativas y a la vez tiene disponibilidad baja, la queja en redes casi
    siempre está describiendo un anaquel vacío, no un problema de producto.
    """
    sql = f"""
        WITH marcas AS (
          SELECT DISTINCT marca, categoria FROM {FQ}.productos
        ),
        social AS (
          SELECT m.categoria,
                 COUNT(*)                       AS menciones,
                 AVG(sp.sentiment_score)        AS score,
                 AVG(CASE WHEN sp.sentiment = 'negativo' THEN 1.0 ELSE 0.0 END) * 100
                                                AS negativos_pct,
                 SUM(sp.engagement)             AS engagement
          FROM {FQ}.social_posts sp
          JOIN marcas m ON m.marca = sp.marca
          WHERE sp.posted_at >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
            AND sp.fabricante = {_q(CLIENTE)}
          GROUP BY m.categoria
        ),
        anaquel AS (
          SELECT categoria,
                 AVG(CAST(en_stock AS INT)) * 100 AS disponibilidad_pct
          FROM {FQ}.visitas
          WHERE visit_ts >= current_timestamp() - INTERVAL {int(window_min)} MINUTES
            AND es_cliente
          GROUP BY categoria
        )
        SELECT s.categoria,
               s.menciones,
               ROUND(s.score, 3)            AS score,
               ROUND(s.negativos_pct, 1)    AS negativos_pct,
               s.engagement,
               ROUND(a.disponibilidad_pct, 1) AS disponibilidad_pct
        FROM social s
        LEFT JOIN anaquel a ON a.categoria = s.categoria
        ORDER BY s.score ASC
    """
    try:
        rows = query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    return [
        {
            "categoria": r["categoria"],
            "menciones": int(r["menciones"] or 0),
            "score": float(r["score"] or 0),
            "negativos_pct": float(r["negativos_pct"] or 0),
            "engagement": int(r["engagement"] or 0),
            "disponibilidad_pct": (
                float(r["disponibilidad_pct"]) if r.get("disponibilidad_pct") is not None else None
            ),
        }
        for r in rows
    ]
