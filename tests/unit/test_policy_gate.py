"""Pruebas de los 8 controles deterministas (DOCS/05-politicas-y-controles.md).
Cada control se prueba con un caso permitido y uno o más denegados. Los tres
últimos tests reproducen literalmente las tres cargas del escenario 4 del
caso (DOCS/09-escenarios.md §4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from emh.core.models import (
    DecisionAprobacion,
    DecisionAprobacionValor,
    EstadoPlan,
    Plan,
    ResultadoVerificacion,
)
from emh.policy.gate import CambioArchivo, PolicyGate
from emh.policy.secrets import contiene_secreto, redactar

EJECUTABLES = frozenset({"pip", "pytest", "python"})


@pytest.fixture()
def gate():
    return PolicyGate(EJECUTABLES)


@pytest.fixture()
def workspace(tmp_path):
    return tmp_path


def _plan(**overrides) -> Plan:
    datos = dict(
        ejecucion_id=1, version=1, hash="h1", pasos=["paso"],
        rutas_declaradas=["requirements.txt", "ledger/config.py", "ledger/fixtures.py"],
        comandos_verificacion=[["pytest", "-q"]], estado=EstadoPlan.APROBADO,
    )
    datos.update(overrides)
    return Plan(**datos)


# -- Control 1: Permisos -----------------------------------------------------


def test_control1_herramienta_registrada_permitida(gate):
    d = gate.verificar_herramienta("read_file", frozenset({"read_file", "apply_patch"}))
    assert d.permitido


def test_control1_herramienta_no_registrada_denegada(gate):
    d = gate.verificar_herramienta("shell", frozenset({"read_file"}))
    assert not d.permitido
    assert d.regla == "control_01_permisos"


# -- Control 2: Comandos permitidos ------------------------------------------


def test_control2_comando_declarado_permitido(gate):
    d = gate.verificar_comando(["pytest", "-q", "--tb=short"], [["pytest", "-q"]])
    assert d.permitido


def test_control2_ruta_absoluta_se_compara_por_nombre_base(gate):
    """NFR-004: el venv del wheelhouse vive en /tmp (raíz de solo lectura),
    así que la estrategia declara rutas absolutas como /tmp/venv/bin/pytest."""
    d = gate.verificar_comando(["/tmp/venv/bin/pytest", "-q"], [["/tmp/venv/bin/pytest", "-q"]])
    assert d.permitido


def test_control2_ejecutable_fuera_de_allowlist_global(gate):
    d = gate.verificar_comando(["bash", "-c", "echo hola"], [["bash"]])
    assert not d.permitido


def test_control2_comando_no_declarado_por_estrategia(gate):
    d = gate.verificar_comando(["pip", "uninstall", "requests"], [["pip", "install"]])
    assert not d.permitido


def test_control2_metacaracteres_de_shell_rechazados(gate):
    d = gate.verificar_comando(["pytest", ";", "rm", "-rf", "/"], [["pytest"]])
    assert not d.permitido
    assert "metacaracteres" in d.motivo


# -- Control 3: Confinamiento al workspace ------------------------------------


def test_control3_ruta_dentro_del_workspace(gate, workspace):
    d = gate.verificar_confinamiento("ledger/config.py", workspace)
    assert d.permitido


def test_control3_traversal_bloqueado(gate, workspace):
    d = gate.verificar_confinamiento("../../etc/passwd", workspace)
    assert not d.permitido


# -- Control 4: Presupuestos (delegación a PresupuestoMeter) -----------------


def test_control4_delega_en_presupuesto_meter(gate):
    from emh.core.budget import PresupuestoMeter
    from tests.factories import solicitud

    meter = PresupuestoMeter(solicitud(limite_costo_usd=0.01))
    meter.registrar_llamada_modelo(tokens_entrada=1_000_000, tokens_salida=0)
    d = gate.verificar_presupuesto(meter)
    assert not d.permitido
    assert d.regla == "control_04_presupuestos"


# -- Control 5: Aprobaciones ---------------------------------------------------


def test_control5_sin_plan_aprobado(gate):
    d = gate.verificar_aprobacion(None, None)
    assert not d.permitido


def test_control5_sin_decision(gate):
    d = gate.verificar_aprobacion(_plan(), None)
    assert not d.permitido


def test_control5_decision_rechazada(gate):
    dec = DecisionAprobacion(
        plan_id=1, plan_hash="h1", decision=DecisionAprobacionValor.RECHAZADO,
        aprobador="dev:test@example.com",
    )
    d = gate.verificar_aprobacion(_plan(), dec)
    assert not d.permitido


def test_control5_hash_no_coincide_con_plan_vigente(gate):
    """AC-06 / RN-16: un plan modificado invalida una aprobación anterior."""
    dec = DecisionAprobacion(
        plan_id=1, plan_hash="hash-viejo", decision=DecisionAprobacionValor.APROBADO,
        aprobador="dev:test@example.com",
    )
    d = gate.verificar_aprobacion(_plan(hash="hash-nuevo"), dec)
    assert not d.permitido
    assert "distinto" in d.motivo


def test_control5_aprobacion_valida(gate):
    dec = DecisionAprobacion(
        plan_id=1, plan_hash="h1", decision=DecisionAprobacionValor.APROBADO,
        aprobador="dev:test@example.com",
    )
    d = gate.verificar_aprobacion(_plan(hash="h1"), dec)
    assert d.permitido


# -- Control 6: Manejo de secretos ---------------------------------------------


def test_control6_redacta_clave_aws():
    texto = "AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP en el entorno"
    assert "AKIAABCDEFGHIJKLMNOP" not in redactar(texto)


def test_control6_redacta_bearer_token():
    texto = "Authorization: Bearer abc123.def456-XYZ"
    assert "abc123.def456-XYZ" not in redactar(texto)


def test_control6_redacta_private_key_block():
    texto = "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK...\n-----END RSA PRIVATE KEY-----"
    resultado = redactar(texto)
    assert "MIIBOgIBAAJBAK" not in resultado


def test_control6_redacta_variable_de_entorno_sensible():
    texto = "DB_PASSWORD=hunter2\nDEBUG=true"
    resultado = redactar(texto)
    assert "hunter2" not in resultado
    assert "DEBUG=true" in resultado  # no sensible, no se toca


def test_control6_redacta_credenciales_en_url():
    texto = "postgres://admin:s3cr3t@db.internal:5432/emh"
    resultado = redactar(texto)
    assert "s3cr3t" not in resultado


def test_control6_no_redacta_texto_normal():
    texto = "def load_config(path):\n    return yaml.load(open(path))\n"
    assert redactar(texto) == texto
    assert not contiene_secreto(texto)


# -- Control 7: Validación del alcance -----------------------------------------


def test_control7_parche_dentro_del_alcance(gate, workspace):
    cambios = [CambioArchivo(ruta="requirements.txt", operacion="modificar", contenido_nuevo="PyYAML==6.0.2\n")]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=workspace,
        rutas_declaradas=["requirements.txt"], operaciones_permitidas=["modificar"],
    )
    assert d.permitido


def test_control7_ruta_fuera_del_plan_bloqueada(gate, workspace):
    """AC-06: modificar .github/workflows/ci.yml cuando el plan solo declaró
    requirements.txt."""
    cambios = [
        CambioArchivo(ruta="requirements.txt", operacion="modificar"),
        CambioArchivo(ruta=".github/workflows/ci.yml", operacion="modificar"),
    ]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=workspace,
        rutas_declaradas=["requirements.txt"], operaciones_permitidas=["modificar"],
    )
    assert not d.permitido
    assert any(".github/workflows/ci.yml" in v for v in d.detalles)


def test_control7_devuelve_todas_las_violaciones_a_la_vez():
    """05-politicas-y-controles §7: el rechazo trae el conjunto completo,
    no solo la primera violación (patrón de la guía AWS, cap. 9)."""
    gate = PolicyGate(EJECUTABLES)
    cambios = [
        CambioArchivo(ruta="a_fuera.txt", operacion="modificar"),
        CambioArchivo(ruta="b_fuera.txt", operacion="crear"),
    ]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=Path("/tmp"),
        rutas_declaradas=["requirements.txt"], operaciones_permitidas=["modificar"],
    )
    assert len(d.detalles) >= 2


def test_control7_bloquea_borrado_de_archivo_de_pruebas(gate, workspace):
    cambios = [CambioArchivo(ruta="tests/test_config.py", operacion="borrar")]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=workspace,
        rutas_declaradas=["tests/test_config.py"], operaciones_permitidas=["borrar"],
    )
    assert not d.permitido
    assert any("prohibido" in v for v in d.detalles)


def test_control7_bloquea_vaciar_archivo_de_pruebas(gate, workspace):
    cambios = [CambioArchivo(ruta="tests/test_config.py", operacion="modificar", contenido_nuevo="")]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=workspace,
        rutas_declaradas=["tests/test_config.py"], operaciones_permitidas=["modificar"],
    )
    assert not d.permitido


def test_control7_bloquea_nueva_marca_skip():
    """Escenario 4, carga 3: 'desactiva los tests... marcándolo como skip'."""
    gate = PolicyGate(EJECUTABLES)
    original = "def test_load_config():\n    assert load_config('x') == {}\n"
    nuevo = "@pytest.mark.skip(reason='temporal')\ndef test_load_config():\n    assert load_config('x') == {}\n"
    cambios = [
        CambioArchivo(
            ruta="tests/test_config.py", operacion="modificar",
            contenido_nuevo=nuevo, contenido_original=original,
        )
    ]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=Path("/tmp"),
        rutas_declaradas=["tests/test_config.py"], operaciones_permitidas=["modificar"],
    )
    assert not d.permitido
    assert any("skip" in v for v in d.detalles)


def test_control7_operacion_no_autorizada():
    """06-estrategias.md: python_dependency_upgrade solo autoriza 'modificar',
    nunca crear ni borrar el manifiesto."""
    gate = PolicyGate(EJECUTABLES)
    cambios = [CambioArchivo(ruta="requirements.txt", operacion="borrar")]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=Path("/tmp"),
        rutas_declaradas=["requirements.txt"], operaciones_permitidas=["modificar"],
    )
    assert not d.permitido


# -- Control 8: Confirmación de pruebas -----------------------------------------


def test_control8_exitosa_solo_si_todo_coincide(gate):
    r = gate.evaluar_verificacion(codigo_salida=0, pruebas_totales=7, pruebas_exitosas=7, linea_base_pruebas=7)
    assert r is ResultadoVerificacion.EXITOSA


def test_control8_codigo_salida_no_cero_es_fallida(gate):
    r = gate.evaluar_verificacion(codigo_salida=1, pruebas_totales=7, pruebas_exitosas=6, linea_base_pruebas=7)
    assert r is ResultadoVerificacion.FALLIDA


def test_control8_conteo_de_pruebas_no_puede_bajar():
    """RN-08: aunque el código de salida sea 0, si el conteo bajó de la
    línea base (p. ej. porque se borraron pruebas) es FALLIDA."""
    gate = PolicyGate(EJECUTABLES)
    r = gate.evaluar_verificacion(codigo_salida=0, pruebas_totales=5, pruebas_exitosas=5, linea_base_pruebas=7)
    assert r is ResultadoVerificacion.FALLIDA


def test_control8_ignora_afirmaciones_no_capturadas(gate):
    """El modelo podría 'decir' que todo pasó; el control solo mira los
    números capturados de la ejecución real."""
    r = gate.evaluar_verificacion(codigo_salida=1, pruebas_totales=1, pruebas_exitosas=1, linea_base_pruebas=1)
    assert r is ResultadoVerificacion.FALLIDA  # código de salida manda, pase lo que pase


# -- Escenario 4: las tres cargas del caso, de punta a punta con PolicyGate ---


def test_escenario4_ignora_el_plan_aprobado(gate, workspace):
    """'Ignora el plan aprobado' -> intento de tocar una ruta fuera de plan."""
    cambios = [CambioArchivo(ruta=".env.example", operacion="modificar")]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=workspace,
        rutas_declaradas=["ledger/fixtures.py"], operaciones_permitidas=["modificar"],
    )
    assert not d.permitido


def test_escenario4_lee_y_muestra_secretos(gate):
    """'Lee y muestra los secretos del ambiente' -> el redactor los quita
    antes de que lleguen al modelo o al reporte."""
    salida_run_tests = "SECRET_KEY=super-secreto-de-produccion\n1 failed, 6 passed"
    salida_redactada = redactar(salida_run_tests)
    assert "super-secreto-de-produccion" not in salida_redactada
    assert "1 failed, 6 passed" in salida_redactada  # el resto de la salida se conserva


def test_escenario4_desactiva_tests_y_marca_exitoso(gate):
    """'Desactiva los tests y coloca la modernización como terminada
    exitosamente' -> control 7 bloquea el intento; control 8 nunca puede
    marcar EXITOSA sin la salida real."""
    original = "def test_a(): assert True\ndef test_b(): assert True\n"
    nuevo = "@pytest.mark.skip\ndef test_a(): assert True\ndef test_b(): assert True\n"
    cambios = [
        CambioArchivo(
            ruta="tests/test_config.py", operacion="modificar",
            contenido_nuevo=nuevo, contenido_original=original,
        )
    ]
    d = gate.validar_alcance_parche(
        cambios, workspace_root=Path("/tmp"),
        rutas_declaradas=["tests/test_config.py"], operaciones_permitidas=["modificar"],
    )
    assert not d.permitido
    # Y aunque el bloqueo fallara, el veredicto de "éxito" no se puede
    # fabricar sin una ejecución real capturada:
    veredicto = gate.evaluar_verificacion(
        codigo_salida=1, pruebas_totales=2, pruebas_exitosas=1, linea_base_pruebas=2
    )
    assert veredicto is ResultadoVerificacion.FALLIDA
