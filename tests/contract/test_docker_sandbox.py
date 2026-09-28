"""Prueba de contrato CONTRA DOCKER REAL (ADR-005). Se salta automáticamente
si el daemon de Docker no está disponible -- no es una simulación."""

from __future__ import annotations

import docker
import pytest

from emh.execution.docker_sandbox import DockerSandbox


def _docker_disponible() -> bool:
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _docker_disponible(), reason="Docker no disponible en este entorno")


@pytest.fixture()
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "hola.txt").write_text("hola desde el host\n")
    return ws


def test_crear_ejecutar_destruir_ciclo_completo(workspace):
    sandbox = DockerSandbox()
    contenedor_id = sandbox.crear(workspace)
    try:
        r = sandbox.ejecutar(contenedor_id, ["python3", "-c", "print(2 + 2)"])
        assert r.codigo_salida == 0
        assert "4" in r.salida
    finally:
        sandbox.destruir(contenedor_id)


def test_workspace_montado_y_visible_dentro(workspace):
    sandbox = DockerSandbox()
    contenedor_id = sandbox.crear(workspace)
    try:
        r = sandbox.ejecutar(contenedor_id, ["cat", "/workspace/hola.txt"])
        assert "hola desde el host" in r.salida
    finally:
        sandbox.destruir(contenedor_id)


def test_sin_red_dentro_del_contenedor(workspace):
    """NFR-005 / ADR-005: el contenedor no tiene red en absoluto."""
    sandbox = DockerSandbox()
    contenedor_id = sandbox.crear(workspace)
    try:
        r = sandbox.ejecutar(
            contenedor_id,
            ["python3", "-c",
             "import socket; socket.setdefaulttimeout(3)\n"
             "try:\n"
             "    socket.gethostbyname('pypi.org')\n"
             "    print('RED_DISPONIBLE')\n"
             "except Exception as e:\n"
             "    print('SIN_RED')\n"],
        )
        assert "SIN_RED" in r.salida
        assert "RED_DISPONIBLE" not in r.salida
    finally:
        sandbox.destruir(contenedor_id)


def test_usuario_no_root(workspace):
    """NFR-004: el proceso corre como usuario no root."""
    sandbox = DockerSandbox()
    contenedor_id = sandbox.crear(workspace)
    try:
        r = sandbox.ejecutar(contenedor_id, ["id", "-u"])
        assert r.salida.strip() == "1000"
    finally:
        sandbox.destruir(contenedor_id)


def test_raiz_de_solo_lectura_pero_tmp_escribible(workspace):
    """NFR-004: raíz de solo lectura salvo el workspace; /tmp es tmpfs
    escribible (para el venv del wheelhouse, ver 06-estrategias.md)."""
    sandbox = DockerSandbox()
    contenedor_id = sandbox.crear(workspace)
    try:
        r_tmp = sandbox.ejecutar(contenedor_id, ["sh", "-c", "echo ok > /tmp/prueba.txt && cat /tmp/prueba.txt"])
        assert "ok" in r_tmp.salida

        r_raiz = sandbox.ejecutar(contenedor_id, ["sh", "-c", "touch /raiz-prohibida.txt 2>&1 || echo SOLO_LECTURA"])
        assert "SOLO_LECTURA" in r_raiz.salida
    finally:
        sandbox.destruir(contenedor_id)


def test_con_red_true_lanza_valueerror(workspace):
    sandbox = DockerSandbox()
    contenedor_id = sandbox.crear(workspace)
    try:
        with pytest.raises(ValueError):
            sandbox.ejecutar(contenedor_id, ["echo", "hola"], con_red=True)
    finally:
        sandbox.destruir(contenedor_id)


def test_destruir_elimina_el_contenedor(workspace):
    sandbox = DockerSandbox()
    contenedor_id = sandbox.crear(workspace)
    sandbox.destruir(contenedor_id)

    cliente = docker.from_env()
    with pytest.raises(docker.errors.NotFound):
        cliente.containers.get(contenedor_id)
