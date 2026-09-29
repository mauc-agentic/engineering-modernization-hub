"""Observabilidad con OpenTelemetry: `medir` emite un span por tramo con la
jerarquía ejecución > nodo > modelo/herramienta, atributos gen_ai.* y sin
contenido de prompts. Se prueba con el SDK real y un exportador en memoria."""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

import emh.agent.traza as traza_mod
from emh.agent.runner import _span_de_ejecucion
from emh.agent.traza import medir
from emh.persistence.sqlite_repo import SqliteRunRepository
from tests.factories import ejecucion, solicitud


@pytest.fixture()
def exportador(monkeypatch):
    exp = InMemorySpanExporter()
    proveedor = TracerProvider()
    proveedor.add_span_processor(SimpleSpanProcessor(exp))
    monkeypatch.setattr(traza_mod, "_tracer", proveedor.get_tracer("prueba"))
    monkeypatch.setattr(trace, "get_tracer", lambda *_a, **_k: proveedor.get_tracer("prueba"))
    return exp


@pytest.fixture()
def repo(tmp_path):
    r = SqliteRunRepository(tmp_path / "t.db")
    yield r
    r.close()


def _ejecucion(repo):
    s = repo.guardar_solicitud(solicitud())
    return repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))


def test_jerarquia_ejecucion_nodo_modelo_y_atributos_gen_ai(repo, exportador):
    e = _ejecucion(repo)
    with _span_de_ejecucion(e.id), medir(repo, e.id, "nodo", "evaluar_viabilidad"):
        with medir(repo, e.id, "modelo", "evaluar_viabilidad") as m:
            m.tokens_entrada, m.tokens_salida = 1200, 300
        with medir(repo, e.id, "herramienta", "search_docs") as h:
            h.detalle = "dominio=pypi.org"

    spans = {s.name: s for s in exportador.get_finished_spans()}
    assert set(spans) == {"ejecucion", "nodo:evaluar_viabilidad", "modelo:evaluar_viabilidad", "herramienta:search_docs"}
    raiz, nodo, modelo = spans["ejecucion"], spans["nodo:evaluar_viabilidad"], spans["modelo:evaluar_viabilidad"]
    assert nodo.parent.span_id == raiz.context.span_id
    assert modelo.parent.span_id == nodo.context.span_id
    assert spans["herramienta:search_docs"].parent.span_id == nodo.context.span_id
    assert modelo.attributes["gen_ai.usage.input_tokens"] == 1200
    assert modelo.attributes["gen_ai.usage.output_tokens"] == 300
    assert modelo.attributes["gen_ai.operation.name"] == "chat"
    assert raiz.attributes["session.id"] == f"ejecucion-{e.id}"
    assert raiz.attributes["emh.ejecucion_id"] == e.id


def test_un_error_marca_el_span_como_error_y_se_propaga(repo, exportador):
    e = _ejecucion(repo)
    with pytest.raises(RuntimeError), medir(repo, e.id, "herramienta", "run_tests"):
        raise RuntimeError("secreto-que-no-debe-salir")
    span = exportador.get_finished_spans()[0]
    assert span.status.status_code.name == "ERROR"
    assert span.attributes["emh.ok"] is False
    assert span.attributes["emh.detalle"] == "RuntimeError"  # solo el tipo, jamás el mensaje
    assert "secreto" not in str(span.attributes) + str(span.status.description)


def test_la_pausa_por_aprobacion_humana_no_es_un_error(repo, exportador):
    class GraphInterrupt(Exception):
        pass

    e = _ejecucion(repo)
    with pytest.raises(GraphInterrupt):
        with medir(repo, e.id, "nodo", "compuerta_aprobacion"):
            raise GraphInterrupt()
    span = exportador.get_finished_spans()[0]
    assert span.status.status_code.name != "ERROR"
    assert span.attributes["emh.ok"] is True


def test_sin_opentelemetry_medir_sigue_guardando_la_traza(repo, monkeypatch):
    monkeypatch.setattr(traza_mod, "_tracer", None)
    e = _ejecucion(repo)
    with medir(repo, e.id, "nodo", "descubrir_repo"):
        pass
    assert [t.nombre for t in repo.listar_trazas(e.id)] == ["descubrir_repo"]


def test_si_guardar_la_traza_falla_la_ejecucion_no_se_rompe(repo, monkeypatch):
    e = _ejecucion(repo)
    monkeypatch.setattr(repo, "guardar_traza", lambda t: (_ for _ in ()).throw(RuntimeError("bd caída")))
    with medir(repo, e.id, "nodo", "descubrir_repo"):
        resultado = 42
    assert resultado == 42
