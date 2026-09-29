"""Adaptador de nube de `Sandbox` (ADR-006, `EMH_ENV=aws`): una tarea Fargate
efímera por verificación, sin permisos IAM.

Como el rol de la tarea del sandbox está vacío a propósito (NFR-004), no hay
`ecs execute-command` ni acceso a S3 por rol: el intercambio va por dos URLs
prefirmadas de un solo objeto (entrada GET, salida PUT) que caducan en minutos.
La API empaqueta workspace + wheelhouse + comandos en un tar, lanza la tarea
con `RunTask`, espera a que termine y lee el resultado. El contrato del lado
del contenedor está en `sandbox/entrypoint.py`.
"""

from __future__ import annotations

import io
import json
import tarfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from emh.core.ports import ResultadoComando

CADUCIDAD_URL_SEGUNDOS = 1800
TIPO_CONTENIDO_RESULTADO = "application/json"  # firmado en la URL; el ejecutor debe enviarlo igual
TIEMPO_MAXIMO_TAREA_SEGUNDOS = 900
INTERVALO_SONDEO_SEGUNDOS = 5


class ErrorSandboxNube(Exception):
    """La tarea no pudo lanzarse, falló al arrancar o no dejó resultado."""


@dataclass
class _Trabajo:
    workspace: Path
    wheelhouse: Path | None
    task_arn: str | None = None


