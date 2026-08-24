"""Feed de recomendaciones de los agentes y registro de decisiones.

Las recomendaciones y el log de decisiones viven en Delta (Unity Catalog): son
escrituras de baja frecuencia con valor de auditoría. El camino caliente de
sugerencias al mercaderista, en cambio, corre sobre Lakebase — ver
`routes/lakebase_studio.py`.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..config import FQ, get_current_user_email
from ..uc import query as uc_query, execute as uc_execute

router = APIRouter()


def _safe_json(s):
    if s is None:
        return None
    if isinstance(s, (dict, list)):
        return s
    try:
        return json.loads(s)
    except Exception:
        return s


def _sql_str(s: Optional[str]) -> str:
    if s is None:
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


@router.get("/api/recommendations")
def list_recommendations(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="filter: pending|approved|rejected"),
    agent: Optional[str] = Query(None, description="filter por agent_name"),
    acciones: Optional[str] = Query(
        None,
        description="tipos de suggested_action.type admitidos, separados por coma",
    ),
):
    filtros = []
    if agent:
        filtros.append("r.agent_name = '" + agent.replace("'", "''") + "'")
    if acciones:
        # Cada pantalla vive en su dominio: la de marca no puede mostrar una
        # acción de reposición aunque la haya escrito su propio agente. El filtro
        # es por tipo de acción y no por agente porque es la acción la que dice
        # quién puede ejecutarla.
        tipos = [t.strip().replace("'", "''") for t in acciones.split(",") if t.strip()]
        if tipos:
            lista = ", ".join(f"'{t}'" for t in tipos)
            filtros.append(
                f"GET_JSON_OBJECT(r.suggested_action, '$.type') IN ({lista})"
            )
    agent_filter = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    sql = f"""
        WITH latest_action AS (
          SELECT recommendation_id, action, actor, notes, occurred_at,
                 ROW_NUMBER() OVER (PARTITION BY recommendation_id ORDER BY occurred_at DESC) AS rn
          FROM {FQ}.action_log
        )
        SELECT r.id, r.agent_name, r.severity, r.title, r.analysis, r.recommendation,
               r.suggested_action, r.supporting_data, r.created_at,
               la.action AS decision_action, la.actor AS decision_actor,
               la.notes AS decision_notes, la.occurred_at AS decision_at
        FROM {FQ}.recomendaciones r
        LEFT JOIN latest_action la ON la.recommendation_id = r.id AND la.rn = 1
        {agent_filter}
        ORDER BY r.created_at DESC
        LIMIT {int(limit) * 2}
    """
    try:
        rows = uc_query(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC query failed: {exc}") from exc

    out = []
    for r in rows:
        decision_action = r.get("decision_action")
        status_val = decision_action.lower() if decision_action else "pending"
        if status and status.lower() != status_val:
            continue
        out.append({
            "id": r["id"],
            "agent_name": r.get("agent_name"),
            "severity": r.get("severity"),
            "title": r.get("title"),
            "analysis": r.get("analysis"),
            "recommendation": r.get("recommendation"),
            "suggested_action": _safe_json(r.get("suggested_action")),
            "supporting_data": _safe_json(r.get("supporting_data")),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "status": status_val,
            "decision": (
                {
                    "action": decision_action,
                    "actor": r.get("decision_actor"),
                    "notes": r.get("decision_notes"),
                    "occurred_at": (
                        r["decision_at"].isoformat() if r.get("decision_at") else None
                    ),
                }
                if decision_action
                else None
            ),
        })
        if len(out) >= limit:
            break
    return out


class Decision(BaseModel):
    action: str = Field(..., pattern="^(APPROVED|REJECTED|approved|rejected)$")
    notes: Optional[str] = None


@router.post("/api/recommendations/{rec_id}/decide")
def decide(rec_id: str, body: Decision, request: Request):
    actor = get_current_user_email(request)
    action = body.action.upper()
    log_id = f"act_{uuid.uuid4().hex[:14]}"
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")

    sql = f"""
        INSERT INTO {FQ}.action_log
          (id, recommendation_id, action, actor, notes, occurred_at)
        VALUES (
          '{log_id}', '{rec_id.replace("'", "")}', '{action}',
          {_sql_str(actor)}, {_sql_str(body.notes)}, '{now_iso}'
        )
    """
    try:
        uc_execute(sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"UC insert failed: {exc}") from exc

    return {"ok": True, "log_id": log_id, "rec_id": rec_id, "action": action, "actor": actor}
