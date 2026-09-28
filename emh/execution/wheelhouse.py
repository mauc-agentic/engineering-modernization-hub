"""*Wheelhouse* (ADR-005, decisión D-6): el host descarga las ruedas ANTES
de crear el sandbox, para que el contenedor nunca necesite red."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from emh.core.ports import ResultadoComando

EjecutorPip = Callable[[list[str]], ResultadoComando]


def _ejecutor_real(comando: list[str]) -> ResultadoComando:
    proceso = subprocess.run(comando, capture_output=True, text=True, timeout=300)
    return ResultadoComando(codigo_salida=proceso.returncode, salida=proceso.stdout + proceso.stderr)


def construir_wheelhouse(
    requirements_path: Path, destino: Path, *, ejecutor: EjecutorPip = _ejecutor_real
) -> ResultadoComando:
    """Descarga las ruedas binarias de `requirements_path` a `destino`.

    `--only-binary=:all:` es la decisión clave: nunca se ejecuta `setup.py`
    de un paquete sin rueda para la plataforma objetivo (limitación conocida
    de ADR-005: ese paquete termina en BLOQUEADO, no en una instalación con
    red abierta).
    """
    destino.mkdir(parents=True, exist_ok=True)
    comando = [
        "pip", "download", "--only-binary=:all:", "-d", str(destino), "-r", str(requirements_path),
    ]
    return ejecutor(comando)
