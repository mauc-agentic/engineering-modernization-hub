"""Pruebas de los invariantes de 02-modelo-entidades.md sobre EJECUCION."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from emh.core.models import (
    EstadoEjecucion,
    MotivoBloqueo,
    ResultadoEjecucion,
)
from tests.factories import ejecucion, solicitud


def test_solicitud_valida_se_construye():
    s = solicitud()
    assert s.limite_costo_usd == 1.0
    assert s.estrategia_id == "python_dependency_upgrade"


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("limite_tiempo_segundos", 0),
        ("limite_iteraciones", 0),
        ("limite_costo_usd", 0),
        ("limite_tiempo_segundos", -5),
    ],
)
def test_solicitud_rechaza_limites_no_positivos(campo, valor):
    with pytest.raises(ValidationError):
        solicitud(**{campo: valor})


def test_ejecucion_no_permite_resultado_si_no_esta_finalizada():
    with pytest.raises(ValidationError):
        ejecucion(estado=EstadoEjecucion.ANALISIS, resultado=ResultadoEjecucion.LISTO_PARA_REVISION)


def test_ejecucion_permite_resultado_cuando_finalizada():
    e = ejecucion(estado=EstadoEjecucion.FINALIZADA, resultado=ResultadoEjecucion.LISTO_PARA_REVISION)
    assert e.resultado is ResultadoEjecucion.LISTO_PARA_REVISION


def test_ejecucion_no_permite_motivo_bloqueo_sin_resultado_bloqueado():
    with pytest.raises(ValidationError):
        ejecucion(
            estado=EstadoEjecucion.FINALIZADA,
            resultado=ResultadoEjecucion.LISTO_PARA_REVISION,
            motivo_bloqueo=MotivoBloqueo.INVIABLE,
        )


def test_ejecucion_bloqueada_exige_motivo():
    e = ejecucion(
        estado=EstadoEjecucion.FINALIZADA,
        resultado=ResultadoEjecucion.BLOQUEADO,
        motivo_bloqueo=MotivoBloqueo.INVIABLE,
    )
    assert e.motivo_bloqueo is MotivoBloqueo.INVIABLE
