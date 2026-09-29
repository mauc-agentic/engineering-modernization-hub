"""Raíz de composición (DOCS/03-arquitectura.md §2). El único módulo que
conoce a todos los adaptadores concretos; nada más en `emh` importa
`boto3`, `docker` o `sqlite3` fuera de sus propios adaptadores."""

from __future__ import annotations

import os
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from emh.agent.graph import Entorno
from emh.agent.runner import LangGraphAgentRunner
from emh.core.ports import ModelPort, RunRepository, Sandbox
from emh.persistence.sqlite_repo import SqliteRunRepository
from emh.policy.gate import PolicyGate
from emh.reporting.renderer import ReportRenderer

# Allowlist global de ejecutables (control 2, 05-politicas-y-controles.md).
# La estrategia activa la intersecta con su propio perfil de comandos.
EJECUTABLES_GLOBALES = frozenset({"git", "pip", "python", "pytest"})


class Aplicacion:
    """Contenedor simple de las piezas ya cableadas. Un proceso = una
    instancia (F1: SQLite con un escritor, ADR-004)."""

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        modo_simulado: bool | None = None,
    ) -> None:
        self.data_dir = data_dir or Path(os.environ.get("EMH_DATA_DIR", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.repo: RunRepository = SqliteRunRepository(self.data_dir / "emh.db")
        self.gate = PolicyGate(EJECUTABLES_GLOBALES)

        modo_simulado = modo_simulado if modo_simulado is not None else os.environ.get("EMH_MODO_SIMULADO") == "1"
        self.modelo: ModelPort = self._construir_modelo(modo_simulado)
        self.sandbox: Sandbox = self._construir_sandbox()

        self.entorno = Entorno(
            repo=self.repo, modelo=self.modelo, gate=self.gate, sandbox=self.sandbox,
            workspace_root_para=self._workspace_root_para,
            usar_wheelhouse=True,  # sandbox Docker real: instalar sin red (ADR-005/D-6)
        )
        self.runner = LangGraphAgentRunner(self.entorno, checkpointer=MemorySaver())
        self.reporte = ReportRenderer(self.repo, modelo=self.modelo)

    def _workspace_root_para(self, ejecucion_id: int) -> Path:
        ws = self.data_dir / "workspaces" / str(ejecucion_id)
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def _construir_modelo(self, modo_simulado: bool) -> ModelPort:
        if modo_simulado:
            from emh.models.scripted import ScriptedModel

            return ScriptedModel([])  # se reemplaza en pruebas; en la demo real, modo_simulado=False
        from emh.models.bedrock import BedrockModel

        return BedrockModel()

    def _construir_sandbox(self) -> Sandbox:
        from emh.execution.docker_sandbox import DockerSandbox

        return DockerSandbox()

    def cerrar(self) -> None:
        if hasattr(self.repo, "close"):
            self.repo.close()
