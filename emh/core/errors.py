"""Errores del dominio. Ninguno de estos escapa como excepción no manejada
hasta el usuario final (RN-11): quien los captura los traduce a un
ResultadoEjecucion. Ver DOCS/00-vision.md RN-11 y DOCS/07-seguridad.md."""

from __future__ import annotations


class ErrorDominio(Exception):
    """Base de todos los errores que el dominio conoce y sabe traducir a un
    resultado final, en vez de dejar propagar una excepción cruda."""


class TransicionIlegal(ErrorDominio):
    """Un nodo pidió una transición que la máquina de estados no permite."""

    def __init__(self, origen: str, destino: str) -> None:
        self.origen = origen
        self.destino = destino
        super().__init__(f"Transición ilegal: {origen} -> {destino}")


class PresupuestoAgotado(ErrorDominio):
    """Corte duro de tiempo, iteraciones o costo (RN-06, NFR-009)."""

    def __init__(self, recurso: str, consumido: float, limite: float) -> None:
        self.recurso = recurso
        self.consumido = consumido
        self.limite = limite
        super().__init__(
            f"Presupuesto agotado: {recurso} consumido={consumido!r} límite={limite!r}"
        )


class AccionDenegada(ErrorDominio):
    """PolicyGate rechazó una acción (RN-03, control correspondiente)."""

    def __init__(self, regla: str, motivo: str) -> None:
        self.regla = regla
        self.motivo = motivo
        super().__init__(f"Acción denegada por {regla}: {motivo}")
