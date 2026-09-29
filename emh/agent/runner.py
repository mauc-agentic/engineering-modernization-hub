"""`LangGraphAgentRunner` -- implementa `emh.core.ports.AgentRunner`
(ADR-003). El *checkpointer* lleva memoria de trabajo entre `run()` y
`resume()`; la máquina de estados del núcleo sigue siendo la fuente de
verdad del estado de negocio (DOCS/03-arquitectura.md §3.1)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from emh.agent.graph import Entorno, _finalizar, construir_grafo
from emh.core.models import ResultadoEjecucion

logger = logging.getLogger(__name__)


@contextmanager
def _span_de_ejecucion(ejecucion_id: int) -> Iterator[None]:
    """Span raíz `ejecucion` y `session.id` en el baggage: AgentCore Observability
    agrupa por sesión, y cada ejecución es una sesión. No-op sin OpenTelemetry."""
    try:
        from opentelemetry import baggage, context, trace
    except ImportError:
        yield
        return
    token = context.attach(baggage.set_baggage("session.id", f"ejecucion-{ejecucion_id}"))
    try:
        with trace.get_tracer("emh.agente").start_as_current_span("ejecucion") as span:
            span.set_attribute("emh.ejecucion_id", ejecucion_id)
            span.set_attribute("session.id", f"ejecucion-{ejecucion_id}")
            yield
    finally:
        context.detach(token)


class LangGraphAgentRunner:
    def __init__(self, entorno: Entorno, checkpointer: BaseCheckpointSaver | None = None) -> None:
        self._entorno = entorno
        self._checkpointer = checkpointer or MemorySaver()
        self._grafo = construir_grafo(entorno).compile(checkpointer=self._checkpointer)

    def _config(self, ejecucion_id: int) -> dict:
        return {"configurable": {"thread_id": str(ejecucion_id)}}

    def _controlado(self, ejecucion_id: int, accion: Callable[[], object]) -> None:
        """RN-11: una excepción inesperada (Bedrock, red, el sandbox de nube)
        no deja la ejecución colgada en un estado intermedio: termina como
        FALLIDO_CONTROLADO y el detalle queda en el log del servicio."""
        try:
            with _span_de_ejecucion(ejecucion_id):
                accion()
        except Exception:
            logger.exception("ejecución %s: error inesperado; se finaliza de forma controlada", ejecucion_id)
            try:
                _finalizar(self._entorno, ejecucion_id, ResultadoEjecucion.FALLIDO_CONTROLADO)
            except Exception:
                logger.exception("ejecución %s: no se pudo registrar el cierre controlado", ejecucion_id)

    def run(self, ejecucion_id: int) -> None:
        self._controlado(ejecucion_id, lambda: self._grafo.invoke(
            {"ejecucion_id": ejecucion_id, "mensajes": [], "archivos_relevantes": []},
            config=self._config(ejecucion_id),
        ))

    def resume(self, ejecucion_id: int) -> None:
        """Reanuda tras la interrupción de `compuerta_aprobacion`. La
        decisión real ya está persistida (RN-01); este `Command.resume` solo
        despierta al grafo -- el nodo relee la decisión desde `repo`."""
        self._controlado(ejecucion_id, lambda: self._grafo.invoke(
            Command(resume=True), config=self._config(ejecucion_id)
        ))
