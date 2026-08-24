"""Chat de Genie — hace de proxy al API REST y expone un flujo simple de pregunta/respuesta.

Dos modos:
  * live — hay GENIE_SPACE_ID: las preguntas van a un Genie Space real por el API REST.
  * demo — GENIE_SPACE_ID vacío: las respuestas salen de canned_genie.json, así que la
           pestaña es demostrable sin montar un Genie Space. Ver docs/GENIE.md para conectar
           una sala real.
"""
from __future__ import annotations

import difflib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import lakebase
from ..config import (
    FQ,
    GENIE_SPACE_ID,
    get_current_user_email,
    get_workspace_client,
    get_workspace_host,
)

router = APIRouter()

MODE = "live" if GENIE_SPACE_ID else "demo"

# ---- Canned (demo mode) -------------------------------------------------------
_CANNED_PATH = Path(__file__).resolve().parent.parent / "canned_genie.json"
try:
    _CANNED = json.loads(_CANNED_PATH.read_text(encoding="utf-8")).get("answers", [])
    # El archivo se commitea con el marcador __FQ__ en lugar del esquema, porque el
    # catálogo de quien clona el repo no es el de quien lo generó.
    for _a in _CANNED:
        if _a.get("sql"):
            _a["sql"] = _a["sql"].replace("__FQ__", FQ)
except Exception:
    _CANNED = []

_SUGGESTED_QUESTIONS = [a["question"] for a in _CANNED]

# Preguntas sugeridas cuando hay un Genie Space real conectado sobre el esquema
# de la demo (visitas, productos, tiendas, precios_competencia, social_posts).
LIVE_SUGGESTED_QUESTIONS = [
    "¿Cuál es la disponibilidad en anaquel por categoría?",
    "¿Qué puntos de venta tienen la peor ejecución esta hora?",
    "¿Cuál es el share of shelf de nuestras marcas por país?",
    "¿Qué SKUs están agotados en más puntos de venta?",
    "¿Cómo se compara nuestro índice de precio con la competencia por cadena?",
    "¿Qué diferencia hay en ejecución entre canal moderno y tradicional?",
]


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9á-úç ]", " ", (s or "").lower())


def _match_canned(question: str) -> Optional[dict]:
    """Pick the best canned answer for a free-text question (keyword + fuzzy match)."""
    if not _CANNED:
        return None
    q = _normalize(question)
    q_tokens = set(q.split())
    best, best_score = None, 0.0
    for ans in _CANNED:
        kw = [k.lower() for k in ans.get("keywords", [])]
        kw_hits = sum(1 for k in kw if k in q)
        ratio = difflib.SequenceMatcher(None, q, _normalize(ans["question"])).ratio()
        overlap = len(q_tokens & set(_normalize(ans["question"]).split()))
        score = kw_hits * 2 + ratio * 3 + overlap * 0.5
        if score > best_score:
            best, best_score = ans, score
    # Require a minimal signal; otherwise fall back to the first canned answer.
    return best if best_score >= 1.0 else (_CANNED[0] if _CANNED else None)


@router.get("/api/genie/space-id")
def genie_space_id():
    if not GENIE_SPACE_ID:
        # Demo mode: no real space, but the tab is fully usable via canned answers.
        return {
            "space_id": None,
            "embed_url": None,
            "mode": "demo",
            "suggested_questions": _SUGGESTED_QUESTIONS,
        }
    host = get_workspace_host().rstrip("/")
    return {
        "space_id": GENIE_SPACE_ID,
        "embed_url": f"{host}/embed/genie/rooms/{GENIE_SPACE_ID}",
        "mode": "live",
        "suggested_questions": LIVE_SUGGESTED_QUESTIONS or _SUGGESTED_QUESTIONS,
    }


class AskBody(BaseModel):
    content: str
    conversation_id: Optional[str] = None


def _api_do(method: str, path: str, body: Optional[dict] = None) -> Any:
    w = get_workspace_client()
    return w.api_client.do(method, path, body=body or {})


def _poll_until_done(conv_id: str, msg_id: str, max_seconds: int = 90) -> dict:
    """Poll a Genie message until status reaches a terminal state."""
    terminal = {"COMPLETED", "FAILED", "CANCELLED", "EXECUTING_QUERY_FAILED", "ERROR"}
    for i in range(max_seconds):
        msg = _api_do(
            "GET",
            f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/conversations/{conv_id}/messages/{msg_id}",
        )
        status = (msg.get("status") or "").upper()
        if status in terminal:
            return msg
        time.sleep(1)
    # Timed out — return last we saw
    return msg


