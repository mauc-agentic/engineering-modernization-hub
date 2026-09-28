"""Fábricas mínimas de entidades para pruebas, evitando repetir boilerplate
en cada test. No es un fixture de fixtures: cada función acepta overrides."""

from __future__ import annotations

from emh.core.models import Ejecucion, Solicitud


def solicitud(**overrides) -> Solicitud:
    datos = dict(
        repositorio_url="https://github.com/example/ledger-service",
        commit_referencia="a1b2c3d",
        estrategia_id="python_dependency_upgrade",
        objetivo="Actualizar PyYAML de 5.3.1 a 6.0.2",
        version_esperada="PyYAML==6.0.2",
        limite_tiempo_segundos=720,
        limite_iteraciones=3,
        limite_costo_usd=1.0,
        solicitante="dev:test@example.com",
    )
    datos.update(overrides)
    return Solicitud(**datos)


def ejecucion(**overrides) -> Ejecucion:
    datos = dict(solicitud_id=1)
    datos.update(overrides)
    return Ejecucion(**datos)
