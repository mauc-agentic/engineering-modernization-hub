from __future__ import annotations

from pathlib import Path

from emh.core.ports import ResultadoComando
from emh.execution.wheelhouse import construir_wheelhouse


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
