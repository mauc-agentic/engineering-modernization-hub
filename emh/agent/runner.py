"""`LangGraphAgentRunner` -- implementa `emh.core.ports.AgentRunner`
(ADR-003). El *checkpointer* lleva memoria de trabajo entre `run()` y
`resume()`; la máquina de estados del núcleo sigue siendo la fuente de
verdad del estado de negocio (DOCS/03-arquitectura.md §3.1)."""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from emh.agent.graph import Entorno, construir_grafo


class LangGraphAgentRunner:
    def __init__(self, entorno: Entorno, checkpointer: BaseCheckpointSaver | None = None) -> None:
        self._entorno = entorno
        self._checkpointer = checkpointer or MemorySaver()
        self._grafo = construir_grafo(entorno).compile(checkpointer=self._checkpointer)

    def _config(self, ejecucion_id: int) -> dict:
        return {"configurable": {"thread_id": str(ejecucion_id)}}

    def run(self, ejecucion_id: int) -> None:
        self._grafo.invoke(
            {"ejecucion_id": ejecucion_id, "mensajes": []}, config=self._config(ejecucion_id)
        )

    def resume(self, ejecucion_id: int) -> None:
        """Reanuda tras la interrupción de `compuerta_aprobacion`. La
        decisión real ya está persistida (RN-01); este `Command.resume` solo
        despierta al grafo -- el nodo relee la decisión desde `repo`."""
        self._grafo.invoke(Command(resume=True), config=self._config(ejecucion_id))
