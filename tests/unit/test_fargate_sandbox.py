"""FargateSandbox contra un S3 y un ECS en memoria. `run_task` ejecuta el
ejecutor REAL (`sandbox/entrypoint.py`) sobre el tar que empaquetó la API,
así se verifica el contrato de los dos lados sin tocar AWS."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest

from emh.execution.fargate_sandbox import ErrorSandboxNube, FargateSandbox

_RUTA = Path(__file__).resolve().parents[2] / "sandbox" / "entrypoint.py"
_spec = importlib.util.spec_from_file_location("sandbox_entrypoint", _RUTA)
ep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ep)


class S3Falso:
    def __init__(self):
        self.objetos: dict[str, bytes] = {}
        self.borrados: list[str] = []

    def put_object(self, *, Bucket, Key, Body):
        self.objetos[Key] = Body

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objetos[Key])}  # KeyError si no existe

    def delete_object(self, *, Bucket, Key):
        self.borrados.append(Key)
        self.objetos.pop(Key, None)

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://s3.falso/{Params['Key']}?op={op}&exp={ExpiresIn}"


class EcsFalso:
    """`run_task` ejecuta el trabajo de verdad, en un directorio temporal."""

    def __init__(self, s3: S3Falso, tmp: Path, *, fallar_al_lanzar=False, sin_resultado=False, nunca_termina=False):
        self.s3, self.tmp = s3, tmp
        self.fallar_al_lanzar, self.sin_resultado, self.nunca_termina = fallar_al_lanzar, sin_resultado, nunca_termina
        self.detenidas: list[str] = []
        self.ultimo_run: dict = {}

    def run_task(self, **kw):
        self.ultimo_run = kw
        if self.fallar_al_lanzar:
            return {"tasks": [], "failures": [{"reason": "RESOURCE:FARGATE"}]}
        env = {e["name"]: e["value"] for e in kw["overrides"]["containerOverrides"][0]["environment"]}
        clave_in = env["EMH_JOB_INPUT_URL"].split("s3.falso/")[1].split("?")[0]
        clave_out = env["EMH_JOB_OUTPUT_URL"].split("s3.falso/")[1].split("?")[0]
        if not self.sin_resultado and not self.nunca_termina:
            ws, wh, home = self.tmp / "ws", self.tmp / "wh", self.tmp / "home"
            for d in (ws, wh, home):
                d.mkdir(exist_ok=True)
            comandos = ep.extraer_trabajo(self.s3.objetos[clave_in], ws, wh)
            import json

            self.s3.objetos[clave_out] = json.dumps({"resultados": ep.ejecutar_comandos(comandos, ws, home)}).encode()
        return {"tasks": [{"taskArn": "arn:tarea/1"}], "failures": []}

    def describe_tasks(self, *, cluster, tasks):
        return {"tasks": [{"lastStatus": "RUNNING" if self.nunca_termina else "STOPPED", "stoppedReason": "Essential container exited"}]}

    def stop_task(self, *, cluster, task, reason):
        self.detenidas.append(task)


def _sandbox(tmp_path, **kw):
    s3 = S3Falso()
    ecs = EcsFalso(s3, tmp_path / "nube", **kw)
    (tmp_path / "nube").mkdir()
    sb = FargateSandbox(
        cluster="c", task_definition="td", subredes=["subnet-1"], security_group="sg-1", bucket="b",
        s3=s3, ecs=ecs, intervalo=0, tiempo_maximo=1, dormir=lambda _s: None,
    )
    return sb, s3, ecs


def _workspace(tmp_path):
    ws = tmp_path / "workspace"
    (ws / "pkg").mkdir(parents=True)
    (ws / "pkg" / "a.py").write_text("VALOR = 42\n")
    (ws / ".git").mkdir()
    (ws / ".git" / "config").write_text("[remote]\n")
    (ws / "enlace").symlink_to("/etc/passwd")
    return ws


def test_ejecuta_la_secuencia_en_una_tarea_y_devuelve_resultados_reales(tmp_path):
    sb, s3, ecs = _sandbox(tmp_path)
    ws = _workspace(tmp_path)
    jid = sb.crear(ws)
    r = sb.ejecutar_secuencia(jid, [["python3", "-c", "import pkg.a as a; print(a.VALOR)"]], con_red=False)
    assert r[0].codigo_salida == 0
    assert "42" in r[0].salida


def test_no_sube_git_ni_enlaces_simbolicos(tmp_path):
    sb, s3, ecs = _sandbox(tmp_path)
    jid = sb.crear(_workspace(tmp_path))
    sb.ejecutar_secuencia(jid, [["echo", "x"]])
    import tarfile

    nombres = tarfile.open(fileobj=io.BytesIO(s3.objetos[f"jobs/{jid}/input.tgz"]), mode="r:gz").getnames()
    assert "workspace/pkg/a.py" in nombres
    assert not any(".git" in n for n in nombres)
    assert "workspace/enlace" not in nombres


def test_la_tarea_se_lanza_con_red_publica_pero_sin_credenciales_y_con_urls_prefirmadas(tmp_path):
    sb, s3, ecs = _sandbox(tmp_path)
    jid = sb.crear(_workspace(tmp_path))
    sb.ejecutar_secuencia(jid, [["echo", "x"]])
    kw = ecs.ultimo_run
    assert kw["launchType"] == "FARGATE" and kw["taskDefinition"] == "td"
    nombres_env = {e["name"] for e in kw["overrides"]["containerOverrides"][0]["environment"]}
    assert nombres_env == {"EMH_JOB_INPUT_URL", "EMH_JOB_OUTPUT_URL"}  # nada más: ni AWS_*, ni secretos


def test_secuencia_se_corta_si_un_paso_intermedio_falla(tmp_path):
    sb, *_ = _sandbox(tmp_path)
    jid = sb.crear(_workspace(tmp_path))
    r = sb.ejecutar_secuencia(jid, [["python3", "-c", "raise SystemExit(5)"], ["echo", "nunca"]])
    assert [x.codigo_salida for x in r] == [5]


def test_destruir_borra_los_objetos_y_detiene_la_tarea(tmp_path):
    sb, s3, ecs = _sandbox(tmp_path)
    jid = sb.crear(_workspace(tmp_path))
    sb.ejecutar_secuencia(jid, [["echo", "x"]])
    sb.destruir(jid)
    assert ecs.detenidas == ["arn:tarea/1"]
    assert not s3.objetos


def test_rechaza_red_extra(tmp_path):
    sb, *_ = _sandbox(tmp_path)
    jid = sb.crear(_workspace(tmp_path))
    with pytest.raises(ValueError):
        sb.ejecutar_secuencia(jid, [["echo", "x"]], con_red=True)


def test_error_claro_si_runtask_falla(tmp_path):
    sb, *_ = _sandbox(tmp_path, fallar_al_lanzar=True)
    jid = sb.crear(_workspace(tmp_path))
    with pytest.raises(ErrorSandboxNube, match="RunTask"):
        sb.ejecutar_secuencia(jid, [["echo", "x"]])


def test_error_claro_si_la_tarea_muere_sin_resultado(tmp_path):
    sb, *_ = _sandbox(tmp_path, sin_resultado=True)
    jid = sb.crear(_workspace(tmp_path))
    with pytest.raises(ErrorSandboxNube, match="sin resultado"):
        sb.ejecutar_secuencia(jid, [["echo", "x"]])


def test_si_la_tarea_excede_el_tiempo_se_detiene(tmp_path):
    sb, s3, ecs = _sandbox(tmp_path, nunca_termina=True)
    jid = sb.crear(_workspace(tmp_path))
    with pytest.raises(ErrorSandboxNube, match="excedió"):
        sb.ejecutar_secuencia(jid, [["echo", "x"]])
    assert ecs.detenidas
