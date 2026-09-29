from __future__ import annotations

from emh.core.ports import ResultadoComando
from emh.execution.wheelhouse import construir_wheelhouse, plataforma_pip_por_defecto


def test_construir_wheelhouse_usa_only_binary(tmp_path):
    llamadas = []

    def ejecutor_falso(comando):
        llamadas.append(comando)
        return ResultadoComando(codigo_salida=0, salida="ok")

    req = tmp_path / "requirements.txt"
    req.write_text("PyYAML==6.0.2\n")
    destino = tmp_path / "wheelhouse"

    r = construir_wheelhouse(req, destino, ejecutor=ejecutor_falso)

    assert r.codigo_salida == 0
    assert "--only-binary=:all:" in llamadas[0]
    assert destino.exists()


def test_construir_wheelhouse_apunta_a_la_plataforma_del_contenedor_no_del_host(tmp_path):
    """Regresión: encontrado en la primera ejecución en vivo real -- sin
    --platform, pip download trae la rueda del host que orquesta (macOS),
    incompatible con el contenedor Linux donde se instala (ADR-005)."""
    llamadas = []

    def ejecutor_falso(comando):
        llamadas.append(comando)
        return ResultadoComando(codigo_salida=0, salida="ok")

    req = tmp_path / "requirements.txt"
    req.write_text("PyYAML==6.0.2\n")
    construir_wheelhouse(req, tmp_path / "wheelhouse", ejecutor=ejecutor_falso, plataforma="manylinux2014_x86_64")

    comando = llamadas[0]
    assert "--platform" in comando and "manylinux2014_x86_64" in comando
    assert "--python-version" in comando
    assert "--implementation" in comando and "cp" in comando
    assert "--abi" in comando


def test_plataforma_pip_por_defecto_devuelve_manylinux():
    assert plataforma_pip_por_defecto().startswith("manylinux2014_")


def test_wheelhouse_incluye_paquetes_de_herramienta_de_la_estrategia(tmp_path):
    """Regresión hallazgo #11: pytest no está en el requirements.txt del repo;
    sin descargarlo, la primera verificación fallaba con código 127."""
    llamadas = []

    def ejecutor_falso(comando):
        llamadas.append(comando)
        return ResultadoComando(codigo_salida=0, salida="ok")

    req = tmp_path / "requirements.txt"
    req.write_text("PyYAML==6.0.2\n")
    construir_wheelhouse(req, tmp_path / "wh", ejecutor=ejecutor_falso, adicionales=["pytest"])
    assert llamadas[0][-1] == "pytest"
