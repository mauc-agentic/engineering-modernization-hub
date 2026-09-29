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
    instancia. `EMH_ENV` elige los adaptadores de los puertos `RunRepository`
    y `Sandbox` (NFR-025) sin tocar `emh.core` ni `emh.agent`:

    - `local` (por defecto): SQLite + Docker (ADR-004, ADR-005).
    - `aws`: RDS Postgres + tarea Fargate efímera (ADR-006, ADR-007).
    """

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        modo_simulado: bool | None = None,
    ) -> None:
        self.data_dir = data_dir or Path(os.environ.get("EMH_DATA_DIR", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.entorno_despliegue = os.environ.get("EMH_ENV", "local")
        if self.entorno_despliegue not in ("local", "aws"):
            raise ValueError(f"EMH_ENV debe ser 'local' o 'aws', no '{self.entorno_despliegue}'")
        self.repo: RunRepository = self._construir_repositorio()
        self.gate = PolicyGate(EJECUTABLES_GLOBALES)

        modo_simulado = modo_simulado if modo_simulado is not None else os.environ.get("EMH_MODO_SIMULADO") == "1"
        self.modelo: ModelPort = self._construir_modelo(modo_simulado)
        self.sandbox: Sandbox = self._construir_sandbox()

        self.entorno = Entorno(
            repo=self.repo, modelo=self.modelo, gate=self.gate, sandbox=self.sandbox,
            workspace_root_para=self._workspace_root_para,
            usar_wheelhouse=True,  # sandbox real (Docker o Fargate): instalar sin red externa (ADR-005/D-6)
        )
        self.runner = LangGraphAgentRunner(self.entorno, checkpointer=MemorySaver())
        self.reporte = ReportRenderer(self.repo, modelo=self.modelo)

    @staticmethod
    def _variable(nombre: str) -> str:
        valor = os.environ.get(nombre)
        if not valor:
            raise RuntimeError(f"EMH_ENV=aws exige la variable de entorno {nombre}")
        return valor

    def _construir_repositorio(self) -> RunRepository:
        if self.entorno_despliegue == "local":
            return SqliteRunRepository(self.data_dir / "emh.db")
        from urllib.parse import quote

        from emh.persistence.postgres_repo import PostgresRunRepository

        v = self._variable
        dsn = (
            f"postgresql://{quote(v('EMH_DB_USER'), safe='')}:{quote(v('EMH_DB_PASSWORD'), safe='')}"
            f"@{v('EMH_DB_HOST')}:{os.environ.get('EMH_DB_PORT', '5432')}/{v('EMH_DB_NAME')}?sslmode={os.environ.get('EMH_DB_SSLMODE', 'require')}"
        )
        return PostgresRunRepository(dsn)

    def _workspace_root_para(self, ejecucion_id: int) -> Path:
        ws = self.data_dir / "workspaces" / str(ejecucion_id)
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def _construir_modelo(self, modo_simulado: bool) -> ModelPort:
        if modo_simulado:
            from emh.models.scripted import ScriptedModel

            return ScriptedModel([])  # se reemplaza en pruebas; en la demo real, modo_simulado=False
        from emh.models.bedrock import MODEL_ID_DEFECTO, REGION_DEFECTO, BedrockModel

        return BedrockModel(
            model_id=os.environ.get("EMH_BEDROCK_MODEL_ID", MODEL_ID_DEFECTO),
            region=os.environ.get("AWS_REGION", REGION_DEFECTO),
        )

    def _construir_sandbox(self) -> Sandbox:
        if self.entorno_despliegue == "local":
            from emh.execution.docker_sandbox import DockerSandbox

            return DockerSandbox()
        from emh.execution.fargate_sandbox import FargateSandbox

        v = self._variable
        return FargateSandbox(
            cluster=v("EMH_ECS_CLUSTER"), task_definition=v("EMH_SANDBOX_TASK_DEFINITION"),
            subredes=v("EMH_SUBNET_IDS").split(","), security_group=v("EMH_SANDBOX_SECURITY_GROUP"),
            bucket=v("EMH_JOBS_BUCKET"), region=os.environ.get("AWS_REGION"),
        )

    def cerrar(self) -> None:
        if hasattr(self.repo, "close"):
            self.repo.close()