class FargateSandbox:
    def __init__(
        self,
        *,
        cluster: str,
        task_definition: str,
        subredes: list[str],
        security_group: str,
        bucket: str,
        region: str | None = None,
        s3=None,
        ecs=None,
        tiempo_maximo: int = TIEMPO_MAXIMO_TAREA_SEGUNDOS,
        intervalo: float = INTERVALO_SONDEO_SEGUNDOS,
        dormir=time.sleep,
    ) -> None:
        if s3 is None or ecs is None:
            import boto3
            from botocore.config import Config

            # SigV4 explícito: sin él boto3 puede firmar con SigV2, donde el
            # Content-Type del PUT entra en la firma y S3 responde 403 (hallazgo
            # en el primer despliegue real, #13).
            s3 = s3 or boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))
            ecs = ecs or boto3.client("ecs", region_name=region)
        self._s3, self._ecs = s3, ecs
        self._cluster, self._task_definition = cluster, task_definition
        self._subredes, self._sg, self._bucket = subredes, security_group, bucket
        self._tiempo_maximo, self._intervalo, self._dormir = tiempo_maximo, intervalo, dormir
        self._trabajos: dict[str, _Trabajo] = {}

    # -- Puerto Sandbox ---------------------------------------------------------

    def crear(self, workspace: Path, *, wheelhouse: Path | None = None) -> str:
        trabajo_id = uuid.uuid4().hex
        self._trabajos[trabajo_id] = _Trabajo(workspace=workspace, wheelhouse=wheelhouse)
        return trabajo_id

    def ejecutar(self, identificador: str, comando: list[str], *, con_red: bool = False) -> ResultadoComando:
        return self.ejecutar_secuencia(identificador, [comando], con_red=con_red)[0]

    def ejecutar_secuencia(
        self, identificador: str, comandos: list[list[str]], *, con_red: bool = False
    ) -> list[ResultadoComando]:
        """Toda la secuencia va en UNA tarea: el venv que crea el primer
        comando tiene que seguir ahí para el último (como el contenedor único
        del adaptador local)."""
        if con_red:
            raise ValueError("FargateSandbox nunca habilita red adicional (ADR-005, decisión D-6)")
        trabajo = self._trabajos[identificador]
        clave_in, clave_out = f"jobs/{identificador}/input.tgz", f"jobs/{identificador}/output.json"

        self._s3.put_object(Bucket=self._bucket, Key=clave_in, Body=self._empaquetar(trabajo, comandos))
        url_in = self._s3.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": clave_in}, ExpiresIn=CADUCIDAD_URL_SEGUNDOS
        )
        url_out = self._s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": clave_out, "ContentType": TIPO_CONTENIDO_RESULTADO},
            ExpiresIn=CADUCIDAD_URL_SEGUNDOS,
        )

        resp = self._ecs.run_task(
            cluster=self._cluster, taskDefinition=self._task_definition, launchType="FARGATE",
            networkConfiguration={"awsvpcConfiguration": {
                "subnets": self._subredes, "securityGroups": [self._sg], "assignPublicIp": "ENABLED",
            }},
            overrides={"containerOverrides": [{
                "name": "sandbox",
                "environment": [
                    {"name": "EMH_JOB_INPUT_URL", "value": url_in},
                    {"name": "EMH_JOB_OUTPUT_URL", "value": url_out},
                ],
            }]},
        )
        if resp.get("failures") or not resp.get("tasks"):
            raise ErrorSandboxNube(f"RunTask falló: {resp.get('failures')}")
        trabajo.task_arn = resp["tasks"][0]["taskArn"]

        self._esperar(trabajo.task_arn)
        try:
            cuerpo = self._s3.get_object(Bucket=self._bucket, Key=clave_out)["Body"].read()
        except Exception as exc:
            raise ErrorSandboxNube(f"la tarea terminó sin resultado ({self._motivo_parada(trabajo.task_arn)})") from exc
        return [
            ResultadoComando(codigo_salida=r["codigo_salida"], salida=r["salida"])
            for r in json.loads(cuerpo)["resultados"]
        ]

    def destruir(self, identificador: str) -> None:
        trabajo = self._trabajos.pop(identificador, None)
        if trabajo is not None and trabajo.task_arn:
            try:
                self._ecs.stop_task(cluster=self._cluster, task=trabajo.task_arn, reason="verificación terminada")
            except Exception:  # noqa: BLE001, S110 -- ya había terminado
                pass
        for clave in ("input.tgz", "output.json"):
            try:
                self._s3.delete_object(Bucket=self._bucket, Key=f"jobs/{identificador}/{clave}")
            except Exception:  # noqa: BLE001, S110 -- el bucket además expira objetos solo
                pass

    # -- Internos ---------------------------------------------------------------

    @staticmethod
    def _empaquetar(trabajo: _Trabajo, comandos: list[list[str]]) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for raiz, prefijo in ((trabajo.workspace, "workspace"), (trabajo.wheelhouse, "wheelhouse")):
                if raiz is None:
                    continue
                for ruta in sorted(raiz.rglob("*")):
                    if ruta.is_symlink() or ".git" in ruta.relative_to(raiz).parts:
                        continue  # sin enlaces (no pueden apuntar fuera) y sin historial git
                    tar.add(ruta, arcname=f"{prefijo}/{ruta.relative_to(raiz)}", recursive=False)
            datos = json.dumps({"comandos": comandos}).encode("utf-8")
            info = tarfile.TarInfo("job.json")
            info.size = len(datos)
            tar.addfile(info, io.BytesIO(datos))
        return buf.getvalue()

    def _esperar(self, task_arn: str) -> None:
        limite = time.monotonic() + self._tiempo_maximo
        while time.monotonic() < limite:
            tareas = self._ecs.describe_tasks(cluster=self._cluster, tasks=[task_arn])["tasks"]
            if tareas and tareas[0]["lastStatus"] == "STOPPED":
                return
            self._dormir(self._intervalo)
        try:
            self._ecs.stop_task(cluster=self._cluster, task=task_arn, reason="tiempo máximo excedido")
        finally:
            raise ErrorSandboxNube(f"la tarea excedió {self._tiempo_maximo}s y se detuvo")

    def _motivo_parada(self, task_arn: str) -> str:
        try:
            t = self._ecs.describe_tasks(cluster=self._cluster, tasks=[task_arn])["tasks"][0]
            return t.get("stoppedReason") or "sin motivo"
        except Exception:  # noqa: BLE001
            return "motivo desconocido"
