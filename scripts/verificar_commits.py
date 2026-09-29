#!/usr/bin/env python3
"""NFR-022 — Commits trazables: todo commit de IMPLEMENTACIÓN cita un ID del catálogo de requisitos.

Regla (documentada en DOCS/GLOSARIO.md): los commits cuyo tipo es `feat`, `fix`, `test`, `refactor` o `perf`
deben citar al menos un ID (FR-, NFR-, C-, RN-, AC-, UC-, TC-, ADR- o D-). Los de tipo `docs`, `chore`, `ci`,
`build`, `style`, `revert` y los merges quedan exentos. Se aplica desde la auditoría del 2026-09-29; el historial
anterior cumplía solo en parte (ver DOCS/AUDITORIA.md).

Uso:
  scripts/verificar_commits.py <rango-git>        p. ej. origin/main..HEAD  (CI)
  scripts/verificar_commits.py --archivo <ruta>   mensaje de un commit en curso (hook `commit-msg`)
"""

from __future__ import annotations

import re
import subprocess
import sys

ID = re.compile(r"\b(?:FR|NFR|RN|AC|UC|TC|ADR|BR)-\d{1,3}\b|\b(?:C|D)-\d{1,3}\b")
TIPO_IMPLEMENTACION = re.compile(r"^(feat|fix|test|refactor|perf)(\([^)]*\))?!?:", re.IGNORECASE)


def evaluar(mensaje: str) -> str | None:
    """Devuelve el motivo del rechazo, o None si el mensaje cumple."""
    asunto = mensaje.strip().splitlines()[0] if mensaje.strip() else ""
    if asunto.lower().startswith(("merge", "revert")):
        return None
    if TIPO_IMPLEMENTACION.match(asunto) and not ID.search(mensaje):
        return (
            f"'{asunto[:70]}' es un commit de implementación y no cita ningún ID del catálogo "
            "(p. ej. FR-013, NFR-022, ADR-008). Añádelo al asunto o al cuerpo."
        )
    return None


def _mensajes_del_rango(rango: str) -> list[tuple[str, str]]:
    ok = subprocess.run(["git", "rev-parse", "--verify", "--quiet", rango.split("..")[0]], capture_output=True, check=False)
    if ok.returncode != 0:  # p. ej. el `before` de un push forzado no existe en el clon: solo se revisa HEAD
        rango = "HEAD~1..HEAD"
    hashes = subprocess.run(["git", "rev-list", "--no-merges", rango], capture_output=True, text=True, check=True).stdout.split()
    return [
        (h[:7], subprocess.run(["git", "log", "-1", "--format=%B", h], capture_output=True, text=True, check=True).stdout)
        for h in hashes
    ]


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--archivo":
        with open(argv[2], encoding="utf-8") as f:
            motivo = evaluar(f.read())
        if motivo:
            print(f"NFR-022: {motivo}", file=sys.stderr)
        return 1 if motivo else 0
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    fallos = [(h, m) for h, msg in _mensajes_del_rango(argv[1]) if (m := evaluar(msg))]
    for h, motivo in fallos:
        print(f"NFR-022: {h}: {motivo}", file=sys.stderr)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
