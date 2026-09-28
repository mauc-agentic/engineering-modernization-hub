"""Las seis herramientas (DOCS/03-arquitectura.md §3.3). Cada una: valida
argumentos (control 1, ya en la frontera de `emh.agent`), consulta
`PolicyGate` DENTRO de la función, redacta su salida (control 6) y la marca
como contenido no confiable (RN-09) antes de devolverla al agente.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import urlopen

from emh.core.budget import PresupuestoMeter
from emh.core.models import DecisionAprobacion, EventoSeguridad, OrigenEvento, Plan, SeveridadEvento
from emh.core.ports import ResultadoComando, Sandbox
from emh.harness.contracts import (
    ArgsApplyPatch,
    ArgsCloneRepo,
    ArgsListFiles,
    ArgsReadFile,
    ArgsRunTests,
    ArgsSearchDocs,
    ResultadoHerramienta,
)
from emh.policy.gate import CambioArchivo, PolicyGate
from emh.policy.secrets import redactar

TAMANO_MAXIMO_ARCHIVO = 200_000  # bytes; evita saturar el contexto del modelo

# Ejecutor de comandos de host inyectable (clone_repo, apply_patch usan git).
# Por defecto, subprocess real, sin shell, lista de argumentos.
EjecutorHost = Callable[[list[str], Path], ResultadoComando]


def _ejecutor_host_real(comando: list[str], cwd: Path) -> ResultadoComando:
    proceso = subprocess.run(comando, cwd=cwd, capture_output=True, text=True, timeout=120)
    return ResultadoComando(codigo_salida=proceso.returncode, salida=proceso.stdout + proceso.stderr)


Fetcher = Callable[[str], str]


def _fetcher_real(url: str) -> str:
    with urlopen(url, timeout=15) as resp:  # noqa: S310 -- URL viene de un dominio ya en la allowlist
        return resp.read().decode("utf-8", errors="replace")


@dataclass
class ContextoHerramientas:
    workspace_root: Path
    gate: PolicyGate
    registrar_evento: Callable[[EventoSeguridad], None]
    plan_aprobado: Plan | None = None
    decision_aprobacion: DecisionAprobacion | None = None
    meter: PresupuestoMeter | None = None
    comandos_permitidos_estrategia: list[list[str]] = field(default_factory=list)
    dominios_fuente_permitidos: list[str] = field(default_factory=list)
    sandbox: Sandbox | None = None
    ejecutor_host: EjecutorHost = _ejecutor_host_real
    fetcher: Fetcher = _fetcher_real
    origen_id: int = 0  # ejecucion_id, para construir EventoSeguridad


def _denegar(ctx: ContextoHerramientas, regla: str, motivo: str, origen: OrigenEvento, detalles: list[str] | None = None) -> ResultadoHerramienta:
    ctx.registrar_evento(
        EventoSeguridad(
            ejecucion_id=ctx.origen_id, regla=regla, accion_intentada=motivo,
            origen=origen, severidad=SeveridadEvento.CRITICA,
        )
    )
    return ResultadoHerramienta(ok=False, motivo_rechazo=motivo, regla=regla, detalles=detalles or [])


# ---------------------------------------------------------------------------
# clone_repo
# ---------------------------------------------------------------------------


def clone_repo(ctx: ContextoHerramientas, args: ArgsCloneRepo) -> ResultadoHerramienta:
    parsed = urlparse(args.repositorio_url)
    if parsed.scheme != "https":
        return _denegar(
            ctx, "control_02_comandos_permitidos",
            f"clone_repo exige https, se recibió '{parsed.scheme}'", OrigenEvento.HERRAMIENTA,
        )

    comando = ["git", "clone", "--no-hardlinks", args.repositorio_url, str(ctx.workspace_root)]
    d = ctx.gate.verificar_comando(["git", "clone"], [["git", "clone"]])
    if not d.permitido:
        return _denegar(ctx, d.regla, d.motivo, OrigenEvento.HERRAMIENTA)

    resultado = ctx.ejecutor_host(comando, ctx.workspace_root.parent)
    if resultado.codigo_salida != 0:
        return ResultadoHerramienta(ok=False, motivo_rechazo="git clone falló", contenido=redactar(resultado.salida))

    checkout = ctx.ejecutor_host(
        ["git", "-C", str(ctx.workspace_root), "checkout", args.commit_referencia],
        ctx.workspace_root,
    )
    ok = checkout.codigo_salida == 0
    return ResultadoHerramienta(ok=ok, contenido=redactar(checkout.salida))


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------


def list_files(ctx: ContextoHerramientas, args: ArgsListFiles) -> ResultadoHerramienta:
    d = ctx.gate.verificar_confinamiento(args.ruta, ctx.workspace_root)
    if not d.permitido:
        return _denegar(ctx, d.regla, d.motivo, OrigenEvento.MODELO)

    objetivo = (ctx.workspace_root / args.ruta).resolve()
    if not objetivo.exists():
        return ResultadoHerramienta(ok=False, motivo_rechazo=f"'{args.ruta}' no existe")

    entradas = sorted(
        str(p.relative_to(ctx.workspace_root))
        for p in objetivo.rglob("*")
        if ".git" not in p.parts
    )
    return ResultadoHerramienta(ok=True, contenido="\n".join(entradas))


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


def read_file(ctx: ContextoHerramientas, args: ArgsReadFile) -> ResultadoHerramienta:
    d = ctx.gate.verificar_confinamiento(args.ruta, ctx.workspace_root)
    if not d.permitido:
        return _denegar(ctx, d.regla, d.motivo, OrigenEvento.MODELO)

    objetivo = (ctx.workspace_root / args.ruta).resolve()
    if not objetivo.is_file():
        return ResultadoHerramienta(ok=False, motivo_rechazo=f"'{args.ruta}' no es un archivo")
    if objetivo.stat().st_size > TAMANO_MAXIMO_ARCHIVO:
        return ResultadoHerramienta(ok=False, motivo_rechazo="archivo demasiado grande")

    texto = objetivo.read_text(encoding="utf-8", errors="replace")
    return ResultadoHerramienta(ok=True, contenido=redactar(texto), no_confiable=True)


# ---------------------------------------------------------------------------
# search_docs
# ---------------------------------------------------------------------------


def search_docs(ctx: ContextoHerramientas, args: ArgsSearchDocs) -> ResultadoHerramienta:
    if not any(args.dominio == dp or args.dominio.endswith("." + dp) for dp in ctx.dominios_fuente_permitidos):
        return _denegar(
            ctx, "control_02_comandos_permitidos",
            f"dominio '{args.dominio}' no está en las fuentes oficiales de la estrategia",
            OrigenEvento.MODELO,
        )

    url = f"https://{args.dominio}/{args.consulta.lstrip('/')}"
    try:
        contenido = ctx.fetcher(url)
    except Exception as exc:  # errores de red se devuelven como resultado, no excepción (RN-11)
        return ResultadoHerramienta(ok=False, motivo_rechazo=f"no se pudo consultar la fuente: {exc}")

    return ResultadoHerramienta(ok=True, contenido=redactar(contenido), no_confiable=True)


# ---------------------------------------------------------------------------
# apply_patch
# ---------------------------------------------------------------------------


def apply_patch(ctx: ContextoHerramientas, args: ArgsApplyPatch, *, operaciones_permitidas: list[str]) -> ResultadoHerramienta:
    d_aprobacion = ctx.gate.verificar_aprobacion(ctx.plan_aprobado, ctx.decision_aprobacion)
    if not d_aprobacion.permitido:
        return _denegar(ctx, d_aprobacion.regla, d_aprobacion.motivo, OrigenEvento.MODELO)

    cambios_policy = []
    for c in args.cambios:
        original = None
        ruta_abs = ctx.workspace_root / c.ruta
        if ruta_abs.is_file():
            original = ruta_abs.read_text(encoding="utf-8", errors="replace")
        cambios_policy.append(
            CambioArchivo(
                ruta=c.ruta, operacion=c.operacion,
                contenido_nuevo=c.contenido_nuevo, contenido_original=original,
            )
        )

    d = ctx.gate.validar_alcance_parche(
        cambios_policy, workspace_root=ctx.workspace_root,
        rutas_declaradas=ctx.plan_aprobado.rutas_declaradas if ctx.plan_aprobado else [],
        operaciones_permitidas=operaciones_permitidas,
    )
    if not d.permitido:
        return _denegar(ctx, d.regla, d.motivo, OrigenEvento.MODELO, detalles=d.detalles)

    for c in args.cambios:
        ruta_abs = ctx.workspace_root / c.ruta
        if c.operacion == "borrar":
            ruta_abs.unlink(missing_ok=True)
        else:
            ruta_abs.parent.mkdir(parents=True, exist_ok=True)
            ruta_abs.write_text(c.contenido_nuevo or "", encoding="utf-8")

    return ResultadoHerramienta(ok=True, contenido=f"{len(args.cambios)} archivo(s) modificado(s)", no_confiable=False)


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------


def run_tests(ctx: ContextoHerramientas, args: ArgsRunTests) -> ResultadoHerramienta:
    d = ctx.gate.verificar_comando(args.comando, ctx.comandos_permitidos_estrategia)
    if not d.permitido:
        return _denegar(ctx, d.regla, d.motivo, OrigenEvento.MODELO)

    if ctx.sandbox is None:
        return ResultadoHerramienta(ok=False, motivo_rechazo="no hay sandbox configurado")

    contenedor_id = ctx.sandbox.crear(ctx.workspace_root)
    try:
        resultado = ctx.sandbox.ejecutar(contenedor_id, args.comando, con_red=False)
    finally:
        ctx.sandbox.destruir(contenedor_id)

    return ResultadoHerramienta(
        ok=True, contenido=redactar(resultado.salida), no_confiable=True,
        detalles=[str(resultado.codigo_salida)],
    )


HERRAMIENTAS_REGISTRADAS: frozenset[str] = frozenset(
    {"clone_repo", "list_files", "read_file", "search_docs", "apply_patch", "run_tests"}
)
