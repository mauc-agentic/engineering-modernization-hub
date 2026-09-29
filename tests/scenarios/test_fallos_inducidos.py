"""Nivel A (SIMULATED): fallos inducidos del modelo, de las herramientas y del entorno (NFR-007, AC-14, RN-11).
En TODOS los casos la ejecución termina en uno de los cinco resultados y `run()`/`resume()` no propagan
excepciones: nada queda colgado en un estado intermedio."""

from __future__ import annotations

import pytest

from emh.agent.graph import Entorno
from emh.agent.runner import LangGraphAgentRunner
from emh.core.models import (
    DecisionAprobacion,
    DecisionAprobacionValor,
    EstadoEjecucion,
    ResultadoEjecucion,
)
from emh.core.ports import LlamadaHerramientaPropuesta, RespuestaModelo, ResultadoComando
from emh.models.scripted import ScriptedModel
from emh.persistence.sqlite_repo import SqliteRunRepository
from emh.policy.gate import PolicyGate
from tests.factories import ejecucion, solicitud

pytestmark = pytest.mark.simulated

CINCO_RESULTADOS = set(ResultadoEjecucion)


def _r(id_, nombre, argumentos):
    return RespuestaModelo(
        texto=None, llamadas_herramienta=[LlamadaHerramientaPropuesta(id=id_, nombre=nombre, argumentos=argumentos)],
        tokens_entrada=100, tokens_salida=20,
    )


class ModeloQueFalla:
    """Un proveedor caído: la primera llamada lanza la excepción indicada."""

    def __init__(self, excepcion: Exception) -> None:
        self._excepcion = excepcion

    def completar(self, **_kw):
        raise self._excepcion


class SandboxNoDisponible:
    """Docker/Fargate no disponible: no se puede ni crear el contenedor."""

    def crear(self, workspace, **_kw):
        raise RuntimeError("Cannot connect to the Docker daemon")

    def ejecutar(self, *_a, **_kw):
        raise AssertionError("no debería llegar aquí")

    def destruir(self, *_a, **_kw):
        return None


@pytest.fixture()
def repo(tmp_path):
    r = SqliteRunRepository(tmp_path / "t.db")
    yield r
    r.close()


@pytest.fixture()
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("PyYAML==5.3.1\n")
    return ws


def _entorno(repo, workspace, modelo, sandbox=None):
    return Entorno(
        repo=repo, modelo=modelo, gate=PolicyGate(frozenset({"pip", "pytest", "python", "git"})), sandbox=sandbox,
        workspace_root_para=lambda _id: workspace,
        ejecutor_host=lambda c, cwd: ResultadoComando(codigo_salida=0, salida="ok"),
        fetcher=lambda url: "(fuente falsa)",
    )


@pytest.mark.parametrize("excepcion", [
    RuntimeError("ThrottlingException: Rate exceeded (agotados los reintentos)"),
    TimeoutError("el modelo no respondió a tiempo"),
    ValueError("respuesta del proveedor con formato inesperado"),
])
def test_un_modelo_caido_termina_de_forma_controlada(repo, workspace, excepcion):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    LangGraphAgentRunner(_entorno(repo, workspace, ModeloQueFalla(excepcion))).run(e.id)  # no propaga
    final = repo.obtener_ejecucion(e.id)
    assert final.estado is EstadoEjecucion.FINALIZADA
    assert final.resultado in CINCO_RESULTADOS
    assert final.resultado is ResultadoEjecucion.FALLIDO_CONTROLADO


def test_docker_no_disponible_tras_la_aprobacion_termina_de_forma_controlada(repo, workspace):
    s = repo.guardar_solicitud(solicitud(objetivo="Actualizar PyYAML", version_esperada="PyYAML==6.0.2"))
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    guion = [
        _r("t1", "objetivo_interpretado", {"objetivo_normalizado": "x"}),
        _r("t2", "listo", {"resumen": "a"}), _r("t3", "listo", {"resumen": "b"}),
        _r("t4", "veredicto_viabilidad", {"veredicto": "VIABLE", "impacto_detectado": "x", "evidencia": "y"}),
        _r("t5", "plan_propuesto", {"pasos": ["subir versión"], "rutas_declaradas": ["requirements.txt"], "riesgos": "ninguno"}),
        _r("t6", "parche_propuesto", {"cambios": [{"ruta": "requirements.txt", "operacion": "modificar", "contenido_nuevo": "PyYAML==6.0.2\n"}]}),
    ]
    runner = LangGraphAgentRunner(_entorno(repo, workspace, ScriptedModel(guion), sandbox=SandboxNoDisponible()))
    runner.run(e.id)
    plan = repo.obtener_plan_vigente(e.id)
    repo.guardar_decision_aprobacion(DecisionAprobacion(
        plan_id=plan.id, plan_hash=plan.hash, decision=DecisionAprobacionValor.APROBADO, aprobador="dev:test",
    ))
    runner.resume(e.id)  # no propaga la excepción del sandbox
    final = repo.obtener_ejecucion(e.id)
    assert final.estado is EstadoEjecucion.FINALIZADA
    assert final.resultado is ResultadoEjecucion.FALLIDO_CONTROLADO
    assert not repo.listar_verificaciones(e.id)  # ninguna verificación fingida como exitosa (AC-08)
