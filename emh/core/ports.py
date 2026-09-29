"""Puertos del núcleo (DOCS/03-arquitectura.md §2).

Interfaces que el núcleo define y los adaptadores de la Capa 6 implementan.
El núcleo importa estos `Protocol`, nunca una implementación concreta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from emh.core.models import (
    CitaFuente,
    DecisionAprobacion,
    DecisionTecnica,
    Ejecucion,
    EventoSeguridad,
    Fuente,
    LlamadaModelo,
    Plan,
    Solicitud,
    Traza,
    Verificacion,
)

# ---------------------------------------------------------------------------
# ModelPort
# ---------------------------------------------------------------------------

NivelEsfuerzo = Literal["low", "medium", "high"]


@dataclass
class LlamadaHerramientaPropuesta:
    """Lo que el modelo propone invocar. Nunca se ejecuta directamente: pasa
    primero por `emh.harness` y `emh.policy` (RN-02, RN-03)."""

    id: str
    nombre: str
    argumentos: dict[str, Any]


@dataclass
class RespuestaModelo:
    texto: str | None
    llamadas_herramienta: list[LlamadaHerramientaPropuesta]
    tokens_entrada: int
    tokens_salida: int


class ModelPort(Protocol):
    """Ver ADR-002. Implementaciones: `emh.models.bedrock.BedrockModel`
    (Nova 2 Lite) y `emh.models.scripted.ScriptedModel` (SIMULATED, nivel A)."""

    def completar(
        self,
        *,
        mensajes: list[dict[str, Any]],
        sistema: str | None = None,
        herramientas: list[dict[str, Any]] | None = None,
        nivel_esfuerzo: NivelEsfuerzo = "low",
    ) -> RespuestaModelo: ...


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------


@dataclass
class ResultadoComando:
    codigo_salida: int
    salida: str


class Sandbox(Protocol):
    """Ver ADR-005 (local) y ADR-006 (nube). Un contenedor efímero por
    ejecución; `run_tests` es la única herramienta que lo usa."""

    def crear(self, workspace: Path) -> str:
        """Crea el contenedor/tarea y devuelve su identificador."""
        ...

    def ejecutar(
        self, identificador: str, comando: list[str], *, con_red: bool = False
    ) -> ResultadoComando: ...

    def ejecutar_secuencia(
        self, identificador: str, comandos: list[list[str]], *, con_red: bool = False
    ) -> list[ResultadoComando]:
        """Toda la secuencia (instalación + verificación) en el MISMO
        contenedor/tarea; se detiene tras un fallo que no sea el último paso.
        Opcional para dobles de prueba: `run_tests` cae a `ejecutar` si falta."""
        ...

    def destruir(self, identificador: str) -> None: ...


# ---------------------------------------------------------------------------
# ModernizationStrategy (ver DOCS/06-estrategias.md)
# ---------------------------------------------------------------------------


@dataclass
class Soporte:
    aplica: bool
    motivo: str = ""


@dataclass
class Senal:
    patron: str


@dataclass
class DominioFuente:
    dominio: str
    tipo: str  # ver TipoFuente


@dataclass
class PerfilComandos:
    instalacion: list[list[str]] = field(default_factory=list)
    verificacion: list[list[str]] = field(default_factory=list)
    paquetes_herramienta: list[str] = field(default_factory=list)
    """Herramientas de verificación que la estrategia necesita en el sandbox
    aunque el repo no las declare (p. ej. el ejecutor de pruebas): el host las
    descarga al wheelhouse y así el manifiesto del cliente no se contamina."""


@dataclass
class PlantillaAlcance:
    rutas: list[str]
    operaciones: list[str]


@dataclass
class SondaEvidencia:
    """Fuente oficial que el harness DEBE consultar antes del análisis de
    viabilidad (la estrategia sabe cuál es la evidencia determinante; el
    modelo decide qué significa, no si se consulta)."""

    dominio: str
    consulta: str


@dataclass
class PaqueteInstrucciones:
    instrucciones: str


class ModernizationStrategy(Protocol):
    id: str

    def supports(self, request: Solicitud) -> Soporte: ...
    def discovery_signals(self) -> list[Senal]: ...
    def official_sources(self, request: Solicitud) -> list[DominioFuente]: ...
    def evidence_probes(self, request: Solicitud) -> list[SondaEvidencia]: ...
    def command_profile(self) -> PerfilComandos: ...
    def scope_template(self, plan_hint: dict[str, Any] | None = None) -> PlantillaAlcance: ...
    def prompt_pack(self) -> PaqueteInstrucciones: ...


# ---------------------------------------------------------------------------
# RunRepository
# ---------------------------------------------------------------------------


class RunRepository(Protocol):
    """Ver ADR-004 (SQLite) y ADR-007 (RDS Postgres). SQL parametrizado,
    nunca interpolación de cadenas."""

    def guardar_solicitud(self, solicitud: Solicitud) -> Solicitud: ...
    def obtener_solicitud(self, solicitud_id: int) -> Solicitud | None: ...

    def guardar_ejecucion(self, ejecucion: Ejecucion) -> Ejecucion: ...
    def actualizar_ejecucion(self, ejecucion: Ejecucion) -> Ejecucion: ...
    def obtener_ejecucion(self, ejecucion_id: int) -> Ejecucion | None: ...

    def guardar_plan(self, plan: Plan) -> Plan: ...
    def actualizar_estado_plan(self, plan_id: int, estado: str) -> None: ...
    def obtener_plan_vigente(self, ejecucion_id: int) -> Plan | None: ...
    def listar_planes(self, ejecucion_id: int) -> list[Plan]: ...

    def guardar_decision_aprobacion(self, decision: DecisionAprobacion) -> DecisionAprobacion: ...
    def obtener_decision_aprobacion_vigente(self, plan_id: int) -> DecisionAprobacion | None: ...

    def guardar_decision_tecnica(self, decision: DecisionTecnica) -> DecisionTecnica: ...
    def listar_decisiones_tecnicas(self, ejecucion_id: int) -> list[DecisionTecnica]: ...

    def guardar_fuente(self, fuente: Fuente) -> Fuente: ...
    def listar_fuentes(self, ejecucion_id: int) -> list[Fuente]: ...

    def guardar_cita_fuente(self, cita: CitaFuente) -> CitaFuente: ...
    def listar_citas(self, decision_tecnica_id: int) -> list[CitaFuente]: ...

    def guardar_verificacion(self, verificacion: Verificacion) -> Verificacion: ...
    def listar_verificaciones(self, ejecucion_id: int) -> list[Verificacion]: ...

    def guardar_evento_seguridad(self, evento: EventoSeguridad) -> EventoSeguridad: ...
    def listar_eventos_seguridad(self, ejecucion_id: int) -> list[EventoSeguridad]: ...

    def guardar_llamada_modelo(self, llamada: LlamadaModelo) -> LlamadaModelo: ...
    def listar_llamadas_modelo(self, ejecucion_id: int) -> list[LlamadaModelo]: ...
    def guardar_traza(self, traza: Traza) -> Traza: ...
    def listar_trazas(self, ejecucion_id: int) -> list[Traza]: ...


# ---------------------------------------------------------------------------
# ReportRenderer / AgentRunner
# ---------------------------------------------------------------------------


class ReportRenderer(Protocol):
    def render(self, ejecucion_id: int) -> dict[str, Any]: ...


class AgentRunner(Protocol):
    """Implementado por `emh.agent` (LangGraph). El núcleo lo invoca sin
    saber qué framework hay detrás (ADR-003)."""

    def run(self, ejecucion_id: int) -> None: ...
    def resume(self, ejecucion_id: int) -> None: ...
