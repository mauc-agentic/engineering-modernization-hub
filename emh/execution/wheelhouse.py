"""*Wheelhouse* (ADR-005, decisión D-6): el host descarga las ruedas ANTES
de crear el sandbox, para que el contenedor nunca necesite red."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable
from pathlib import Path

from emh.core.ports import ResultadoComando

EjecutorPip = Callable[[list[str]], ResultadoComando]


def _ejecutor_real(comando: list[str]) -> ResultadoComando:
    proceso = subprocess.run(comando, capture_output=True, text=True, timeout=300)
    return ResultadoComando(codigo_salida=proceso.returncode, salida=proceso.stdout + proceso.stderr)


def plataforma_pip_por_defecto() -> str:
    """Hallazgo en vivo: `pip download` sin --platform descarga la rueda
    del host que orquesta (macOS/arm64 en desarrollo), no la del contenedor
    Linux donde se instala -- pip install --no-index falla dentro del
    sandbox con 'No matching distribution'. Se asume que el sandbox corre
    en la misma arquitectura que este proceso (cierto en Docker Desktop
    nativo, ADR-005; y en un despliegue de Fargate de una sola arquitectura
    para API y sandbox, ADR-006)."""
    maquina = platform.machine().lower()
    arch = "aarch64" if maquina in ("arm64", "aarch64") else "x86_64"
    return f"manylinux2014_{arch}"


def construir_wheelhouse(
    requirements_path: Path,
    destino: Path,
    *,
    ejecutor: EjecutorPip = _ejecutor_real,
    plataforma: str | None = None,
    version_python: str = "312",
    adicionales: list[str] | None = None,
) -> ResultadoComando:
    """Descarga las ruedas binarias de `requirements_path` a `destino`,
    para la plataforma del CONTENEDOR (Linux), no la del host que orquesta.

    `--only-binary=:all:` es la decisión clave: nunca se ejecuta `setup.py`
    de un paquete sin rueda para la plataforma objetivo (limitación conocida
    de ADR-005: ese paquete termina en BLOQUEADO, no en una instalación con
    red abierta).
    """
    destino.mkdir(parents=True, exist_ok=True)
    plataforma = plataforma or plataforma_pip_por_defecto()
    comando = [
        "pip", "download", "--only-binary=:all:",
        "--platform", plataforma, "--python-version", version_python,
        "--implementation", "cp", "--abi", f"cp{version_python}",
        "-d", str(destino), "-r", str(requirements_path),
        *(adicionales or []),
    ]
    return ejecutor(comando)
