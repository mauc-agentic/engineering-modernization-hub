"""Pruebas de la estrategia de referencia y de la extensibilidad (NFR-015):
una estrategia ficticia, definida SOLO en este archivo de pruebas, se
registra y se usa sin tocar ni una línea de emh/core (DOCS/06-estrategias.md §3.5)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from emh.strategies.python_dependency_upgrade import PythonDependencyUpgradeStrategy
from tests.factories import solicitud


def test_supports_dependencia_python():
    s = PythonDependencyUpgradeStrategy()
    assert s.supports(solicitud(version_esperada="PyYAML==6.0.2")).aplica


def test_discovery_signals_incluye_manifiestos():
    s = PythonDependencyUpgradeStrategy()
    patrones = [x.patron for x in s.discovery_signals()]
    assert "requirements.txt" in patrones


def test_official_sources_incluye_pypi():
    s = PythonDependencyUpgradeStrategy()
    dominios = {f.dominio for f in s.official_sources(solicitud())}
    assert dominios == {"pypi.org", "github.com"}  # exactamente estas fuentes, no más


def test_scope_template_solo_autoriza_modificar():
    s = PythonDependencyUpgradeStrategy()
    plantilla = s.scope_template()
    assert plantilla.operaciones == ["modificar"]


def test_command_profile_usa_wheelhouse_sin_red_en_contenedor():
    s = PythonDependencyUpgradeStrategy()
    perfil = s.command_profile()
    assert any("--no-index" in arg for paso in perfil.instalacion for arg in paso)
    assert perfil.verificacion[0][0].startswith("/tmp/venv/")  # NFR-004: raíz de solo lectura


# ---------------------------------------------------------------------------
# NFR-015: extensibilidad sin tocar el núcleo
# ---------------------------------------------------------------------------


class EchoUpgradeStrategy:
    """Estrategia ficticia (DOCS/06-estrategias.md §3.5), definida solo aquí,
    en tests/. Si esto compila y corre sin importar ni modificar emh.core,
    la interfaz de extensión funciona como se diseñó."""

    id = "echo_upgrade_ficticia"

    def evidence_probes(self, request):
        return []

    def supports(self, request):
        from emh.core.ports import Soporte

        return Soporte(aplica=True)

    def discovery_signals(self):
        from emh.core.ports import Senal

        return [Senal(patron="ECHO")]

    def official_sources(self, request):
        from emh.core.ports import DominioFuente

        return [DominioFuente(dominio="example.org", tipo="DOCUMENTACION_OFICIAL")]

    def command_profile(self):
        from emh.core.ports import PerfilComandos

        return PerfilComandos(instalacion=[], verificacion=[["true"]])

    def scope_template(self, plan_hint=None):
        from emh.core.ports import PlantillaAlcance

        return PlantillaAlcance(rutas=["ECHO.txt"], operaciones=["modificar"])

    def prompt_pack(self):
        from emh.core.ports import PaqueteInstrucciones

        return PaqueteInstrucciones(instrucciones="di ECHO y termina")


def test_estrategia_ficticia_se_registra_sin_tocar_el_nucleo():
    from emh.strategies.registry import REGISTRO_ESTRATEGIAS

    registro_prueba = dict(REGISTRO_ESTRATEGIAS)
    registro_prueba["echo_upgrade_ficticia"] = EchoUpgradeStrategy()

    estrategia = registro_prueba["echo_upgrade_ficticia"]
    assert estrategia.supports(solicitud()).aplica
    assert estrategia.command_profile().verificacion == [["true"]]


def test_ninguna_capa_del_nucleo_importa_estrategias_concretas():
    """Verificación estática (además de import-linter): ningún archivo de
    emh/core, emh/agent o emh/harness menciona el nombre de una estrategia
    concreta."""
    raiz = Path(__file__).resolve().parents[2] / "emh"
    prohibido = "PythonDependencyUpgradeStrategy"
    for capa in ("core", "agent", "harness"):
        for py in (raiz / capa).rglob("*.py"):
            assert prohibido not in py.read_text(encoding="utf-8"), f"{py} menciona la estrategia concreta"


def test_import_linter_pasa_con_la_estrategia_registrada(tmp_path):
    """Ejecuta el contrato real de import-linter (no solo un grep) para
    confirmar NFR-015 de punta a punta."""
    proyecto = Path(__file__).resolve().parents[2]
    resultado = subprocess.run(
        ["lint-imports"], cwd=proyecto, capture_output=True, text=True
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_perfil_python_declara_pytest_como_herramienta_del_sandbox():
    from emh.strategies.python_dependency_upgrade import PythonDependencyUpgradeStrategy

    perfil = PythonDependencyUpgradeStrategy().command_profile()
    assert perfil.paquetes_herramienta == ["pytest"]
    assert perfil.instalacion[-1][-1] == "pytest"


def test_sondas_de_evidencia_apuntan_a_los_metadatos_oficiales_de_la_version_objetivo():
    """Regresión: el modelo llegó a afirmar 'Flask 3 es compatible con Python 3.7'
    sin haber consultado nada. La estrategia obliga a traer requires_python."""
    from tests.factories import solicitud

    s = PythonDependencyUpgradeStrategy()
    sondas = s.evidence_probes(solicitud(version_esperada="Flask==3.0.0"))
    assert [(x.dominio, x.consulta) for x in sondas] == [("pypi.org", "pypi/Flask/3.0.0/json")]
    assert s.evidence_probes(solicitud(version_esperada="Flask>=3.0")) == []
