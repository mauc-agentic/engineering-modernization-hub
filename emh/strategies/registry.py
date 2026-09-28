"""Registro de estrategias (DOCS/06-estrategias.md §1). El único lugar que
conoce todas las estrategias concretas; núcleo/agente/harness resuelven por
`id`, nunca importan una estrategia directamente (RN-13)."""

from __future__ import annotations

from emh.core.ports import ModernizationStrategy
from emh.strategies.python_dependency_upgrade import PythonDependencyUpgradeStrategy

REGISTRO_ESTRATEGIAS: dict[str, ModernizationStrategy] = {
    "python_dependency_upgrade": PythonDependencyUpgradeStrategy(),
}


def obtener_estrategia(estrategia_id: str) -> ModernizationStrategy | None:
    return REGISTRO_ESTRATEGIAS.get(estrategia_id)
