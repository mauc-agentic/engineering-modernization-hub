"""`PolicyGate` — los ocho controles deterministas (DOCS/05-politicas-y-
controles.md). Nada aquí consulta al modelo (RN-02, RN-03). *Deny by
default*: lo que ninguna regla permite explícitamente, se rechaza.

Se invoca DENTRO de cada herramienta (`emh.harness`), nunca como un paso
previo del grafo que un nodo pudiera saltarse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from emh.core.budget import PresupuestoMeter
from emh.core.models import DecisionAprobacion, DecisionAprobacionValor, Plan, ResultadoVerificacion

Operacion = Literal["crear", "modificar", "borrar"]

# Metacaracteres de shell: aunque los comandos siempre se invocan como lista
# de argumentos (nunca `shell=True`), se rechaza cualquier argumento que los
# contenga como defensa en profundidad (control 2).
_METACARACTERES_SHELL = (";", "&&", "||", "|", "`", "$(", "\n", ">", "<")

_MARCAS_SKIP = ("@pytest.mark.skip", "@pytest.mark.xfail", "pytest.skip(", "pytest.mark.skip(")


@dataclass
class Decision:
    permitido: bool
    regla: str
    motivo: str
    detalles: list[str] = field(default_factory=list)


@dataclass
class CambioArchivo:
    """Una entrada del parche propuesto (control 7)."""

    ruta: str
    operacion: Operacion
    contenido_nuevo: str | None = None
    contenido_original: str | None = None


def _dentro_del_workspace(ruta: str, workspace_root: Path) -> bool:
    try:
        objetivo = (workspace_root / ruta).resolve()
        objetivo.relative_to(workspace_root.resolve())
    except ValueError:
        return False
    return True


def _contar_marcas_skip(texto: str) -> int:
    return sum(texto.count(m) for m in _MARCAS_SKIP)


class PolicyGate:
    def __init__(
        self,
        ejecutables_permitidos_globales: frozenset[str],
        rutas_protegidas_pruebas: tuple[str, ...] = ("tests/", "test_"),
    ) -> None:
        self._ejecutables_globales = ejecutables_permitidos_globales
        self._rutas_protegidas_pruebas = rutas_protegidas_pruebas

    # -- Control 1: Permisos ------------------------------------------------

    def verificar_herramienta(
        self, nombre: str, herramientas_registradas: frozenset[str]
    ) -> Decision:
        if nombre not in herramientas_registradas:
            return Decision(
                False, "control_01_permisos", f"herramienta '{nombre}' no está registrada"
            )
        return Decision(True, "control_01_permisos", "herramienta registrada")

    # -- Control 2: Comandos permitidos --------------------------------------

    def verificar_comando(
        self, comando: list[str], comandos_permitidos_estrategia: list[list[str]]
    ) -> Decision:
        if not comando:
            return Decision(False, "control_02_comandos_permitidos", "comando vacío")

        unido = " ".join(comando)
        if any(m in unido for m in _METACARACTERES_SHELL):
            return Decision(
                False, "control_02_comandos_permitidos",
                "el comando contiene metacaracteres de shell",
            )

        # Se compara por nombre base: la estrategia puede declarar rutas
        # absolutas (p. ej. /tmp/venv/bin/pytest, NFR-004: venv en tmpfs
        # porque la raíz del sandbox es de solo lectura). Esto no afloja el
        # control: el comando completo TODAVÍA debe coincidir con un
        # perfil exacto declarado por la estrategia activa, más abajo.
        if Path(comando[0]).name not in self._ejecutables_globales:
            return Decision(
                False, "control_02_comandos_permitidos",
                f"ejecutable '{comando[0]}' fuera de la allowlist global",
            )

        for perfil in comandos_permitidos_estrategia:
            if comando[: len(perfil)] == perfil:
                return Decision(True, "control_02_comandos_permitidos", "comando permitido")

        return Decision(
            False, "control_02_comandos_permitidos",
            "el comando no coincide con el perfil de la estrategia activa",
        )

    # -- Control 3: Rutas modificables (confinamiento simple, lecturas) -----

    def verificar_confinamiento(self, ruta: str, workspace_root: Path) -> Decision:
        if not _dentro_del_workspace(ruta, workspace_root):
            return Decision(
                False, "control_03_rutas_modificables", f"'{ruta}' escapa del workspace"
            )
        return Decision(True, "control_03_rutas_modificables", "ruta confinada al workspace")

    # -- Control 4: Presupuestos ---------------------------------------------

    def verificar_presupuesto(self, meter: PresupuestoMeter) -> Decision:
        try:
            meter.verificar()
        except Exception as exc:  # PresupuestoAgotado
            return Decision(False, "control_04_presupuestos", str(exc))
        return Decision(True, "control_04_presupuestos", "dentro del presupuesto")

    # -- Control 5: Aprobaciones ----------------------------------------------

    def verificar_aprobacion(
        self, plan_aprobado: Plan | None, decision: DecisionAprobacion | None
    ) -> Decision:
        if plan_aprobado is None:
            return Decision(False, "control_05_aprobaciones", "no hay plan vigente")
        if decision is None:
            return Decision(False, "control_05_aprobaciones", "no hay decisión de aprobación")
        if decision.decision != DecisionAprobacionValor.APROBADO:
            return Decision(False, "control_05_aprobaciones", "el plan fue rechazado")
        if decision.plan_hash != plan_aprobado.hash:
            return Decision(
                False, "control_05_aprobaciones",
                "la aprobación referencia un plan distinto al vigente",
            )
        return Decision(True, "control_05_aprobaciones", "aprobación válida para el plan vigente")

    # -- Control 7: Validación del alcance (parche completo) -----------------

    def validar_alcance_parche(
        self,
        cambios: list[CambioArchivo],
        *,
        workspace_root: Path,
        rutas_declaradas: list[str],
        operaciones_permitidas: list[Operacion],
    ) -> Decision:
        violaciones: list[str] = []
        for c in cambios:
            if not _dentro_del_workspace(c.ruta, workspace_root):
                violaciones.append(f"{c.ruta}: fuera del workspace")
                continue
            if c.ruta not in rutas_declaradas:
                violaciones.append(f"{c.ruta}: no declarada en el plan aprobado")
            if c.operacion not in operaciones_permitidas:
                violaciones.append(
                    f"{c.ruta}: operación '{c.operacion}' no autorizada por el plan"
                )
            es_prueba = any(c.ruta.startswith(p) for p in self._rutas_protegidas_pruebas)
            if es_prueba:
                if c.operacion == "borrar":
                    violaciones.append(f"{c.ruta}: borrar un archivo de pruebas está prohibido")
                if c.contenido_nuevo is not None and c.contenido_nuevo.strip() == "":
                    violaciones.append(f"{c.ruta}: vaciar un archivo de pruebas está prohibido")
                if c.contenido_nuevo is not None:
                    nuevas = _contar_marcas_skip(c.contenido_nuevo) - _contar_marcas_skip(
                        c.contenido_original or ""
                    )
                    if nuevas > 0:
                        violaciones.append(
                            f"{c.ruta}: añade {nuevas} marca(s) skip/xfail nueva(s)"
                        )

        if violaciones:
            return Decision(
                False, "control_07_validacion_alcance",
                "el parche viola el alcance aprobado", detalles=violaciones,
            )
        return Decision(True, "control_07_validacion_alcance", "dentro del alcance aprobado")

    # -- Control 8: Confirmación de pruebas -----------------------------------

    def evaluar_verificacion(
        self,
        codigo_salida: int,
        pruebas_totales: int,
        pruebas_exitosas: int,
        linea_base_pruebas: int,
    ) -> ResultadoVerificacion:
        """Deriva el veredicto EXCLUSIVAMENTE de la salida real capturada
        (RN-08). El modelo puede leer este resultado, nunca escribirlo."""
        if (
            codigo_salida == 0
            and pruebas_exitosas == pruebas_totales
            and pruebas_totales >= linea_base_pruebas
        ):
            return ResultadoVerificacion.EXITOSA
        return ResultadoVerificacion.FALLIDA
