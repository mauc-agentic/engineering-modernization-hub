"""Nivel A (SIMULATED): recorre el grafo completo de extremo a extremo con
`ScriptedModel`, reproduciendo el Ejemplo A de DOCS/09-escenarios.md §2 --
un primer intento que rompe una prueba (escenario 3) y una corrección que
termina en LISTO_PARA_REVISION (escenario 1). Todo lo demás (PolicyGate,
persistencia SQLite, harness) es real; solo el modelo está guionado."""

from __future__ import annotations

import pytest

from emh.agent.graph import Entorno
from emh.agent.runner import LangGraphAgentRunner
from emh.core.models import DecisionAprobacion, DecisionAprobacionValor, EstadoEjecucion, ResultadoEjecucion
from emh.core.ports import LlamadaHerramientaPropuesta, ResultadoComando, RespuestaModelo
from emh.models.scripted import ScriptedModel
from emh.persistence.sqlite_repo import SqliteRunRepository
from emh.policy.gate import PolicyGate
from tests.factories import ejecucion, solicitud

pytestmark = pytest.mark.simulated

EJECUTABLES = frozenset({"pip", "pytest", "python", "git"})


class SandboxSecuencial:
    """Fake de Sandbox que devuelve resultados distintos en cada llamada,
    en orden -- simula el primer intento fallido y el segundo exitoso."""

    def __init__(self, resultados_pytest: list[ResultadoComando]):
        self._resultados = list(resultados_pytest)
        self._indice = 0

    def crear(self, workspace, **kwargs):
        return f"contenedor-{self._indice}"

    def ejecutar(self, identificador, comando, *, con_red=False):
        # Solo el comando de verificación real (pytest) consume el guion;
        # los pasos de instalación (venv, pip) se simulan como exitosos --
        # no son lo que este test está verificando (eso lo cubre
        # test_run_tests_ejecuta_instalacion_y_verificacion_en_un_solo_contenedor).
        if any("pytest" in parte for parte in comando):
            r = self._resultados[self._indice]
            self._indice += 1
            return r
        return ResultadoComando(codigo_salida=0, salida="(paso de instalación simulado)")

    def destruir(self, identificador):
        pass


def _tool(id_, nombre, argumentos):
    return LlamadaHerramientaPropuesta(id=id_, nombre=nombre, argumentos=argumentos)


def _respuesta(id_, nombre, argumentos, tokens_e=200, tokens_s=50):
    return RespuestaModelo(
        texto=None, llamadas_herramienta=[_tool(id_, nombre, argumentos)],
        tokens_entrada=tokens_e, tokens_salida=tokens_s,
    )


@pytest.fixture()
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("PyYAML==5.3.1\n")
    (ws / "ledger").mkdir()
    (ws / "ledger" / "config.py").write_text("import yaml\n\ndef load_config(p):\n    return yaml.load(open(p))\n")
    (ws / "ledger" / "fixtures.py").write_text("import yaml\n\ndef load_fixtures(p):\n    return yaml.load(open(p))\n")
    return ws


@pytest.fixture()
def repo(tmp_path):
    r = SqliteRunRepository(tmp_path / "test.db")
    yield r
    r.close()


