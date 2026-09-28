"""Máquina de estados de la ejecución — fuente de verdad del estado de
negocio (DOCS/03-arquitectura.md §3.1). LangGraph lleva la memoria de
trabajo; esta máquina decide si una transición es legal. Un nodo del grafo
que pide una transición ilegal termina la ejecución en FALLIDO_CONTROLADO
(RN-11), nunca con una excepción sin manejar.
"""

from __future__ import annotations

from typing import Callable

from emh.core.errors import TransicionIlegal
from emh.core.models import (
    Ejecucion,
    EstadoEjecucion as E,
    MotivoBloqueo,
    ResultadoEjecucion,
    utcnow,
)

# Aristas legales del grafo de negocio (03-arquitectura.md §4), colapsadas a
# nivel de EstadoEjecucion. Cada estado permite quedarse en sí mismo (pasos
# internos del mismo macro-estado, p. ej. varios nodos de ANALISIS).
ALLOWED_TRANSITIONS: dict[E, frozenset[E]] = {
    E.DESCUBRIMIENTO: frozenset({E.DESCUBRIMIENTO, E.ANALISIS, E.FINALIZADA}),
    E.ANALISIS: frozenset({E.ANALISIS, E.PLANEACION, E.FINALIZADA}),
    E.PLANEACION: frozenset({E.PLANEACION, E.ESPERANDO_APROBACION, E.FINALIZADA}),
    E.ESPERANDO_APROBACION: frozenset(
        {E.ESPERANDO_APROBACION, E.APLICANDO_CAMBIOS, E.FINALIZADA}
    ),
    E.APLICANDO_CAMBIOS: frozenset({E.APLICANDO_CAMBIOS, E.VERIFICANDO, E.FINALIZADA}),
    E.VERIFICANDO: frozenset({E.VERIFICANDO, E.CORRIGIENDO, E.FINALIZADA}),
    E.CORRIGIENDO: frozenset({E.CORRIGIENDO, E.APLICANDO_CAMBIOS, E.FINALIZADA}),
    E.FINALIZADA: frozenset(),  # estado terminal: ninguna transición sale de aquí
}


def transicionar(
    ejecucion: Ejecucion,
    nuevo_estado: E,
    *,
    resultado: ResultadoEjecucion | None = None,
    motivo_bloqueo: MotivoBloqueo | None = None,
    ahora: Callable[[], "object"] = utcnow,
) -> Ejecucion:
    """Devuelve una nueva `Ejecucion` con la transición aplicada.

    Lanza `TransicionIlegal` si la transición no está en `ALLOWED_TRANSITIONS`.
    Exige `resultado` exactamente cuando `nuevo_estado == FINALIZADA` (RN-11):
    ninguna ejecución llega a FINALIZADA sin uno de los cinco resultados.
    """
    permitidos = ALLOWED_TRANSITIONS.get(ejecucion.estado, frozenset())
    if nuevo_estado not in permitidos:
        raise TransicionIlegal(ejecucion.estado.value, nuevo_estado.value)

    if nuevo_estado is E.FINALIZADA:
        if resultado is None:
            raise ValueError(
                "toda transición a FINALIZADA requiere un resultado (RN-11)"
            )
        if resultado is ResultadoEjecucion.BLOQUEADO and motivo_bloqueo is None:
            raise ValueError("resultado=BLOQUEADO requiere motivo_bloqueo")
        if resultado is not ResultadoEjecucion.BLOQUEADO and motivo_bloqueo is not None:
            raise ValueError("motivo_bloqueo solo aplica cuando resultado=BLOQUEADO")
        return ejecucion.model_copy(
            update={
                "estado": nuevo_estado,
                "resultado": resultado,
                "motivo_bloqueo": motivo_bloqueo,
                "finalizado_en": ahora(),
            }
        )

    return ejecucion.model_copy(update={"estado": nuevo_estado})
