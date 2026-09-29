"""Ejecutor de la tarea efímera de verificación (ADR-006, Fargate). Solo
biblioteca estándar: la imagen del sandbox no instala `emh`.

Contrato con `FargateSandbox` (lado API):
  EMH_JOB_INPUT_URL   URL prefirmada (GET) de un .tar.gz con `workspace/`,
                      `wheelhouse/` (opcional) y `job.json` {"comandos": [[...], ...]}
  EMH_JOB_OUTPUT_URL  URL prefirmada (PUT) donde se sube el resultado JSON
                      {"resultados": [{"codigo_salida": int, "salida": str}, ...]}

La tarea NO tiene permisos IAM (NFR-004): solo puede leer y escribir esos dos
objetos, por las URLs. Las variables EMH_* se retiran del entorno antes de
ejecutar código del repositorio objetivo, que nunca las ve.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

TIEMPO_MAXIMO_COMANDO_SEGUNDOS = 600
SALIDA_MAXIMA_CARACTERES = 200_000


def _entorno_limpio(home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def extraer_trabajo(contenido: bytes, raiz_workspace: Path, raiz_wheelhouse: Path) -> list[list[str]]:
    """Descomprime el trabajo y devuelve los comandos. Rechaza rutas que
    escapen del directorio de destino (tar malicioso)."""
    comandos: list[list[str]] = []
    with tarfile.open(fileobj=io.BytesIO(contenido), mode="r:gz") as tar:
        for miembro in tar.getmembers():
            if miembro.name == "job.json":
                comandos = json.loads(tar.extractfile(miembro).read())["comandos"]
                continue
            destino_base, relativa = None, None
            for prefijo, base in (("workspace/", raiz_workspace), ("wheelhouse/", raiz_wheelhouse)):
                if miembro.name.startswith(prefijo):
                    destino_base, relativa = base, miembro.name[len(prefijo):]
            if destino_base is None or not relativa:
                continue
            destino = (destino_base / relativa).resolve()
            if destino_base.resolve() not in destino.parents and destino != destino_base.resolve():
                raise ValueError(f"ruta fuera del destino en el tar: {miembro.name}")
            if miembro.issym() or miembro.islnk():
                continue  # sin enlaces: no hay forma de apuntar fuera del workspace
            if miembro.isdir():
                destino.mkdir(parents=True, exist_ok=True)
            elif miembro.isfile():
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(tar.extractfile(miembro).read())
                destino.chmod(miembro.mode & 0o755 or 0o644)
    return comandos


def ejecutar_comandos(comandos: list[list[str]], cwd: Path, home: Path) -> list[dict]:
    """Misma semántica que `run_tests` en local: si un paso que no es el
    último falla, no se sigue (no tiene sentido verificar sin instalar)."""
    resultados: list[dict] = []
    for i, comando in enumerate(comandos):
        try:
            p = subprocess.run(  # sin shell: lista de argumentos
                comando, cwd=cwd, env=_entorno_limpio(home), capture_output=True, text=True,
                timeout=TIEMPO_MAXIMO_COMANDO_SEGUNDOS,
            )
            codigo, salida = p.returncode, p.stdout + p.stderr
        except subprocess.TimeoutExpired:
            codigo, salida = 124, f"tiempo máximo excedido ({TIEMPO_MAXIMO_COMANDO_SEGUNDOS}s)"
        except OSError as exc:
            codigo, salida = 127, f"no se pudo ejecutar: {exc}"
        resultados.append({"codigo_salida": codigo, "salida": salida[-SALIDA_MAXIMA_CARACTERES:]})
        if codigo != 0 and i != len(comandos) - 1:
            break
    return resultados


def main() -> int:
    url_entrada = os.environ["EMH_JOB_INPUT_URL"]
    url_salida = os.environ["EMH_JOB_OUTPUT_URL"]
    for var in [v for v in os.environ if v.startswith("EMH_")]:
        del os.environ[var]

    for u in (url_entrada, url_salida):
        if not u.startswith(("https://", "http://")):  # nunca file: ni otros esquemas
            raise ValueError("URL de trabajo con esquema no permitido")
    with urllib.request.urlopen(url_entrada, timeout=120) as resp:  # noqa: S310 -- URL prefirmada inyectada por la API
        contenido = resp.read()
    workspace, wheelhouse, home = Path("/workspace"), Path("/wheelhouse"), Path("/tmp")
    workspace.mkdir(parents=True, exist_ok=True)
    wheelhouse.mkdir(parents=True, exist_ok=True)
    comandos = extraer_trabajo(contenido, workspace, wheelhouse)
    resultados = ejecutar_comandos(comandos, workspace, home)

    peticion = urllib.request.Request(  # noqa: S310 -- URL prefirmada inyectada por la API
        url_salida, data=json.dumps({"resultados": resultados}).encode("utf-8"), method="PUT",
        headers={"Content-Type": "application/json"},  # el mismo que firmó la API
    )
    with urllib.request.urlopen(peticion, timeout=120):  # noqa: S310
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
