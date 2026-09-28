"""Nivel A (SIMULATED): escenario 2 del caso -- modernización inviable
(DOCS/09-escenarios.md §3, Ejemplo B `orders-api`). La plataforma notifica
la inviabilidad con evidencia y NO toca el repositorio ni pide aprobación."""

from __future__ import annotations

import pytest

from emh.agent.graph import Entorno
from emh.agent.runner import LangGraphAgentRunner
from emh.core.models import EstadoEjecucion, MotivoBloqueo, ResultadoEjecucion
from emh.core.ports import LlamadaHerramientaPropuesta, RespuestaModelo, ResultadoComando
from emh.models.scripted import ScriptedModel
from emh.persistence.sqlite_repo import SqliteRunRepository
from emh.policy.gate import PolicyGate
from tests.factories import ejecucion, solicitud

pytestmark = pytest.mark.simulated

EJECUTABLES = frozenset({"pip", "pytest", "python", "git"})


def _r(id_, nombre, argumentos):
    return RespuestaModelo(
        texto=None,
        llamadas_herramienta=[LlamadaHerramientaPropuesta(id=id_, nombre=nombre, argumentos=argumentos)],
        tokens_entrada=150, tokens_salida=40,
    )


@pytest.fixture()
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("Flask==2.0.3\n")
    (ws / "runtime.txt").write_text("python-3.7.13\n")
    return ws


@pytest.fixture()
def repo(tmp_path):
    r = SqliteRunRepository(tmp_path / "test.db")
    yield r
    r.close()


def test_modernizacion_inviable_no_toca_el_repositorio(repo, workspace):
    s = repo.guardar_solicitud(solicitud(
        objetivo="Actualizar Flask de 2.0.3 a 3.0.x", version_esperada="Flask>=3.0,<3.1",
        restricciones="El runtime de despliegue está fijado a Python 3.7",
    ))
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))

    guion = [
        _r("t1", "objetivo_interpretado", {"objetivo_normalizado": "Actualizar Flask a 3.0.x"}),
        _r("t2", "listo", {"resumen": "requirements.txt tiene Flask==2.0.3; runtime.txt fija python-3.7.13"}),
        _r("t3", "listo", {"resumen": "Flask 3.0.0 en PyPI declara Requires-Python >=3.8"}),
        _r("t4", "veredicto_viabilidad", {
            "veredicto": "INVIABLE",
            "impacto_detectado": "Flask 3.0.0 requiere Python >=3.8; el runtime declarado es 3.7.13",
            "evidencia": "PyPI metadatos de Flask 3.0.0 (Requires-Python >=3.8) vs. runtime.txt (python-3.7.13)",
        }),
    ]
    modelo = ScriptedModel(guion)

    entorno = Entorno(
        repo=repo, modelo=modelo, gate=PolicyGate(EJECUTABLES), sandbox=None,
        workspace_root_para=lambda eid: workspace,
        ejecutor_host=lambda c, cwd: ResultadoComando(codigo_salida=0, salida="ok"),
        fetcher=lambda url: "(fuente falsa)",
    )
    runner = LangGraphAgentRunner(entorno)
    runner.run(e.id)

    final = repo.obtener_ejecucion(e.id)
    assert final.estado is EstadoEjecucion.FINALIZADA
    assert final.resultado is ResultadoEjecucion.BLOQUEADO
    assert final.motivo_bloqueo is MotivoBloqueo.INVIABLE

    # Nunca se propuso ni se aprobó ningún plan; el repositorio no cambió.
    assert repo.obtener_plan_vigente(e.id) is None
    assert (workspace / "requirements.txt").read_text() == "Flask==2.0.3\n"

    analisis = repo.obtener_analisis_viabilidad(e.id)
    assert analisis.veredicto.value == "INVIABLE"
    assert "Requires-Python" in analisis.evidencia

    # Trazabilidad: 4 llamadas (interpretar, descubrir, consultar, viabilidad)
    assert len(repo.listar_llamadas_modelo(e.id)) == 4
