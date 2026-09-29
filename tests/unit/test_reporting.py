from __future__ import annotations

import pytest

from emh.core.models import (
    CitaFuente,
    DecisionTecnica,
    EstadoEjecucion,
    Fuente,
    MotivoBloqueo,
    ResultadoEjecucion,
    ResultadoVerificacion,
    TipoDecisionTecnica,
    TipoFuente,
    Verificacion,
)
from emh.core.ports import LlamadaHerramientaPropuesta, RespuestaModelo
from emh.core.state_machine import transicionar
from emh.models.scripted import ScriptedModel
from emh.persistence.sqlite_repo import SqliteRunRepository
from emh.reporting.renderer import ReportRenderer
from tests.factories import ejecucion, solicitud


@pytest.fixture()
def repo(tmp_path):
    r = SqliteRunRepository(tmp_path / "t.db")
    yield r
    r.close()


def _ejecucion_bloqueada(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    f = repo.guardar_fuente(Fuente(
        ejecucion_id=e.id, tipo=TipoFuente.REGISTRO_PAQUETES, url="https://pypi.org/project/PyYAML",
        hash_contenido="abc", resumen="x",
    ))
    dt = repo.guardar_decision_tecnica(DecisionTecnica(
        ejecucion_id=e.id, tipo=TipoDecisionTecnica.VIABILIDAD, descripcion="viable", sustentada=True,
    ))
    repo.guardar_cita_fuente(CitaFuente(decision_tecnica_id=dt.id, fuente_id=f.id))
    repo.guardar_verificacion(Verificacion(
        ejecucion_id=e.id, comando="pytest -q", codigo_salida=0, salida_capturada="7 passed",
        pruebas_totales=7, pruebas_exitosas=7, resultado=ResultadoVerificacion.EXITOSA,
    ))
    finalizada = transicionar(e, EstadoEjecucion.FINALIZADA, resultado=ResultadoEjecucion.LISTO_PARA_REVISION)
    repo.actualizar_ejecucion(finalizada)
    return e.id


def test_reporte_sin_modelo_usa_narrativa_deterministica(repo):
    eid = _ejecucion_bloqueada(repo)
    renderer = ReportRenderer(repo, modelo=None)
    reporte = renderer.render(eid)

    assert reporte["ejecucion"]["resultado"] == "LISTO_PARA_REVISION"
    assert reporte["narrativa_generada_por_ia"] is False
    assert len(reporte["verificaciones"]) == 1
    assert reporte["verificaciones"][0]["resultado"] == "EXITOSA"
    assert reporte["decisiones_tecnicas"][0]["sustentada"] is True
    assert reporte["decisiones_tecnicas"][0]["fuentes"] == ["https://pypi.org/project/PyYAML"]


def test_reporte_con_modelo_marca_narrativa_generada_por_ia(repo):
    eid = _ejecucion_bloqueada(repo)
    modelo = ScriptedModel([
        RespuestaModelo(
            texto=None,
            llamadas_herramienta=[LlamadaHerramientaPropuesta(id="t1", nombre="resumen_reporte", argumentos={"resumen": "Todo salió bien."})],
            tokens_entrada=50, tokens_salida=10,
        )
    ])
    renderer = ReportRenderer(repo, modelo=modelo)
    reporte = renderer.render(eid)
    assert reporte["narrativa"] == "Todo salió bien."
    assert reporte["narrativa_generada_por_ia"] is True


def test_decision_sin_cita_se_marca_sin_fuentes(repo):
    s = repo.guardar_solicitud(solicitud())
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))
    repo.guardar_decision_tecnica(DecisionTecnica(
        ejecucion_id=e.id, tipo=TipoDecisionTecnica.PLAN, descripcion="sin sustento", sustentada=False,
    ))
    finalizada = transicionar(e, EstadoEjecucion.FINALIZADA, resultado=ResultadoEjecucion.BLOQUEADO, motivo_bloqueo=MotivoBloqueo.INVIABLE)
    repo.actualizar_ejecucion(finalizada)

    reporte = ReportRenderer(repo).render(e.id)
    assert reporte["decisiones_tecnicas"][0]["sustentada"] is False
    assert reporte["decisiones_tecnicas"][0]["fuentes"] == []
    assert reporte["cambios"] == []  # BLOQUEADO: nunca se presenta un cambio como aplicado


def test_el_reporte_muestra_el_costo_con_cuatro_decimales(tmp_path):
    """NFR-010."""
    from emh.persistence.sqlite_repo import SqliteRunRepository
    from emh.reporting.renderer import ReportRenderer
    from tests.factories import ejecucion, solicitud

    repo = SqliteRunRepository(tmp_path / "t.db")
    try:
        s = repo.guardar_solicitud(solicitud())
        e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id, costo_estimado_usd=0.0190326))
        assert ReportRenderer(repo).render(e.id)["ejecucion"]["costo_estimado_usd"] == 0.019
    finally:
        repo.close()
