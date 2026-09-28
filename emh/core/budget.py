"""Control 4 — Presupuestos (DOCS/05-politicas-y-controles.md §4).

Corte duro de tiempo de pared, iteraciones y costo. El reloj y la tabla de
precios se inyectan para que la prueba de NFR-009 pueda controlar el tiempo
sin dormir de verdad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from emh.core.errors import PresupuestoAgotado
from emh.core.models import Solicitud, utcnow

# Precios por defecto: Amazon Nova 2 Lite, confirmados 2026-09-28
# (DOCS/ADR/ADR-002-proveedor-y-modelo.md). USD por token.
PRECIO_ENTRADA_POR_TOKEN_DEFECTO = 0.30 / 1_000_000
PRECIO_SALIDA_POR_TOKEN_DEFECTO = 2.50 / 1_000_000


@dataclass
class EstadoPresupuesto:
    tokens_entrada: int = 0
    tokens_salida: int = 0
    iteraciones_usadas: int = 0
    costo_estimado_usd: float = 0.0
    tiempo_transcurrido_segundos: float = 0.0


@dataclass
class PresupuestoMeter:
    """Un medidor por ejecución. Se construye una vez por `Ejecucion` y se
    consulta con `verificar()` antes de cada llamada costosa (control 4)."""

    solicitud: Solicitud
    ahora: Callable[[], datetime] = field(default=utcnow)
    precio_entrada_por_token: float = PRECIO_ENTRADA_POR_TOKEN_DEFECTO
    precio_salida_por_token: float = PRECIO_SALIDA_POR_TOKEN_DEFECTO
    momento_inicio: datetime | None = None
    """Si se da (al reconstruir el medidor tras una interrupción de
    aprobación), se usa como origen del tiempo de pared en vez de `ahora()`,
    para que la espera humana cuente como tiempo transcurrido real."""
    tokens_ya_consumidos: tuple[int, int] = (0, 0)
    """(tokens_entrada, tokens_salida) ya persistidos, al reconstruir."""
    iteraciones_ya_usadas: int = 0
    _inicio: datetime = field(init=False)
    _estado: EstadoPresupuesto = field(init=False, default_factory=EstadoPresupuesto)

    def __post_init__(self) -> None:
        self._inicio = self.momento_inicio if self.momento_inicio is not None else self.ahora()
        if self.tokens_ya_consumidos != (0, 0):
            self.registrar_llamada_modelo(*self.tokens_ya_consumidos)
        self._estado.iteraciones_usadas = self.iteraciones_ya_usadas

    @property
    def estado(self) -> EstadoPresupuesto:
        self._estado.tiempo_transcurrido_segundos = (
            self.ahora() - self._inicio
        ).total_seconds()
        return self._estado

    def registrar_llamada_modelo(self, tokens_entrada: int, tokens_salida: int) -> None:
        """Acumula tokens y recalcula el costo estimado (control 4, fórmula de costo)."""
        self._estado.tokens_entrada += tokens_entrada
        self._estado.tokens_salida += tokens_salida
        self._estado.costo_estimado_usd = (
            self._estado.tokens_entrada * self.precio_entrada_por_token
            + self._estado.tokens_salida * self.precio_salida_por_token
        )

    def registrar_iteracion(self) -> None:
        self._estado.iteraciones_usadas += 1

    def verificar(self) -> None:
        """Lanza `PresupuestoAgotado` si algún límite ya se superó.

        Se llama ANTES de la siguiente llamada costosa: la que ya está en
        vuelo se deja terminar (05-politicas-y-controles.md control 4).
        """
        e = self.estado
        if e.tiempo_transcurrido_segundos > self.solicitud.limite_tiempo_segundos:
            raise PresupuestoAgotado(
                "tiempo_segundos", e.tiempo_transcurrido_segundos,
                self.solicitud.limite_tiempo_segundos,
            )
        if e.iteraciones_usadas > self.solicitud.limite_iteraciones:
            raise PresupuestoAgotado(
                "iteraciones", e.iteraciones_usadas, self.solicitud.limite_iteraciones
            )
        if e.costo_estimado_usd > self.solicitud.limite_costo_usd:
            raise PresupuestoAgotado(
                "costo_usd", e.costo_estimado_usd, self.solicitud.limite_costo_usd
            )
