"""Contexto de política (DOCS/05-politicas-y-controles.md). Se construye por
el núcleo a partir de lo persistido, nunca de lo que el modelo afirme."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from emh.core.budget import EstadoPresupuesto
from emh.core.models import Plan


@dataclass
class ContextoPolitica:
    ejecucion_id: int
    workspace_root: Path
    plan_aprobado: Plan | None = None
    presupuesto: EstadoPresupuesto | None = None
    linea_base_pruebas: int = 0
