"""LLM client — OpenAI-compatible wrapper around Databricks Foundation Model API.

Used by the live drill-down explain endpoint. Reuses the app's WorkspaceClient,
so in Databricks Apps it goes through the service principal; locally through
the dev profile.
"""
from __future__ import annotations

import os
from functools import lru_cache

from .config import get_workspace_client

# Configurables por entorno para que el repo corra en workspaces donde estos
# endpoints no estén disponibles.
LLM_ENDPOINT = os.environ.get(
    "LLM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct"
)
EXPLAIN_LLM_ENDPOINT = os.environ.get(
    "EXPLAIN_LLM_ENDPOINT", "databricks-claude-sonnet-4-6"
)


@lru_cache(maxsize=1)
def get_openai_client():
    """OpenAI-compatible client for Databricks serving endpoints."""
    w = get_workspace_client()
    return w.serving_endpoints.get_open_ai_client()