def test_flujo_completo_exito_con_correccion(repo, workspace):
    # -- Arrange: solicitud y ejecución ya registradas (UC-001) --------------
    s = repo.guardar_solicitud(solicitud(
        objetivo="Actualizar PyYAML de 5.3.1 a 6.0.2", version_esperada="PyYAML==6.0.2",
        limite_iteraciones=3, limite_costo_usd=1.0,
    ))
    e = repo.guardar_ejecucion(ejecucion(solicitud_id=s.id))

    guion = [
        _respuesta("t1", "objetivo_interpretado", {"objetivo_normalizado": "Actualizar PyYAML a 6.0.2"}),
        _respuesta("t2", "listo", {"resumen": "requirements.txt tiene PyYAML==5.3.1; dos usos de yaml.load sin Loader= en ledger/config.py y ledger/fixtures.py"}),
        _respuesta("t3", "listo", {"resumen": "PyYAML 6.0 exige Loader= explícito en yaml.load (release notes oficiales)"}),
        _respuesta("t4", "veredicto_viabilidad", {
            "veredicto": "VIABLE",
            "impacto_detectado": "yaml.load sin Loader= falla en 6.0.2 en dos archivos",
            "evidencia": "Release notes de PyYAML 6.0 (pypi.org / github.com)",
        }),
        _respuesta("t5", "plan_propuesto", {
            "pasos": ["Actualizar requirements.txt", "Añadir Loader=yaml.SafeLoader en config.py y fixtures.py", "Ejecutar pytest"],
            "rutas_declaradas": ["requirements.txt", "ledger/config.py", "ledger/fixtures.py"],
            "riesgos": "Ninguno crítico",
        }),
        # Primer intento: solo el manifiesto (deliberadamente incompleto -> dispara escenario 3)
        _respuesta("t6", "parche_propuesto", {
            "cambios": [{"ruta": "requirements.txt", "operacion": "modificar", "contenido_nuevo": "PyYAML==6.0.2\n"}]
        }),
        _respuesta("t7", "diagnostico", {"causa_raiz": "yaml.load sin Loader= lanza TypeError en PyYAML 6.0.2"}),
        # Corrección: ahora sí toca los dos módulos afectados
        _respuesta("t8", "parche_propuesto", {
            "cambios": [
                {"ruta": "ledger/config.py", "operacion": "modificar",
                 "contenido_nuevo": "import yaml\n\ndef load_config(p):\n    return yaml.load(open(p), Loader=yaml.SafeLoader)\n"},
                {"ruta": "ledger/fixtures.py", "operacion": "modificar",
                 "contenido_nuevo": "import yaml\n\ndef load_fixtures(p):\n    return yaml.load(open(p), Loader=yaml.SafeLoader)\n"},
            ]
        }),
    ]
    modelo = ScriptedModel(guion)

    sandbox = SandboxSecuencial([
        ResultadoComando(codigo_salida=1, salida="FAILED tests/test_config.py::test_load_config\n1 failed, 6 passed in 0.4s"),
        ResultadoComando(codigo_salida=0, salida="7 passed in 0.3s"),
    ])

    def ejecutor_host_falso(comando, cwd):
        return ResultadoComando(codigo_salida=0, salida="ya clonado (falso)")

    entorno = Entorno(
        repo=repo, modelo=modelo, gate=PolicyGate(EJECUTABLES), sandbox=sandbox,
        workspace_root_para=lambda eid: workspace, ejecutor_host=ejecutor_host_falso,
        fetcher=lambda url: "(fuente falsa)",
    )
    runner = LangGraphAgentRunner(entorno)

    # -- Act: correr hasta la compuerta de aprobación -------------------------
    runner.run(e.id)

    ejecucion_pausada = repo.obtener_ejecucion(e.id)
    assert ejecucion_pausada.estado is EstadoEjecucion.ESPERANDO_APROBACION
    assert ejecucion_pausada.resultado is None

    plan = repo.obtener_plan_vigente(e.id)
    assert plan is not None
    assert set(plan.rutas_declaradas) == {"requirements.txt", "ledger/config.py", "ledger/fixtures.py"}

    # -- Act: el desarrollador aprueba (UC-003) --------------------------------
    repo.guardar_decision_aprobacion(DecisionAprobacion(
        plan_id=plan.id, plan_hash=plan.hash, decision=DecisionAprobacionValor.APROBADO,
        aprobador="dev:test@example.com",
    ))
    runner.resume(e.id)

    # -- Assert: resultado final ------------------------------------------------
    final = repo.obtener_ejecucion(e.id)
    assert final.estado is EstadoEjecucion.FINALIZADA
    assert final.resultado is ResultadoEjecucion.LISTO_PARA_REVISION
    assert final.iteraciones_usadas == 1  # un ciclo de corrección (límite era 3)

    verificaciones = repo.listar_verificaciones(e.id)
    assert len(verificaciones) == 2
    assert verificaciones[0].resultado.value == "FALLIDA"
    assert verificaciones[1].resultado.value == "EXITOSA"

    # El código realmente quedó corregido en el workspace (no solo "se dijo"):
    assert "Loader=yaml.SafeLoader" in (workspace / "ledger" / "config.py").read_text()
    assert "Loader=yaml.SafeLoader" in (workspace / "ledger" / "fixtures.py").read_text()

    # Trazabilidad: 8 llamadas al modelo quedaron persistidas (NFR-014)
    llamadas = repo.listar_llamadas_modelo(e.id)
    assert len(llamadas) == 8
