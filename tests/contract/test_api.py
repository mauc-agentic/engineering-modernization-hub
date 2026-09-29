"""Prueba de contrato de la API (NFR-021), con un `Aplicacion` armado a mano
(ScriptedModel + sandbox falso) para no depender de Docker/Bedrock reales
-- eso ya lo cubren los tests de contrato de cada adaptador."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from emh.agent.graph import Entorno
from emh.agent.runner import LangGraphAgentRunner
from emh.api.app import crear_app
from emh.bootstrap import Aplicacion
from emh.core.ports import (
    LlamadaHerramientaPropuesta,
    RespuestaModelo,
    ResultadoComando,
)
from emh.models.scripted import ScriptedModel
from emh.persistence.sqlite_repo import SqliteRunRepository
from emh.policy.gate import PolicyGate
from emh.reporting.renderer import ReportRenderer

EJECUTABLES = frozenset({"pip", "pytest", "python", "git"})


def _r(id_, nombre, argumentos):
    return RespuestaModelo(
        texto=None,
        llamadas_herramienta=[LlamadaHerramientaPropuesta(id=id_, nombre=nombre, argumentos=argumentos)],
        tokens_entrada=100, tokens_salida=20,
    )


def _construir_aplicacion_de_prueba(tmp_path, modelo, workspace):
    app_obj = Aplicacion.__new__(Aplicacion)  # evita __init__ (que crea Docker/Bedrock reales)
    app_obj.data_dir = tmp_path
    app_obj.repo = SqliteRunRepository(tmp_path / "t.db")
    app_obj.gate = PolicyGate(EJECUTABLES)
    app_obj.modelo = modelo
    app_obj.sandbox = None
    app_obj.entorno = Entorno(
        repo=app_obj.repo, modelo=modelo, gate=app_obj.gate, sandbox=app_obj.sandbox,
        workspace_root_para=lambda eid: workspace,
        ejecutor_host=lambda c, cwd: ResultadoComando(codigo_salida=0, salida="ok"),
        fetcher=lambda url: "(fuente falsa)",
    )
    app_obj.runner = LangGraphAgentRunner(app_obj.entorno, checkpointer=MemorySaver())
    app_obj.reporte = ReportRenderer(app_obj.repo, modelo=None)
    return app_obj


@pytest.fixture()
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("Flask==2.0.3\n")
    (ws / "runtime.txt").write_text("python-3.7.13\n")
    return ws


def test_flujo_completo_via_api_escenario_inviable(tmp_path, workspace):
    guion = [
        _r("t1", "objetivo_interpretado", {"objetivo_normalizado": "Actualizar Flask"}),
        _r("t2", "listo", {"resumen": "Flask==2.0.3, runtime 3.7.13"}),
        _r("t3", "listo", {"resumen": "Flask 3.0 exige Python >=3.8"}),
        _r("t4", "veredicto_viabilidad", {
            "veredicto": "INVIABLE", "impacto_detectado": "requiere Python 3.8+",
            "evidencia": "PyPI Requires-Python >=3.8 vs runtime.txt 3.7.13",
        }),
    ]
    modelo = ScriptedModel(guion)
    aplicacion = _construir_aplicacion_de_prueba(tmp_path, modelo, workspace)
    client = TestClient(crear_app(aplicacion))

    # UC-001: registrar solicitud
    r = client.post("/solicitudes", json={
        "repositorio_url": "https://github.com/example/orders-api", "commit_referencia": "9f0e1d2",
        "estrategia_id": "python_dependency_upgrade", "objetivo": "Actualizar Flask de 2.0.3 a 3.0.x",
        "version_esperada": "Flask>=3.0,<3.1", "restricciones": "Python 3.7 fijo",
        "limite_tiempo_segundos": 600, "limite_iteraciones": 3, "limite_costo_usd": 1.0,
        "solicitante": "dev:test@example.com",
    })
    assert r.status_code == 201
    ejecucion_id = r.json()["ejecucion_id"]

    # BackgroundTasks de TestClient corre sincrónicamente al salir del `with`
    # implícito de la respuesta; para FastAPI clásico, forzamos una consulta
    # que ya debería reflejar el resultado final (la tarea ya corrió).
    r2 = client.get(f"/ejecuciones/{ejecucion_id}")
    assert r2.status_code == 200
    assert r2.json()["resultado"] == "BLOQUEADO"
    assert r2.json()["motivo_bloqueo"] == "INVIABLE"

    # UC-002: consultar análisis de viabilidad
    r3 = client.get(f"/ejecuciones/{ejecucion_id}/analisis-viabilidad")
    assert r3.status_code == 200
    assert r3.json()["veredicto"] == "INVIABLE"

    # UC-005: reporte
    r4 = client.get(f"/ejecuciones/{ejecucion_id}/reporte")
    assert r4.status_code == 200
    assert r4.json()["ejecucion"]["resultado"] == "BLOQUEADO"


def test_solicitud_con_estrategia_no_soportada_rechazada(tmp_path, workspace):
    aplicacion = _construir_aplicacion_de_prueba(tmp_path, ScriptedModel([]), workspace)
    client = TestClient(crear_app(aplicacion))
    r = client.post("/solicitudes", json={
        "repositorio_url": "https://github.com/example/x", "commit_referencia": "abc",
        "estrategia_id": "no_existe", "objetivo": "x", "version_esperada": "1.0",
        "limite_tiempo_segundos": 60, "limite_iteraciones": 1, "limite_costo_usd": 1.0,
        "solicitante": "dev:test@example.com",
    })
    assert r.status_code == 422
    assert r.json()["detail"]["codigo"] == "ESTRATEGIA_NO_SOPORTADA"


def test_ejecucion_inexistente_da_404_con_formato_uniforme(tmp_path, workspace):
    aplicacion = _construir_aplicacion_de_prueba(tmp_path, ScriptedModel([]), workspace)
    client = TestClient(crear_app(aplicacion))
    r = client.get("/ejecuciones/9999")
    assert r.status_code == 404
    detalle = r.json()["detail"]
    assert detalle["codigo"] == "NO_ENCONTRADO"
    assert detalle["run_id"] == 9999


def test_endpoint_traza_devuelve_tramos_y_resumen_sin_contenido(tmp_path):
    from fastapi.testclient import TestClient

    from emh.api.app import crear_app
    from emh.bootstrap import Aplicacion
    from emh.core.models import Traza
    from tests.factories import ejecucion, solicitud

    app_ = Aplicacion(data_dir=tmp_path, modo_simulado=True)
    try:
        s = app_.repo.guardar_solicitud(solicitud())
        e = app_.repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
        app_.repo.guardar_traza(Traza(ejecucion_id=e.id, tipo="nodo", nombre="descubrir_repo", duracion_ms=1200))
        app_.repo.guardar_traza(Traza(ejecucion_id=e.id, tipo="modelo", nombre="evaluar_viabilidad", duracion_ms=900,
                                      tokens_entrada=1000, tokens_salida=200))
        app_.repo.guardar_traza(Traza(ejecucion_id=e.id, tipo="herramienta", nombre="run_tests", duracion_ms=5000, ok=False,
                                      detalle="TimeoutError"))
        cliente = TestClient(crear_app(app_))
        r = cliente.get(f"/ejecuciones/{e.id}/traza")
        assert r.status_code == 200
        cuerpo = r.json()
        assert [t["tipo"] for t in cuerpo["tramos"]] == ["nodo", "modelo", "herramienta"]
        assert cuerpo["resumen"]["llamadas_modelo"] == 1
        assert cuerpo["resumen"]["tokens_entrada"] == 1000
        assert cuerpo["resumen"]["errores"] == 1
        assert cliente.get("/ejecuciones/99999/traza").status_code == 404
    finally:
        app_.cerrar()
