"""`ScriptedModel` — SIMULATED. Adaptador de `ModelPort` para pruebas de
nivel A (DOCS/03-arquitectura.md §8): determinista, sin llamar a Bedrock.
Marcado explícitamente como simulación (RN-14): NUNCA se usa en la demo en
vivo, solo para probar que los controles frenan cualquier propuesta,
independientemente de qué proponga el modelo.
"""

from __future__ import annotations

from emh.core.ports import ModelPort, RespuestaModelo  # noqa: F401 -- documenta el contrato


class ScriptedModel:
    """SIMULATED. Devuelve, en orden, las respuestas con las que se
    construyó. Lanza `IndexError` si se le pide una llamada de más --
    señal de que el guion no cubre el flujo que se está probando."""

    def __init__(self, respuestas: list[RespuestaModelo]) -> None:
        self._respuestas = list(respuestas)
        self._indice = 0
        self.mensajes_recibidos: list[list[dict]] = []

    def completar(self, *, mensajes, sistema=None, herramientas=None, nivel_esfuerzo="low") -> RespuestaModelo:
        self.mensajes_recibidos.append(mensajes)
        if self._indice >= len(self._respuestas):
            raise IndexError(
                f"ScriptedModel (SIMULATED) agotó su guion en la llamada {self._indice + 1}: "
                "el flujo bajo prueba pidió más respuestas de las programadas"
            )
        respuesta = self._respuestas[self._indice]
        self._indice += 1
        return respuesta
