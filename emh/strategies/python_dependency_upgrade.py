"""Estrategia de referencia F1 (DOCS/06-estrategias.md §2): actualización de
una dependencia Python declarada en requirements.txt / pyproject.toml.

Solo devuelve datos (Protocol `ModernizationStrategy`, DOCS/03-arquitectura.md
§2). No ejecuta nada, no toca disco, red ni contenedor.
"""

from __future__ import annotations

import re

from emh.core.models import Solicitud, TipoFuente
from emh.core.ports import (
    DominioFuente,
    PaqueteInstrucciones,
    PerfilComandos,
    PlantillaAlcance,
    Senal,
    Soporte,
)

_VERSION_RE = re.compile(r"^[A-Za-z0-9_.\-]+(==|>=|<=|~=)?[A-Za-z0-9_.\-]*$")


class PythonDependencyUpgradeStrategy:
    id = "python_dependency_upgrade"

    def supports(self, request: Solicitud) -> Soporte:
        if not request.version_esperada or not _VERSION_RE.match(request.version_esperada.strip()):
            return Soporte(aplica=False, motivo="version_esperada no tiene forma de versión de paquete")
        return Soporte(aplica=True, motivo="objetivo referencia una dependencia Python")

    def discovery_signals(self) -> list[Senal]:
        return [
            Senal(patron="requirements.txt"),
            Senal(patron="pyproject.toml"),
            Senal(patron="*.lock"),
        ]

    def official_sources(self, request: Solicitud) -> list[DominioFuente]:
        return [
            DominioFuente(dominio="pypi.org", tipo=TipoFuente.REGISTRO_PAQUETES.value),
            DominioFuente(dominio="github.com", tipo=TipoFuente.RELEASE_NOTES.value),
        ]

    def command_profile(self) -> PerfilComandos:
        # El contenedor tiene la raíz de solo lectura (NFR-004): el venv se
        # crea en /tmp (tmpfs escribible), nunca en el site-packages de la
        # imagen. Las ruedas ya están en /wheelhouse, descargadas por el
        # host (ADR-005, decisión D-6) -- sin red dentro del contenedor.
        return PerfilComandos(
            instalacion=[
                ["python", "-m", "venv", "/tmp/venv"],
                ["/tmp/venv/bin/pip", "install", "--no-index",
                 "--find-links=/wheelhouse", "-r", "requirements.txt"],
            ],
            verificacion=[["/tmp/venv/bin/pytest", "-q", "--tb=short"]],
        )

    def scope_template(self, plan_hint: dict | None = None) -> PlantillaAlcance:
        rutas = ["requirements.txt"]
        if plan_hint and "modulos_afectados" in plan_hint:
            rutas.extend(plan_hint["modulos_afectados"])
        return PlantillaAlcance(rutas=rutas, operaciones=["modificar"])

    def prompt_pack(self) -> PaqueteInstrucciones:
        return PaqueteInstrucciones(
            instrucciones=(
                "Extrae el changelog entre la versión actual y la objetivo. "
                "Identifica breaking changes declarados. Relaciona cada breaking "
                "change con usos del paquete en el código fuente antes de decidir "
                "viabilidad. Nunca actualices transitivamente otras dependencias "
                "no solicitadas."
            )
        )
