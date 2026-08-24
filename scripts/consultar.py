#!/usr/bin/env python3
"""Ejecuta SQL contra el SQL Warehouse de la instalación y lo imprime como tabla.

No se invoca directo: `scripts/consultar.sh` le pasa el perfil, el warehouse y el
esquema que resolvió del bundle.

    ./scripts/consultar.sh "SELECT * FROM {S}.visitas LIMIT 5"
    echo "SELECT 1" | ./scripts/consultar.sh
    ./scripts/consultar.sh --json "SELECT * FROM {S}.recomendaciones LIMIT 3"

`{S}` se expande al esquema completo (catálogo.esquema), así las consultas de
ejemplo de la documentación corren en cualquier workspace sin editar nada.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile


def run_sql(profile: str, warehouse: str, statement: str) -> tuple[list[str], list[list]]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(
            {"warehouse_id": warehouse, "statement": statement, "wait_timeout": "50s"}, f
        )
        path = f.name
    try:
        proc = subprocess.run(
            ["databricks", "api", "post", "/api/2.0/sql/statements",
             "-p", profile, "--json", f"@{path}"],
            capture_output=True, text=True,
        )
    finally:
        os.unlink(path)
    if proc.returncode != 0:
        raise SystemExit(f"❌ CLI falló: {proc.stderr.strip()[:600]}")
    payload = json.loads(proc.stdout)
    state = payload.get("status", {}).get("state")
    if state != "SUCCEEDED":
        raise SystemExit(f"❌ query {state}: {json.dumps(payload.get('status', {}))[:600]}")
    cols = [c["name"] for c in payload.get("manifest", {}).get("schema", {}).get("columns", [])]
    return cols, payload.get("result", {}).get("data_array") or []


def render(cols: list[str], rows: list[list]) -> str:
    if not cols:
        return "(sin filas)"
    cells = [[("" if v is None else str(v)) for v in r] for r in rows]
    widths = [
        min(48, max(len(c), *(len(r[i]) for r in cells)) if cells else len(c))
        for i, c in enumerate(cols)
    ]
    out = [" | ".join(c[:w].ljust(w) for c, w in zip(cols, widths))]
    out.append("-+-".join("-" * w for w in widths))
    for r in cells:
        out.append(" | ".join(v[:w].ljust(w) for v, w in zip(r, widths)))
    out.append(f"({len(rows)} filas)")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sql", nargs="?", help="consulta; si se omite, se lee de stdin")
    ap.add_argument("--json", action="store_true", help="salida JSON en vez de tabla")
    args = ap.parse_args()

    statement = args.sql or sys.stdin.read()
    if not statement.strip():
        raise SystemExit("❌ No recibí ninguna consulta.")

    profile = os.environ.get("PROFILE") or os.environ.get("DATABRICKS_PROFILE") or "DEFAULT"
    warehouse = os.environ.get("WAREHOUSE_ID")
    if not warehouse:
        raise SystemExit("❌ WAREHOUSE_ID no está definido — usá ./scripts/consultar.sh")
    fq = os.environ.get("FQ_SCHEMA") or (
        f"{os.environ.get('CATALOG', 'main')}.{os.environ.get('SCHEMA', 'ditcher_neira')}"
    )

    cols, rows = run_sql(profile, warehouse, statement.replace("{S}", fq))
    if args.json:
        print(json.dumps([dict(zip(cols, r)) for r in rows], indent=2, ensure_ascii=False))
    else:
        print(render(cols, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
