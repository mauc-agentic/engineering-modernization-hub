"""El ejecutor de la tarea Fargate, probado de verdad (sin red): empaqueta un
trabajo como lo hace FargateSandbox, lo extrae y ejecuta comandos reales."""

from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[2] / "sandbox" / "entrypoint.py"
_spec = importlib.util.spec_from_file_location("sandbox_entrypoint", _RUTA)
ep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ep)


def _tar(archivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for nombre, datos in archivos.items():
            info = tarfile.TarInfo(nombre)
            info.size = len(datos)
            tar.addfile(info, io.BytesIO(datos))
    return buf.getvalue()


def test_extrae_workspace_wheelhouse_y_comandos(tmp_path):
    contenido = _tar({
        "workspace/a/b.txt": b"hola", "wheelhouse/x.whl": b"rueda",
        "job.json": json.dumps({"comandos": [["echo", "1"]]}).encode(),
    })
    ws, wh = tmp_path / "ws", tmp_path / "wh"
    ws.mkdir(), wh.mkdir()
    comandos = ep.extraer_trabajo(contenido, ws, wh)
    assert comandos == [["echo", "1"]]
    assert (ws / "a" / "b.txt").read_bytes() == b"hola"
    assert (wh / "x.whl").read_bytes() == b"rueda"


def test_rechaza_rutas_que_escapan_del_workspace(tmp_path):
    ws, wh = tmp_path / "ws", tmp_path / "wh"
    ws.mkdir(), wh.mkdir()
    with pytest.raises(ValueError):
        ep.extraer_trabajo(_tar({"workspace/../../evil.txt": b"x"}), ws, wh)
    assert not (tmp_path / "evil.txt").exists()


def test_ejecuta_secuencia_y_corta_si_un_paso_intermedio_falla(tmp_path):
    r = ep.ejecutar_comandos(
        [["python3", "-c", "import sys; sys.exit(3)"], ["echo", "no debe correr"]], tmp_path, tmp_path
    )
    assert len(r) == 1 and r[0]["codigo_salida"] == 3


def test_el_ultimo_comando_siempre_se_ejecuta_y_captura_salida(tmp_path):
    r = ep.ejecutar_comandos([["echo", "uno"], ["python3", "-c", "print('dos')"]], tmp_path, tmp_path)
    assert [x["codigo_salida"] for x in r] == [0, 0]
    assert "dos" in r[1]["salida"]


def test_el_codigo_del_repo_no_ve_variables_emh(tmp_path, monkeypatch):
    monkeypatch.setenv("EMH_JOB_OUTPUT_URL", "https://secreto")
    r = ep.ejecutar_comandos([["python3", "-c", "import os; print(sorted(k for k in os.environ if k.startswith('EMH')))"]], tmp_path, tmp_path)
    assert "[]" in r[0]["salida"]


def test_comando_inexistente_devuelve_127_sin_excepcion(tmp_path):
    r = ep.ejecutar_comandos([["no-existe-este-binario"]], tmp_path, tmp_path)
    assert r[0]["codigo_salida"] == 127
