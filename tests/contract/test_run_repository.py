"""Prueba de contrato: SqliteRunRepository y PostgresRunRepository contra el
puerto RunRepository (NFR-016 — cambiar de adaptador no debe exigir cambiar
el dominio). Postgres corre en un contenedor Docker real; sin Docker se omite."""

from __future__ import annotations

import pytest

from emh.core.models import (
    CitaFuente,
    DecisionAprobacion,
    DecisionAprobacionValor,
    DecisionTecnica,
    EstadoEjecucion,
    EstadoPlan,
    EventoSeguridad,
    Fuente,
    LlamadaModelo,
    OrigenEvento,
    Plan,
    ResultadoVerificacion,
    SeveridadEvento,
    TipoDecisionTecnica,
    TipoFuente,
    Verificacion,
)
from emh.persistence.sqlite_repo import SqliteRunRepository
from tests.factories import ejecucion, solicitud


@pytest.fixture(params=["sqlite", "postgres"])
def repo(request, tmp_path):
    if request.param == "sqlite":
        r = SqliteRunRepository(tmp_path / "test.db")
    else:
        import uuid

        import psycopg

        from emh.persistence.postgres_repo import PostgresRunRepository

        admin_dsn = request.getfixturevalue("postgres_admin_dsn")
        nombre = f"t_{uuid.uuid4().hex[:12]}"  # base fresca por prueba: sin hashes UNIQUE cruzados
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(f"CREATE DATABASE {nombre}")
        r = PostgresRunRepository(admin_dsn.rsplit("/", 1)[0] + "/" + nombre)
    yield r
    r.close()


def test_solicitud_guarda_y_recupera(repo):
    s = repo.guardar_solicitud(solicitud())
    assert s.id is not None
    recuperada = repo.obtener_solicitud(s.id)
    assert recuperada.repositorio_url == s.repositorio_url
    assert recuperada.limite_costo_usd == s.limite_costo_usd


def test_ejecucion_guarda_actualiza_y_recupera(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    assert e.id is not None

    e2 = e.model_copy(update={"estado": EstadoEjecucion.ANALISIS})
    repo.actualizar_ejecucion(e2)

    recuperada = repo.obtener_ejecucion(e.id)
    assert recuperada.estado is EstadoEjecucion.ANALISIS


def test_plan_versiones_y_vigente(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))

    p1 = repo.guardar_plan(Plan(
        ejecucion_id=e.id, version=1, hash="h1", pasos=["paso 1"],
        rutas_declaradas=["requirements.txt"], comandos_verificacion=[["pytest", "-q"]],
        estado=EstadoPlan.SUPERSEDIDO,
    ))
    p2 = repo.guardar_plan(Plan(
        ejecucion_id=e.id, version=2, hash="h2", pasos=["paso 1", "paso 2"],
        rutas_declaradas=["requirements.txt", "ledger/config.py"],
        comandos_verificacion=[["pytest", "-q"]], estado=EstadoPlan.PROPUESTO,
    ))

    vigente = repo.obtener_plan_vigente(e.id)
    assert vigente.id == p2.id
    assert vigente.rutas_declaradas == ["requirements.txt", "ledger/config.py"]
    assert len(repo.listar_planes(e.id)) == 2
    assert p1.id != p2.id


def test_decision_aprobacion(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    p = repo.guardar_plan(Plan(
        ejecucion_id=e.id, version=1, hash="h1", pasos=["x"],
        rutas_declaradas=["requirements.txt"], comandos_verificacion=[["pytest"]],
    ))
    d = repo.guardar_decision_aprobacion(DecisionAprobacion(
        plan_id=p.id, plan_hash=p.hash, decision=DecisionAprobacionValor.APROBADO,
        aprobador="dev:test@example.com",
    ))
    assert d.id is not None
    vigente = repo.obtener_decision_aprobacion_vigente(p.id)
    assert vigente.decision is DecisionAprobacionValor.APROBADO


def test_fuente_decision_tecnica_y_cita(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))

    f = repo.guardar_fuente(Fuente(
        ejecucion_id=e.id, tipo=TipoFuente.REGISTRO_PAQUETES,
        url="https://pypi.org/project/PyYAML", hash_contenido="abc123",
        resumen="PyYAML 6.0 requiere Loader= explícito",
    ))
    dt = repo.guardar_decision_tecnica(DecisionTecnica(
        ejecucion_id=e.id, tipo=TipoDecisionTecnica.VIABILIDAD,
        descripcion="Viable: breaking change acotado a dos llamadas", sustentada=True,
    ))
    cita = repo.guardar_cita_fuente(CitaFuente(decision_tecnica_id=dt.id, fuente_id=f.id))

    assert cita.id is not None
    assert len(repo.listar_fuentes(e.id)) == 1
    assert len(repo.listar_decisiones_tecnicas(e.id)) == 1
    assert len(repo.listar_citas(dt.id)) == 1


def test_verificacion_captura_salida_real(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    v = repo.guardar_verificacion(Verificacion(
        ejecucion_id=e.id, comando="pytest -q --tb=short", codigo_salida=1,
        salida_capturada="1 failed, 6 passed", pruebas_totales=7, pruebas_exitosas=6,
        resultado=ResultadoVerificacion.FALLIDA,
    ))
    assert v.id is not None
    listadas = repo.listar_verificaciones(e.id)
    assert listadas[0].resultado is ResultadoVerificacion.FALLIDA
    assert listadas[0].codigo_salida == 1


def test_evento_seguridad(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    ev = repo.guardar_evento_seguridad(EventoSeguridad(
        ejecucion_id=e.id, regla="control_02_comandos_permitidos",
        accion_intentada="bash -c 'rm -rf /'", origen=OrigenEvento.MODELO,
        severidad=SeveridadEvento.CRITICA,
    ))
    assert ev.id is not None
    assert len(repo.listar_eventos_seguridad(e.id)) == 1


def test_llamada_modelo_trazabilidad(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    repo.guardar_llamada_modelo(LlamadaModelo(
        ejecucion_id=e.id, nodo="analizar_impacto", tokens_entrada=3000,
        tokens_salida=400, duracion_ms=1200,
    ))
    llamadas = repo.listar_llamadas_modelo(e.id)
    assert len(llamadas) == 1
    assert llamadas[0].nodo == "analizar_impacto"


def test_claves_foraneas_activas(repo):
    """Una ejecución que referencia una solicitud inexistente debe fallar
    (PRAGMA foreign_keys=ON en SQLite, ADR-004; restricción nativa en Postgres)."""
    import sqlite3

    import psycopg

    with pytest.raises((sqlite3.IntegrityError, psycopg.IntegrityError)):
        repo.guardar_ejecucion(ejecucion(solicitud_id=999999))


def test_traza_guarda_y_lista_en_orden_de_inicio(repo):
    from datetime import UTC, datetime, timedelta

    from emh.core.models import Traza

    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    base = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    repo.guardar_traza(Traza(ejecucion_id=e.id, tipo="modelo", nombre="b", inicio=base + timedelta(seconds=2),
                             duracion_ms=300, tokens_entrada=10, tokens_salida=5))
    repo.guardar_traza(Traza(ejecucion_id=e.id, tipo="nodo", nombre="a", inicio=base, duracion_ms=5000,
                             ok=False, detalle="TimeoutError"))
    lista = repo.listar_trazas(e.id)
    assert [t.nombre for t in lista] == ["a", "b"]
    assert lista[0].ok is False and lista[0].detalle == "TimeoutError"
    assert lista[1].tokens_entrada == 10
    assert repo.listar_trazas(999999) == []
