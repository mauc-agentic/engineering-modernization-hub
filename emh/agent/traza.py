"""Observabilidad del agente (NFR-014): `medir` registra un tramo -- nodo del
grafo, llamada al modelo o herramienta -- con su duración real, en la base de
datos de la ejecución (visible en el dashboard y por la API).

Es el ÚNICO punto de instrumentación: la exportación a OpenTelemetry/CloudWatch
(AgentCore Observability) se engancha aquí, no esparcida por el código.

Además emite un span de OpenTelemetry por tramo (si `opentelemetry-api` está
instalado, como en la imagen de la API con ADOT): con `AGENT_OBSERVABILITY_ENABLED`
el ADOT lo exporta a CloudWatch (AgentCore Observability, vista GenAI). Los spans
llevan las convenciones `gen_ai.*` para el modelo y NUNCA el contenido de prompts,
archivos o salidas. Sin OpenTelemetry instalado o configurado es un no-op.

Reglas: (1) jamás rompe una ejecución -- un fallo al guardar la traza solo se
loguea; (2) jamás guarda contenido (prompts, archivos, salidas): solo nombres,
tiempos, tokens y una nota corta ya redactada."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from emh.core.models import Traza, utcnow
from emh.core.ports import RunRepository

logger = logging.getLogger(__name__)

try:  # opcional: solo está en la imagen de la nube (extra `observabilidad`) y en pruebas
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import Status, StatusCode

    _tracer = _otel_trace.get_tracer("emh.agente")
except ImportError:  # pragma: no cover - entorno sin OpenTelemetry
    _tracer = None

# LangGraph pausa el grafo lanzando una excepción de interrupción: no es un error.
_PAUSAS = frozenset({"GraphInterrupt", "NodeInterrupt"})


@dataclass
class Tramo:
    ok: bool = True
    detalle: str | None = None
    tokens_entrada: int = 0
    tokens_salida: int = 0


@contextmanager
def medir(repo: RunRepository, ejecucion_id: int, tipo: str, nombre: str) -> Iterator[Tramo]:
    tramo = Tramo()
    inicio = utcnow()
    t0 = time.perf_counter()
    span = _abrir_span(ejecucion_id, tipo, nombre)
    try:
        yield tramo
    except BaseException as exc:
        if type(exc).__name__ in _PAUSAS:
            tramo.detalle = tramo.detalle or "pausa: espera de decisión humana"
        else:
            tramo.ok = False
            tramo.detalle = tramo.detalle or type(exc).__name__
        raise
    finally:
        _cerrar_span(span, tipo, tramo)
        try:
            repo.guardar_traza(Traza(
                ejecucion_id=ejecucion_id, tipo=tipo, nombre=nombre[:100], inicio=inicio,
                duracion_ms=int((time.perf_counter() - t0) * 1000), ok=tramo.ok,
                tokens_entrada=tramo.tokens_entrada, tokens_salida=tramo.tokens_salida,
                detalle=(tramo.detalle or None) and tramo.detalle[:300],
            ))
        except Exception:
            logger.exception("ejecución %s: no se pudo guardar la traza de %s/%s", ejecucion_id, tipo, nombre)


def _abrir_span(ejecucion_id: int, tipo: str, nombre: str):
    """Span hijo del que esté activo (la ejecución > el nodo > el modelo/la herramienta)."""
    if _tracer is None:
        return None
    try:
        cm = _tracer.start_as_current_span(f"{tipo}:{nombre}")
        span = cm.__enter__()
        span.set_attribute("emh.ejecucion_id", ejecucion_id)
        span.set_attribute("emh.tipo", tipo)
        span.set_attribute("emh.nombre", nombre)
        if tipo == "modelo":
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.system", "aws.bedrock")
        return cm, span
    except Exception:
        logger.exception("no se pudo abrir el span de OpenTelemetry")
        return None


def _cerrar_span(handle, tipo: str, tramo: Tramo) -> None:
    if handle is None:
        return
    cm, span = handle
    try:
        if tipo == "modelo":
            span.set_attribute("gen_ai.usage.input_tokens", tramo.tokens_entrada)
            span.set_attribute("gen_ai.usage.output_tokens", tramo.tokens_salida)
        if tramo.detalle:
            span.set_attribute("emh.detalle", tramo.detalle[:300])
        span.set_attribute("emh.ok", tramo.ok)
        if not tramo.ok:
            span.set_status(Status(StatusCode.ERROR, tramo.detalle or "error"))
        cm.__exit__(None, None, None)
    except Exception:
        logger.exception("no se pudo cerrar el span de OpenTelemetry")
