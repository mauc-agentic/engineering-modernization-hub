"""Adaptador local de `Sandbox` (ADR-005): un contenedor Docker efímero por
ejecución, endurecido, sin red durante `run_tests` (decisión D-6: el
*wheelhouse* ya resolvió las dependencias en el host, así que el contenedor
nunca necesita red, ni siquiera en la fase de instalación).
"""

from __future__ import annotations

from pathlib import Path

import docker
from docker.errors import NotFound

from emh.core.ports import ResultadoComando

IMAGEN_BASE_DEFECTO = "python:3.12-slim"


class DockerSandbox:
    """Implementa `emh.core.ports.Sandbox`. NFR-004: sin privilegios, usuario
    no root, sistema de archivos raíz de solo lectura salvo el workspace,
    límites de CPU/memoria, destrucción ≤ 10 s tras terminar."""

    def __init__(
        self,
        imagen: str = IMAGEN_BASE_DEFECTO,
        cpu_nanos: int = 2_000_000_000,
        memoria: str = "2g",
    ) -> None:
        self._cliente = docker.from_env()
        self._imagen = imagen
        self._cpu_nanos = cpu_nanos
        self._memoria = memoria

    def crear(self, workspace: Path, *, wheelhouse: Path | None = None) -> str:
        volumenes = {str(workspace.resolve()): {"bind": "/workspace", "mode": "rw"}}
        if wheelhouse is not None:
            volumenes[str(wheelhouse.resolve())] = {"bind": "/wheelhouse", "mode": "ro"}

        contenedor = self._cliente.containers.run(
            self._imagen,
            command=["sleep", "infinity"],
            volumes=volumenes,
            working_dir="/workspace",
            user="1000:1000",  # NFR-004: usuario no root
            read_only=True,  # NFR-004: raíz de solo lectura salvo el workspace
            tmpfs={"/tmp": "rw,size=256m"},
            network_disabled=True,  # ADR-005/D-6: nunca hay red en el sandbox
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            nano_cpus=self._cpu_nanos,
            mem_limit=self._memoria,
            detach=True,
            remove=False,
        )
        return contenedor.id

    def ejecutar(self, identificador: str, comando: list[str], *, con_red: bool = False) -> ResultadoComando:
        if con_red:
            raise ValueError(
                "DockerSandbox nunca permite red durante la ejecución (ADR-005, decisión D-6)"
            )
        contenedor = self._cliente.containers.get(identificador)
        salida = contenedor.exec_run(comando, workdir="/workspace", user="1000:1000")
        return ResultadoComando(
            codigo_salida=salida.exit_code, salida=salida.output.decode("utf-8", errors="replace")
        )

    def destruir(self, identificador: str) -> None:
        try:
            contenedor = self._cliente.containers.get(identificador)
            contenedor.stop(timeout=5)
            contenedor.remove(force=True)
        except NotFound:
            pass