def _fetch_query_results(conv_id: str, msg_id: str, attachments: list[dict]) -> list[dict]:
    """For each attachment that has a SQL query, fetch the result rows.

    Returns the original attachments list with `query_result` added when applicable.
    """
    enriched: list[dict] = []
    for att in attachments:
        att_copy = dict(att)
        att_id = att.get("attachment_id") or att.get("id")
        if att_id and att.get("query"):
            try:
                result = _api_do(
                    "GET",
                    f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/conversations/{conv_id}/messages/{msg_id}/attachments/{att_id}/query-result",
                )
                # Trim the result for transport
                sr = result.get("statement_response") or result
                manifest = sr.get("manifest") or {}
                data = sr.get("result") or {}
                schema = manifest.get("schema") or {}
                cols = [c.get("name") for c in schema.get("columns", [])]
                rows = data.get("data_array") or []
                # Cap rows for the chat UI
                att_copy["query_result"] = {
                    "columns": cols,
                    "rows": rows[:50],
                    "row_count": len(rows),
                    "truncated": len(rows) > 50,
                }
            except Exception as exc:
                att_copy["query_result_error"] = str(exc)
        enriched.append(att_copy)
    return enriched


@router.post("/api/genie/ask")
def ask(body: AskBody, request: Request):
    """Send a question to Genie. Starts a new conversation if no conversation_id,
    else appends a message to the existing one. Blocks until Genie responds (≤90s).

    Returns: { conversation_id, message_id, text, sql, query_result, status }.
    """
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    # ---- Demo mode: answer from canned_genie.json --------------------------
    if not GENIE_SPACE_ID:
        ans = _match_canned(content)
        if not ans:
            return {
                "conversation_id": "demo",
                "message_id": "demo",
                "status": "COMPLETED",
                "mode": "demo",
                "text": "Modo demostración: no hay una respuesta preconfigurada para esa pregunta. "
                        "Prueba una de las preguntas sugeridas, o conecta un Genie Space real "
                        "(ver docs/GENIE.md).",
                "sql": None,
                "query_result": None,
                "error": None,
            }
        return {
            "conversation_id": body.conversation_id or "demo",
            "message_id": ans["id"],
            "status": "COMPLETED",
            "mode": "demo",
            "text": ans.get("text", ""),
            "sql": ans.get("sql"),
            "query_result": ans.get("query_result"),
            "error": None,
        }

    started = time.monotonic()
    user_email = get_current_user_email(request=request)
    try:
        if body.conversation_id:
            # Follow-up message in an existing conversation
            resp = _api_do(
                "POST",
                f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/conversations/{body.conversation_id}/messages",
                body={"content": content},
            )
            conv_id = body.conversation_id
            msg_id = resp.get("id") or resp.get("message_id")
        else:
            # New conversation
            resp = _api_do(
                "POST",
                f"/api/2.0/genie/spaces/{GENIE_SPACE_ID}/start-conversation",
                body={"content": content},
            )
            conv_id = resp.get("conversation_id") or (resp.get("conversation") or {}).get("id")
            msg_id = resp.get("message_id") or (resp.get("message") or {}).get("id")

        if not conv_id or not msg_id:
            raise HTTPException(
                status_code=502,
                detail=f"Genie did not return conversation/message ids: {resp}",
            )

        msg = _poll_until_done(conv_id, msg_id)

        # Extract main fields. Genie's `msg.content` is the user's echoed prompt, not
        # the assistant's reply — the reply lives inside attachments (text.content
        # for prose, query.description for SQL-backed answers).
        attachments = msg.get("attachments") or []
        attachments = _fetch_query_results(conv_id, msg_id, attachments)
        status = (msg.get("status") or "UNKNOWN").upper()

        text = ""
        sql = None
        primary_result = None
        for att in attachments:
            if not text:
                att_text = att.get("text") or {}
                if isinstance(att_text, dict) and att_text.get("content"):
                    text = att_text["content"]
            q = att.get("query") or {}
            if q.get("query") and not sql:
                sql = q.get("query")
            if not text and isinstance(q, dict) and q.get("description"):
                text = q["description"]
            if att.get("query_result") and not primary_result:
                primary_result = att["query_result"]

        # Last-resort fallback when there are no attachments at all (rare)
        if not text and not attachments:
            text = msg.get("content") or ""

        error = (msg.get("error") or {}).get("error") if status in {"FAILED", "ERROR", "EXECUTING_QUERY_FAILED"} else None
        duration_ms = int((time.monotonic() - started) * 1000)

        lakebase.log_genie_interaction(
            conversation_id=conv_id,
            message_id=str(msg_id),
            user_email=user_email,
            question=content,
            answer=text or None,
            sql_query=sql,
            status=status,
            row_count=(primary_result or {}).get("row_count"),
            has_result=bool(primary_result),
            error=error,
            duration_ms=duration_ms,
        )

        return {
            "conversation_id": conv_id,
            "message_id": msg_id,
            "status": status,
            "mode": "live",
            "text": text,
            "sql": sql,
            "query_result": primary_result,
            "error": error,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Genie call failed: {exc}") from exc
