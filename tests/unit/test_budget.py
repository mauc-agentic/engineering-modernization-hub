"""Control 4 — Presupuestos: corte duro de tiempo, iteraciones y costo
(NFR-009). El reloj se inyecta para no depender de tiempo real (03-arquitectura
§3.1: "con un reloj y un contador de tokens inyectados")."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from emh.core.budget import PresupuestoMeter
from emh.core.errors import PresupuestoAgotado
from tests.factories import solicitud


class RelojFalso:
    def __init__(self, inicio: datetime) -> None:
        self._ahora = inicio

    def avanzar(self, segundos: float) -> None:
        self._ahora += timedelta(seconds=segundos)

    def __call__(self) -> datetime:
        return self._ahora


def test_no_lanza_dentro_del_limite():
    reloj = RelojFalso(datetime(2026, 1, 1, tzinfo=UTC))
    meter = PresupuestoMeter(solicitud(limite_tiempo_segundos=60), ahora=reloj)
    reloj.avanzar(30)
    meter.verificar()  # no debe lanzar


def test_corta_exactamente_al_superar_el_tiempo():
    reloj = RelojFalso(datetime(2026, 1, 1, tzinfo=UTC))
    meter = PresupuestoMeter(solicitud(limite_tiempo_segundos=60), ahora=reloj)
    reloj.avanzar(61)
    with pytest.raises(PresupuestoAgotado) as exc:
        meter.verificar()
    assert exc.value.recurso == "tiempo_segundos"


def test_corta_al_superar_iteraciones():
    meter = PresupuestoMeter(solicitud(limite_iteraciones=2))
    meter.registrar_iteracion()
    meter.registrar_iteracion()
    meter.verificar()  # 2 usadas, límite 2: aún no se supera
    meter.registrar_iteracion()
    with pytest.raises(PresupuestoAgotado) as exc:
        meter.verificar()
    assert exc.value.recurso == "iteraciones"


def test_costo_se_deriva_de_tokens_con_precios_de_nova_2_lite():
    meter = PresupuestoMeter(solicitud(limite_costo_usd=1.0))
    # 1_000_000 tokens de entrada a 0.30 USD/1M = 0.30 USD
    meter.registrar_llamada_modelo(tokens_entrada=1_000_000, tokens_salida=0)
    assert meter.estado.costo_estimado_usd == pytest.approx(0.30)
    # + 200_000 tokens de salida a 2.50 USD/1M = 0.50 USD -> total 0.80 USD
    meter.registrar_llamada_modelo(tokens_entrada=0, tokens_salida=200_000)
    assert meter.estado.costo_estimado_usd == pytest.approx(0.80)
    meter.verificar()  # 0.80 < 1.0, aún no se agota


def test_corta_al_superar_costo():
    meter = PresupuestoMeter(solicitud(limite_costo_usd=0.10))
    meter.registrar_llamada_modelo(tokens_entrada=1_000_000, tokens_salida=0)  # USD 0.30
    with pytest.raises(PresupuestoAgotado) as exc:
        meter.verificar()
    assert exc.value.recurso == "costo_usd"


def test_llamada_en_vuelo_se_deja_terminar():
    """El control 4 dice: la llamada en curso se deja terminar; solo la
    SIGUIENTE se bloquea. Verificamos que registrar tras superar el límite
    no lanza por sí solo -- quien orquesta debe llamar verificar() antes."""
    meter = PresupuestoMeter(solicitud(limite_costo_usd=0.10))
    meter.registrar_llamada_modelo(tokens_entrada=1_000_000, tokens_salida=0)
    # registrar_llamada_modelo no lanza; el corte lo decide verificar()
    with pytest.raises(PresupuestoAgotado):
        meter.verificar()
