"""FR-020: la memoria de trabajo del agente sobrevive a un reinicio. Se simula el reinicio construyendo un runner NUEVO
(con entorno y checkpointer nuevos) sobre el mismo almacenamiento, y se reanuda una ejecución que esperaba aprobación."""

from __future__ import annotations

import sqlite3

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


def _r(id_, nombre, argumentos):
    return RespuestaModelo(
        texto=None, llamadas_herramienta=[LlamadaHerramientaPropuesta(id=id_, nombre=nombre, argumentos=argumentos)],
        tokens_entrada=100, tokens_salida=20,
    )


class SandboxVerde:
    def crear(self, workspace, **_kw):
        return "c1"

    def ejecutar(self, _id, comando, **_kw):
        return ResultadoComando(codigo_salida=0, salida="7 passed in 0.1s")

    def destruir(self, _id):
        return None


ANTES_DE_LA_APROBACION = [
    _r("t1", "objetivo_interpretado", {"objetivo_normalizado": "x"}),
    _r("t2", "listo", {"resumen": "a"}), _r("t3", "listo", {"resumen": "b"}),
    _r("t4", "veredicto_viabilidad", {"veredicto": "VIABLE", "impacto_detectado": "x", "evidencia": "y"}),
    _r("t5", "plan_propuesto", {"pasos": ["subir versión"], "rutas_declaradas": ["requirements.txt"], "riesgos": "ninguno"}),
]
DESPUES_DE_LA_APROBACION = [
    _r("t6", "parche_propuesto", {"cambios": [{"ruta": "requirements.txt", "operacion": "modificar", "contenido_nuevo": "PyYAML==6.0.2\n"}]}),
]


def _entorno(repo, workspace, guion):
    return Entorno(
        repo=repo, modelo=ScriptedModel(guion), gate=PolicyGate(frozenset({"pip", "pytest", "python", "git"})),
        sandbox=SandboxVerde(), workspace_root_para=lambda _id: workspace,
        ejecutor_host=lambda c, cwd: ResultadoComando(codigo_salida=0, salida="ok"),
        fetcher=lambda url: "(fuente falsa)",
    )


def _reanudar_tras_reinicio(repo, workspace, nuevo_checkpointer):
    """Ejecuta hasta la compuerta de aprobación, 'reinicia' y reanuda con un runner y un modelo nuevos."""
    s = repo.guardar_solicitud(solicitud(objetivo="Actualizar PyYAML", version_esperada="PyYAML==6.0.2"))
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))

    LangGraphAgentRunner(_entorno(repo, workspace, ANTES_DE_LA_APROBACION), checkpointer=nuevo_checkpointer()).run(e.id)
    assert repo.obtener_ejecucion(e.id).estado is EstadoEjecucion.ESPERANDO_APROBACION

    plan = repo.obtener_plan_vigente(e.id)
    repo.guardar_decision_aprobacion(DecisionAprobacion(
        plan_id=plan.id, plan_hash=plan.hash, decision=DecisionAprobacionValor.APROBADO, aprobador="dev:test",
    ))

    # ---- "reinicio": proceso nuevo = runner, entorno, modelo y checkpointer nuevos, mismo almacenamiento ----
    LangGraphAgentRunner(_entorno(repo, workspace, DESPUES_DE_LA_APROBACION), checkpointer=nuevo_checkpointer()).resume(e.id)
    return repo.obtener_ejecucion(e.id)


def test_reanuda_tras_reinicio_con_checkpointer_sqlite(tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("PyYAML==5.3.1\n")
    repo = SqliteRunRepository(tmp_path / "emh.db")

    def nuevo():
        saver = SqliteSaver(sqlite3.connect(tmp_path / "checkpoints.db", check_same_thread=False))
        saver.setup()
        return saver

    try:
        final = _reanudar_tras_reinicio(repo, ws, nuevo)
        assert final.estado is EstadoEjecucion.FINALIZADA
        assert final.resultado is ResultadoEjecucion.LISTO_PARA_REVISION
        assert (ws / "requirements.txt").read_text() == "PyYAML==6.0.2\n"
    finally:
        repo.close()


def test_reanuda_tras_reinicio_con_checkpointer_postgres(tmp_path, postgres_admin_dsn):
    import uuid

    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    from emh.persistence.postgres_repo import PostgresRunRepository

    nombre = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(postgres_admin_dsn, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {nombre}")
    dsn = postgres_admin_dsn.rsplit("/", 1)[0] + "/" + nombre
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("PyYAML==5.3.1\n")
    repo = PostgresRunRepository(dsn)
    pools: list[ConnectionPool] = []

    def nuevo():
        pool = ConnectionPool(dsn, min_size=1, max_size=3, open=True,
                              kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        pools.append(pool)
        saver = PostgresSaver(pool)
        saver.setup()
        return saver

    try:
        final = _reanudar_tras_reinicio(repo, ws, nuevo)
        assert final.resultado is ResultadoEjecucion.LISTO_PARA_REVISION
    finally:
        for p in pools:
            p.close()
        repo.close()


@pytest.mark.parametrize("motor", ["memoria"])
def test_sin_checkpointer_persistente_el_reinicio_pierde_la_memoria_de_trabajo(tmp_path, motor):
    """Contraste que documenta POR QUÉ importa: con `MemorySaver` un runner nuevo no puede reanudar."""
    from langgraph.checkpoint.memory import MemorySaver

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("PyYAML==5.3.1\n")
    repo = SqliteRunRepository(tmp_path / "emh.db")
    try:
        final = _reanudar_tras_reinicio(repo, ws, MemorySaver)  # cada runner recibe una memoria NUEVA y vacía
        assert final.resultado is not ResultadoEjecucion.LISTO_PARA_REVISION
    finally:
        repo.close()
