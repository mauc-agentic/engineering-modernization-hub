"""Pruebas de la máquina de estados (RN-11): transiciones legales/ilegales,
y que FINALIZADA siempre exige un resultado de los cinco posibles."""

from __future__ import annotations

import pytest

from emh.core.errors import TransicionIlegal
from emh.core.models import EstadoEjecucion as E
from emh.core.models import MotivoBloqueo
from emh.core.models import ResultadoEjecucion as R
from emh.core.state_machine import transicionar
from tests.factories import ejecucion


def test_transicion_legal_avanza_el_estado():
    e = ejecucion(estado=E.DESCUBRIMIENTO)
    e2 = transicionar(e, E.ANALISIS)
    assert e2.estado is E.ANALISIS
    assert e.estado is E.DESCUBRIMIENTO  # inmutable: el original no cambia


def test_transicion_ilegal_lanza_error():
    e = ejecucion(estado=E.DESCUBRIMIENTO)
    with pytest.raises(TransicionIlegal):
        transicionar(e, E.VERIFICANDO)


def test_finalizada_exige_resultado():
    e = ejecucion(estado=E.VERIFICANDO)
    with pytest.raises(ValueError):
        transicionar(e, E.FINALIZADA)


def test_finalizada_exitosa_registra_finalizado_en():
    e = ejecucion(estado=E.VERIFICANDO)
    e2 = transicionar(e, E.FINALIZADA, resultado=R.LISTO_PARA_REVISION)
    assert e2.resultado is R.LISTO_PARA_REVISION
    assert e2.finalizado_en is not None


def test_bloqueado_exige_motivo():
    e = ejecucion(estado=E.ANALISIS)
    with pytest.raises(ValueError):
        transicionar(e, E.FINALIZADA, resultado=R.BLOQUEADO)


def test_bloqueado_con_motivo_ok():
    e = ejecucion(estado=E.ANALISIS)
    e2 = transicionar(e, E.FINALIZADA, resultado=R.BLOQUEADO, motivo_bloqueo=MotivoBloqueo.INVIABLE)
    assert e2.motivo_bloqueo is MotivoBloqueo.INVIABLE


def test_finalizada_es_terminal():
    e = ejecucion(estado=E.FINALIZADA, resultado=R.LISTO_PARA_REVISION)
    with pytest.raises(TransicionIlegal):
        transicionar(e, E.ANALISIS)


def test_correccion_vuelve_a_aplicando_cambios():
    e = ejecucion(estado=E.CORRIGIENDO)
    e2 = transicionar(e, E.APLICANDO_CAMBIOS)
    assert e2.estado is E.APLICANDO_CAMBIOS


@pytest.mark.parametrize("estado", list(E))
def test_todo_estado_tiene_camino_a_finalizada(estado):
    """RN-11: ninguna ejecución puede quedar sin forma de terminar."""
    from emh.core.state_machine import ALLOWED_TRANSITIONS

    if estado is E.FINALIZADA:
        pytest.skip("ya es terminal")
    assert E.FINALIZADA in ALLOWED_TRANSITIONS[estado]
