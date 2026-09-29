"""Las seis herramientas (DOCS/03-arquitectura.md §3.3). Cada una: valida
argumentos (control 1, ya en la frontera de `emh.agent`), consulta
`PolicyGate` DENTRO de la función, redacta su salida (control 6) y la marca
como contenido no confiable (RN-09) antes de devolverla al agente.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from emh.core.budget import PresupuestoMeter
from emh.core.models import (
    DecisionAprobacion,
    EventoSeguridad,
    Fuente,
    OrigenEvento,
    Plan,
    SeveridadEvento,
)
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


MAX_CARACTERES_FUENTE = 20_000  # una fuente entera (p. ej. un CHANGES.rst de 600 KB) agotaría el contexto


def _fetcher_real(url: str) -> str:
    # Bundle de certifi: el Python de python.org en macOS no trae CAs y toda
    # consulta a fuentes oficiales fallaba con CERTIFICATE_VERIFY_FAILED
    # (hallazgo en vivo #10). La verificación TLS sigue activa.
    import ssl

    import certifi

    if not url.startswith("https://"):  # nunca file: ni otros esquemas (el dominio ya viene validado por la política)
        raise ValueError("solo se consultan fuentes por HTTPS")
    contexto = ssl.create_default_context(cafile=certifi.where())
    with urlopen(url, timeout=15, context=contexto) as resp:  # noqa: S310 -- esquema https comprobado arriba
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
    tipos_fuente_por_dominio: dict[str, str] = field(default_factory=dict)
    registrar_fuente: Callable[[Fuente], Fuente] | None = None
    sandbox: Sandbox | None = None
    ejecutor_host: EjecutorHost = _ejecutor_host_real
    fetcher: Fetcher = _fetcher_real
    origen_id: int = 0  # ejecucion_id, para construir EventoSeguridad
    wheelhouse_dir: Path | None = None  # ADR-005/D-6: ruedas ya descargadas en el host


def _denegar(ctx: ContextoHerramientas, regla: str, motivo: str, origen: OrigenEvento, detalles: list[str] | None = None) -> ResultadoHerramienta:
    # NFR-013: el evento persistido lleva el detalle completo (qué ruta u
    # operación se intentó), no solo el motivo genérico -- si no, el reporte
    # y la auditoría no pueden distinguir un intento de otro.
    accion = motivo if not detalles else f"{motivo}: " + "; ".join(detalles)
    ctx.registrar_evento(
        EventoSeguridad(
            ejecucion_id=ctx.origen_id, regla=regla, accion_intentada=accion,
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

    raiz = ctx.workspace_root.resolve()  # macOS: /var/... es symlink a /private/var/...;
    objetivo = (raiz / args.ruta).resolve()  # sin resolver ambos lados, relative_to() falla
    if not objetivo.exists():
        return ResultadoHerramienta(ok=False, motivo_rechazo=f"'{args.ruta}' no existe")

    entradas = sorted(
        str(p.relative_to(raiz))
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


def _dominio_pelado(valor: str) -> str:
    """Normaliza lo que el modelo mande como 'dominio' -- en la primera
    ejecución en vivo el modelo propuso 'https://pyyaml.org' en vez de
    'pyyaml.org'. Se acepta cualquiera de las dos formas; el chequeo de
    permiso sigue siendo exacto contra el dominio ya pelado (no se afloja
    la allowlist, solo se interpreta correctamente el argumento)."""
    # Sin esquema ("github.com/pyyaml") el host es el primer segmento; el
    # permiso sigue siendo exacto contra el host, nunca contra el path.
    return urlparse(valor).netloc or valor.strip().split("/")[0]


def _registrar_fuente(ctx: ContextoHerramientas, dominio: str, url: str, contenido: str) -> None:
    """Trazabilidad (AC-08): toda consulta exitosa queda persistida con el
    hash de lo que se leyó, para que el reporte cite las fuentes usadas."""
    if ctx.registrar_fuente is None:
        return
    import hashlib

    tipo = next(
        (t for d, t in ctx.tipos_fuente_por_dominio.items() if dominio == d or dominio.endswith("." + d)),
        "DOCUMENTACION_OFICIAL",
    )
    ctx.registrar_fuente(Fuente(
        ejecucion_id=ctx.origen_id, tipo=tipo, url=url[:500],
        hash_contenido=hashlib.sha256(contenido.encode("utf-8", errors="replace")).hexdigest(),
        resumen=redactar(contenido[:500]),
    ))


def search_docs(ctx: ContextoHerramientas, args: ArgsSearchDocs) -> ResultadoHerramienta:
    dominio = _dominio_pelado(args.dominio)
    if not any(dominio == dp or dominio.endswith("." + dp) for dp in ctx.dominios_fuente_permitidos):
        return _denegar(
            ctx, "control_02_comandos_permitidos",
            f"dominio '{args.dominio}' no está en las fuentes oficiales de la estrategia",
            OrigenEvento.MODELO,
        )

    url = f"https://{dominio}/{args.consulta.lstrip('/')}"
    try:
        contenido = ctx.fetcher(url)
    except Exception as exc:  # errores de red se devuelven como resultado, no excepción (RN-11)
        return ResultadoHerramienta(ok=False, motivo_rechazo=f"no se pudo consultar la fuente: {exc}")

    _registrar_fuente(ctx, dominio, url, contenido)
    if len(contenido) > MAX_CARACTERES_FUENTE:
        contenido = contenido[:MAX_CARACTERES_FUENTE] + f"\n[... truncado: {len(contenido)} caracteres en total]"
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
    """Ejecuta TODA la secuencia (instalación + verificación) en UN solo
    contenedor efímero -- el venv que crea el primer comando (NFR-004: raíz
    de solo lectura, venv en /tmp) tiene que seguir ahí para el último."""
    for comando in args.comandos:
        d = ctx.gate.verificar_comando(comando, ctx.comandos_permitidos_estrategia)
        if not d.permitido:
            return _denegar(ctx, d.regla, d.motivo, OrigenEvento.MODELO)

    if ctx.sandbox is None:
        return ResultadoHerramienta(ok=False, motivo_rechazo="no hay sandbox configurado")

    kwargs_crear = {"wheelhouse": ctx.wheelhouse_dir} if ctx.wheelhouse_dir is not None else {}
    contenedor_id = ctx.sandbox.crear(ctx.workspace_root, **kwargs_crear)
    try:
        bloques: list[str] = []
        codigo_final = 0
        secuencia = getattr(ctx.sandbox, "ejecutar_secuencia", None)
        if secuencia is not None:
            resultados = secuencia(contenedor_id, args.comandos, con_red=False)
        else:  # dobles de prueba que solo implementan `ejecutar`
            resultados = []
            for i, comando in enumerate(args.comandos):
                resultado = ctx.sandbox.ejecutar(contenedor_id, comando, con_red=False)
                resultados.append(resultado)
                if resultado.codigo_salida != 0 and i != len(args.comandos) - 1:
                    # un paso de instalación falló: no tiene sentido seguir con
                    # el resto de la secuencia (RN-11: se informa, no se cuelga)
                    break
        for comando, resultado in zip(args.comandos, resultados, strict=False):  # la secuencia puede cortarse antes
            bloques.append(f"$ {' '.join(comando)}\n{resultado.salida}")
            codigo_final = resultado.codigo_salida
    finally:
        ctx.sandbox.destruir(contenedor_id)

    return ResultadoHerramienta(
        ok=True, contenido=redactar("\n".join(bloques)), no_confiable=True,
        detalles=[str(codigo_final)],
    )


HERRAMIENTAS_REGISTRADAS: frozenset[str] = frozenset(
    {"clone_repo", "list_files", "read_file", "search_docs", "apply_patch", "run_tests"}
)
