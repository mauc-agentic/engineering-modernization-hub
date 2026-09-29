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
    SondaEvidencia,
    Soporte,
)

_PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-]+)$")
# Paquete + versión fija ("PyYAML==6.0.2") o un rango PEP 440 ("Flask>=3.0,<3.1").
_ESPECIFICADOR = r"(==|>=|<=|~=|!=|<|>)\s*[A-Za-z0-9_.*\-]+"
_VERSION_RE = re.compile(rf"^[A-Za-z0-9_.\-]+(\s*{_ESPECIFICADOR}(\s*,\s*{_ESPECIFICADOR})*)?$")


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

    def evidence_probes(self, request: Solicitud) -> list[SondaEvidencia]:
        # Metadatos oficiales de la versión objetivo: incluyen `requires_python`,
        # decisivo para la viabilidad frente al runtime del repo.
        m = _PIN_RE.match((request.version_esperada or "").strip())
        if not m:
            return []
        return [SondaEvidencia(dominio="pypi.org", consulta=f"pypi/{m.group(1)}/{m.group(2)}/json")]

    def command_profile(self) -> PerfilComandos:
        # El contenedor tiene la raíz de solo lectura (NFR-004): el venv se
        # crea en /tmp (tmpfs escribible), nunca en el site-packages de la
        # imagen. Las ruedas ya están en /wheelhouse, descargadas por el
        # host (ADR-005, decisión D-6) -- sin red dentro del contenedor.
        return PerfilComandos(
            instalacion=[
                ["python", "-m", "venv", "/tmp/venv"],
                ["/tmp/venv/bin/pip", "install", "--no-index",
                 "--find-links=/wheelhouse", "-r", "requirements.txt", "pytest"],
            ],
            verificacion=[["/tmp/venv/bin/pytest", "-q", "--tb=short"]],
            paquetes_herramienta=["pytest"],
        )

    def scope_template(self, plan_hint: dict | None = None) -> PlantillaAlcance:
        rutas = ["requirements.txt"]
        if plan_hint and "modulos_afectados" in plan_hint:
            rutas.extend(plan_hint["modulos_afectados"])
        # "crear" solo alcanza a rutas que el plan DECLARE y el humano apruebe (RN-05): permite añadir
        # una prueba nueva (FR-014); borrar sigue prohibido y el control 7 impide vaciar o des-activar pruebas.
        return PlantillaAlcance(rutas=rutas, operaciones=["modificar", "crear"])

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
