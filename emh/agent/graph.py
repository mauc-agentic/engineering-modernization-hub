"""El grafo agéntico (DOCS/03-arquitectura.md §4). Implementa `AgentRunner`.

Principio: el modelo propone, el código dispone. Cada nodo que produce un
efecto pasa por `emh.harness` -> `emh.policy`. La máquina de estados del
núcleo (`emh.core.state_machine`) es la fuente de verdad del estado de
negocio; este grafo lleva memoria de trabajo (mensajes) y decide el próximo
paso, pero nunca decide por sí mismo si algo está permitido.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from emh.core.budget import PresupuestoMeter
from emh.core.errors import PresupuestoAgotado
from emh.core.models import (
    AnalisisViabilidad,
    DecisionTecnica,
    Ejecucion,
    EstadoEjecucion,
    EstadoPlan,
    MotivoBloqueo,
    Plan,
    ResultadoEjecucion,
    ResultadoVerificacion,
    TipoDecisionTecnica,
    Verificacion,
)
from emh.core.ports import ModelPort, RunRepository, Sandbox
from emh.core.state_machine import transicionar
from emh.agent.runtime import ContextoAgente, ErrorSalidaModelo, bucle_exploracion, pedir_estructurado
from emh.agent import prompts
from emh.harness.contracts import ArgsApplyPatch, ArgsRunTests, CambioArchivoArgs
from emh.harness.tools import ContextoHerramientas, EjecutorHost, Fetcher, _ejecutor_host_real, _fetcher_real
from emh.harness.tools import apply_patch as fn_apply_patch
from emh.harness.tools import run_tests as fn_run_tests
from emh.policy.gate import PolicyGate
from emh.strategies.registry import obtener_estrategia

MAX_INTENTOS_VALIDACION_ALCANCE = 3  # reparación de propuestas fuera de alcance (control 7)


class EstadoGrafo(TypedDict):
    ejecucion_id: int
    mensajes: list[dict[str, Any]]


@dataclass
class Entorno:
    """Lo que no cambia entre ejecuciones concurrentes: adaptadores. Todo lo
    que sí cambia por ejecución (plan vigente, presupuesto consumido...) se
    reconstruye desde `repo` en cada nodo -- ninguna capa de caché en
    memoria que pudiera desincronizarse entre reanudaciones (NFR-020)."""

    repo: RunRepository
    modelo: ModelPort
    gate: PolicyGate
    sandbox: Sandbox
    workspace_root_para: Callable[[int], Path]
    ejecutor_host: EjecutorHost = _ejecutor_host_real
    fetcher: Fetcher = _fetcher_real
    max_turnos_exploracion: int = 6


def _construir_meter(entorno: Entorno, solicitud, ejecucion: Ejecucion) -> PresupuestoMeter:
    llamadas = entorno.repo.listar_llamadas_modelo(ejecucion.id)
    return PresupuestoMeter(
        solicitud,
        momento_inicio=ejecucion.iniciado_en,
        tokens_ya_consumidos=(sum(l.tokens_entrada for l in llamadas), sum(l.tokens_salida for l in llamadas)),
        iteraciones_ya_usadas=ejecucion.iteraciones_usadas,
    )


def _construir_contexto(entorno: Entorno, ejecucion_id: int) -> ContextoAgente:
    ejecucion = entorno.repo.obtener_ejecucion(ejecucion_id)
    solicitud = entorno.repo.obtener_solicitud(ejecucion.solicitud_id)
    estrategia = obtener_estrategia(solicitud.estrategia_id)
    if estrategia is None:
        raise ErrorSalidaModelo(f"estrategia '{solicitud.estrategia_id}' no está registrada")

    meter = _construir_meter(entorno, solicitud, ejecucion)
    workspace = entorno.workspace_root_para(ejecucion_id)
    plan_aprobado = entorno.repo.obtener_plan_vigente(ejecucion_id)
    decision = entorno.repo.obtener_decision_aprobacion_vigente(plan_aprobado.id) if plan_aprobado else None

    perfil = estrategia.command_profile()
    fuentes_decl = estrategia.official_sources(solicitud)

    herramientas_ctx = ContextoHerramientas(
        workspace_root=workspace,
        gate=entorno.gate,
        registrar_evento=entorno.repo.guardar_evento_seguridad,
        plan_aprobado=plan_aprobado,
        decision_aprobacion=decision,
        meter=meter,
        comandos_permitidos_estrategia=perfil.instalacion + perfil.verificacion,
        dominios_fuente_permitidos=[f.dominio for f in fuentes_decl],
        sandbox=entorno.sandbox,
        ejecutor_host=entorno.ejecutor_host,
        fetcher=entorno.fetcher,
        origen_id=ejecucion_id,
    )
    return ContextoAgente(
        ejecucion_id=ejecucion_id, modelo=entorno.modelo, meter=meter, repo=entorno.repo,
        gate=entorno.gate, herramientas_ctx=herramientas_ctx, estrategia=estrategia,
        max_turnos_exploracion=entorno.max_turnos_exploracion,
    )


def _avanzar(entorno: Entorno, ejecucion_id: int, nuevo_estado: EstadoEjecucion, **kw) -> Ejecucion:
    ejecucion = entorno.repo.obtener_ejecucion(ejecucion_id)
    if ejecucion.estado is EstadoEjecucion.FINALIZADA:
        # Idempotente a propósito (RN-11): los bordes del grafo entre nodos
        # son en su mayoría incondicionales; un nodo anterior pudo haber
        # finalizado la ejecución (p. ej. PresupuestoAgotado) y el siguiente
        # nodo se ejecuta igual. FINALIZADA es terminal -- reintentar la
        # transición no debe lanzar TransicionIlegal, solo no hacer nada.
        return ejecucion
    nueva = transicionar(ejecucion, nuevo_estado, **kw)
    return entorno.repo.actualizar_ejecucion(nueva)


def _finalizar(entorno: Entorno, ejecucion_id: int, resultado: ResultadoEjecucion, motivo: MotivoBloqueo | None = None) -> None:
    _avanzar(entorno, ejecucion_id, EstadoEjecucion.FINALIZADA, resultado=resultado, motivo_bloqueo=motivo)


def _hash_plan(pasos: list[str], rutas: list[str], comandos: list[list[str]]) -> str:
    payload = json.dumps({"pasos": pasos, "rutas": rutas, "comandos": comandos}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def construir_grafo(entorno: Entorno):
    """Compila el grafo. Cada nodo es un closure sobre `entorno`; el estado
    de negocio real vive en `entorno.repo`, no en el estado de LangGraph."""

    def nodo_interpretar_solicitud(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ejecucion = entorno.repo.obtener_ejecucion(ejecucion_id)
        solicitud = entorno.repo.obtener_solicitud(ejecucion.solicitud_id)
        ctx = _construir_contexto(entorno, ejecucion_id)
        try:
            resultado = pedir_estructurado(
                ctx, "interpretar_solicitud",
                sistema=prompts.BASE + "\n\nFase: interpretar la solicitud. Normaliza el objetivo en una frase clara.",
                mensajes=[{"role": "user", "content": [{"text": (
                    f"Repositorio: {solicitud.repositorio_url}\nObjetivo: {solicitud.objetivo}\n"
                    f"Versión esperada: {solicitud.version_esperada}\n"
                    f"Restricciones: {solicitud.restricciones or '(ninguna)'}"
                )}]}],
                nombre_tool="objetivo_interpretado",
                descripcion_tool="Entrega el objetivo normalizado",
                json_schema={"type": "object", "properties": {"objetivo_normalizado": {"type": "string"}}, "required": ["objetivo_normalizado"]},
            )
        except PresupuestoAgotado:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.PRESUPUESTO_AGOTADO)
            return estado
        except ErrorSalidaModelo:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.FALLIDO_CONTROLADO)
            return estado

        mensajes = estado["mensajes"] + [
            {"role": "user", "content": [{"text": f"Objetivo normalizado: {resultado.get('objetivo_normalizado', solicitud.objetivo)}"}]}
        ]
        return {"ejecucion_id": ejecucion_id, "mensajes": mensajes}

    def nodo_descubrir_repo(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ctx = _construir_contexto(entorno, ejecucion_id)

        # Clonar es mecánico (repo/commit ya vienen en la Solicitud), no una
        # decisión del modelo (08-uso-de-ia.md empieza en "explorar el
        # repositorio", no en "clonarlo"). Idempotente: si ya hay contenido
        # en el workspace (reanudación tras interrupción), no se reclona.
        workspace = ctx.herramientas_ctx.workspace_root
        if not workspace.exists() or not any(workspace.iterdir()):
            ejecucion = entorno.repo.obtener_ejecucion(ejecucion_id)
            solicitud = entorno.repo.obtener_solicitud(ejecucion.solicitud_id)
            workspace.mkdir(parents=True, exist_ok=True)
            from emh.harness.contracts import ArgsCloneRepo
            from emh.harness.tools import clone_repo as fn_clone_repo

            r_clone = fn_clone_repo(
                ctx.herramientas_ctx,
                ArgsCloneRepo(repositorio_url=solicitud.repositorio_url, commit_referencia=solicitud.commit_referencia),
            )
            if not r_clone.ok:
                _finalizar(entorno, ejecucion_id, ResultadoEjecucion.FALLIDO_CONTROLADO)
                return estado

        try:
            historial, resumen = bucle_exploracion(
                ctx, "descubrir_repo", sistema=prompts.DESCUBRIR_REPO,
                mensajes=estado["mensajes"], herramientas_permitidas=["list_files", "read_file"],
            )
        except PresupuestoAgotado:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.PRESUPUESTO_AGOTADO)
            return estado
        return {"ejecucion_id": ejecucion_id, "mensajes": historial}

    def nodo_consultar_fuentes(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ctx = _construir_contexto(entorno, ejecucion_id)
        try:
            historial, resumen = bucle_exploracion(
                ctx, "consultar_fuentes", sistema=prompts.CONSULTAR_FUENTES,
                mensajes=estado["mensajes"], herramientas_permitidas=["search_docs"],
            )
        except PresupuestoAgotado:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.PRESUPUESTO_AGOTADO)
            return estado
        _avanzar(entorno, ejecucion_id, EstadoEjecucion.ANALISIS)
        return {"ejecucion_id": ejecucion_id, "mensajes": historial}

    def nodo_evaluar_viabilidad(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ctx = _construir_contexto(entorno, ejecucion_id)
        try:
            resultado = pedir_estructurado(
                ctx, "evaluar_viabilidad", sistema=prompts.ANALIZAR_IMPACTO_Y_VIABILIDAD,
                mensajes=estado["mensajes"], nombre_tool="veredicto_viabilidad",
                descripcion_tool="Entrega el veredicto de viabilidad",
                json_schema={
                    "type": "object",
                    "properties": {
                        "veredicto": {"type": "string", "enum": ["VIABLE", "INVIABLE"]},
                        "impacto_detectado": {"type": "string"},
                        "evidencia": {"type": "string"},
                    },
                    "required": ["veredicto", "impacto_detectado", "evidencia"],
                },
                nivel_esfuerzo="high",
            )
        except PresupuestoAgotado:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.PRESUPUESTO_AGOTADO)
            return estado
        except ErrorSalidaModelo:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.FALLIDO_CONTROLADO)
            return estado

        analisis = AnalisisViabilidad(
            ejecucion_id=ejecucion_id, veredicto=resultado["veredicto"],
            impacto_detectado=resultado["impacto_detectado"][:4000], evidencia=resultado["evidencia"][:4000],
        )
        entorno.repo.guardar_analisis_viabilidad(analisis)
        entorno.repo.guardar_decision_tecnica(
            DecisionTecnica(
                ejecucion_id=ejecucion_id, tipo=TipoDecisionTecnica.VIABILIDAD,
                descripcion=resultado["impacto_detectado"][:2000], sustentada=True,
            )
        )
        mensajes = estado["mensajes"] + [
            {"role": "user", "content": [{"text": f"Veredicto de viabilidad: {resultado['veredicto']}"}]}
        ]
        return {"ejecucion_id": ejecucion_id, "mensajes": mensajes}

    def _ruta_tras_viabilidad(estado: EstadoGrafo) -> Literal["proponer_plan", "construir_reporte", "fin_directo"]:
        ejecucion = entorno.repo.obtener_ejecucion(estado["ejecucion_id"])
        if ejecucion.resultado is not None:  # ya se finalizó (presupuesto/error)
            return "fin_directo"
        analisis = entorno.repo.obtener_analisis_viabilidad(estado["ejecucion_id"])
        if analisis is None or analisis.veredicto.value == "INVIABLE":
            _finalizar(entorno, estado["ejecucion_id"], ResultadoEjecucion.BLOQUEADO, MotivoBloqueo.INVIABLE)
            return "construir_reporte"
        _avanzar(entorno, estado["ejecucion_id"], EstadoEjecucion.PLANEACION)
        return "proponer_plan"

    def nodo_proponer_plan(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ctx = _construir_contexto(entorno, ejecucion_id)
        plantilla = ctx.estrategia.scope_template()
        try:
            resultado = pedir_estructurado(
                ctx, "proponer_plan", sistema=prompts.PROPONER_PLAN,
                mensajes=estado["mensajes"] + [{
                    "role": "user",
                    "content": [{"text": f"Rutas permitidas por la estrategia: {plantilla.rutas}. Operaciones permitidas: {plantilla.operaciones}."}],
                }],
                nombre_tool="plan_propuesto", descripcion_tool="Entrega el plan de modernización",
                json_schema={
                    "type": "object",
                    "properties": {
                        "pasos": {"type": "array", "items": {"type": "string"}},
                        "rutas_declaradas": {"type": "array", "items": {"type": "string"}},
                        "riesgos": {"type": "string"},
                    },
                    "required": ["pasos", "rutas_declaradas"],
                },
                nivel_esfuerzo="high",
            )
        except PresupuestoAgotado:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.PRESUPUESTO_AGOTADO)
            return estado
        except ErrorSalidaModelo:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.FALLIDO_CONTROLADO)
            return estado

        # Las rutas del plan quedan confinadas a lo que la estrategia autoriza
        # (06-estrategias.md): el manifiesto siempre entra; los módulos que
        # el modelo declara afectados por el cambio (además del manifiesto)
        # se registran explícitamente vía plan_hint, y son EXACTAMENTE lo
        # que queda en rutas_declaradas -- nada añadido fuera de ese conjunto.
        # Esto NO es el control 7 (que valida el parche final aplicado);
        # es la plantilla acotando la PROPUESTA. El límite de seguridad real
        # es la aprobación humana (RN-01) más el control 7 sobre el parche.
        modulos_declarados = [r for r in resultado["rutas_declaradas"] if r not in plantilla.rutas]
        plantilla = ctx.estrategia.scope_template({"modulos_afectados": modulos_declarados})
        rutas = [r for r in resultado["rutas_declaradas"] if r in plantilla.rutas] or plantilla.rutas
        comandos_verif = ctx.estrategia.command_profile().verificacion
        version = len(entorno.repo.listar_planes(ejecucion_id)) + 1
        plan_hash = _hash_plan(resultado["pasos"], rutas, comandos_verif)
        plan = entorno.repo.guardar_plan(
            Plan(
                ejecucion_id=ejecucion_id, version=version, hash=plan_hash,
                pasos=resultado["pasos"], rutas_declaradas=rutas, comandos_verificacion=comandos_verif,
                riesgos=resultado.get("riesgos"), estado=EstadoPlan.PROPUESTO,
            )
        )
        mensajes = estado["mensajes"] + [
            {"role": "user", "content": [{"text": f"Plan propuesto (hash {plan.hash[:8]}): {resultado['pasos']}"}]}
        ]
        return {"ejecucion_id": ejecucion_id, "mensajes": mensajes}

    def nodo_compuerta_aprobacion(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        _avanzar(entorno, ejecucion_id, EstadoEjecucion.ESPERANDO_APROBACION)
        interrupt({"tipo": "aprobacion_requerida", "ejecucion_id": ejecucion_id})
        return estado

    def _ruta_tras_aprobacion(estado: EstadoGrafo) -> Literal["generar_cambios", "construir_reporte"]:
        ejecucion_id = estado["ejecucion_id"]
        plan = entorno.repo.obtener_plan_vigente(ejecucion_id)
        decision = entorno.repo.obtener_decision_aprobacion_vigente(plan.id) if plan else None
        d = entorno.gate.verificar_aprobacion(plan, decision)
        if not d.permitido:
            if plan is not None:
                entorno.repo.actualizar_estado_plan(plan.id, EstadoPlan.RECHAZADO.value)
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.BLOQUEADO, MotivoBloqueo.PLAN_RECHAZADO)
            return "construir_reporte"
        entorno.repo.actualizar_estado_plan(plan.id, EstadoPlan.APROBADO.value)
        _avanzar(entorno, ejecucion_id, EstadoEjecucion.APLICANDO_CAMBIOS)
        return "generar_cambios"

    def nodo_generar_cambios(estado: EstadoGrafo) -> EstadoGrafo:
        return _generar_o_reparar_cambios(estado, es_correccion=False)

    def nodo_proponer_correccion(estado: EstadoGrafo) -> EstadoGrafo:
        return _generar_o_reparar_cambios(estado, es_correccion=True)

    def _generar_o_reparar_cambios(estado: EstadoGrafo, *, es_correccion: bool, mensaje_extra: str | None = None) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ctx = _construir_contexto(entorno, ejecucion_id)
        operaciones = ctx.estrategia.scope_template().operaciones
        sistema = prompts.PROPONER_CORRECCION if es_correccion else prompts.GENERAR_CAMBIOS
        mensajes = list(estado["mensajes"])
        if mensaje_extra:
            mensajes.append({"role": "user", "content": [{"text": mensaje_extra}]})

        violaciones_previas: list[str] = []
        for _intento in range(MAX_INTENTOS_VALIDACION_ALCANCE):
            extra = mensajes
            if violaciones_previas:
                extra = mensajes + [{
                    "role": "user",
                    "content": [{"text": "Tu propuesta anterior violó el alcance: " + "; ".join(violaciones_previas) + ". Corrígelo."}],
                }]
            try:
                resultado = pedir_estructurado(
                    ctx, "generar_cambios", sistema=sistema, mensajes=extra,
                    nombre_tool="parche_propuesto", descripcion_tool="Entrega los cambios propuestos",
                    json_schema={
                        "type": "object",
                        "properties": {
                            "cambios": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ruta": {"type": "string"},
                                        "operacion": {"type": "string", "enum": ["crear", "modificar", "borrar"]},
                                        "contenido_nuevo": {"type": "string"},
                                    },
                                    "required": ["ruta", "operacion"],
                                },
                            }
                        },
                        "required": ["cambios"],
                    },
                    nivel_esfuerzo="high",
                )
            except PresupuestoAgotado:
                _finalizar(entorno, ejecucion_id, ResultadoEjecucion.PRESUPUESTO_AGOTADO)
                return estado
            except ErrorSalidaModelo:
                _finalizar(entorno, ejecucion_id, ResultadoEjecucion.FALLIDO_CONTROLADO)
                return estado

            cambios = [CambioArchivoArgs(**c) for c in resultado["cambios"]]
            r = fn_apply_patch(ctx.herramientas_ctx, ArgsApplyPatch(cambios=cambios), operaciones_permitidas=operaciones)
            if r.ok:
                _avanzar(entorno, ejecucion_id, EstadoEjecucion.APLICANDO_CAMBIOS)
                mensajes.append({"role": "user", "content": [{"text": f"Parche aplicado: {r.contenido}"}]})
                return {"ejecucion_id": ejecucion_id, "mensajes": mensajes}

            violaciones_previas = r.detalles or [r.motivo_rechazo or "rechazado"]

        _finalizar(entorno, ejecucion_id, ResultadoEjecucion.BLOQUEADO, MotivoBloqueo.ACCION_BLOQUEADA)
        return estado

    def nodo_ejecutar_verificaciones(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ejecucion_actual = entorno.repo.obtener_ejecucion(ejecucion_id)
        if ejecucion_actual.resultado is not None:
            return estado  # ya se finalizó en el paso anterior (p.ej. presupuesto agotado)

        ctx = _construir_contexto(entorno, ejecucion_id)
        _avanzar(entorno, ejecucion_id, EstadoEjecucion.VERIFICANDO)
        comandos = ctx.estrategia.command_profile().verificacion
        linea_base = _linea_base_pruebas(entorno, ejecucion_id)

        ok_total = True
        ultima_salida = ""
        for comando in comandos:
            r = fn_run_tests(ctx.herramientas_ctx, ArgsRunTests(comando=comando))
            if not r.ok:
                _finalizar(entorno, ejecucion_id, ResultadoEjecucion.BLOQUEADO, MotivoBloqueo.ACCION_BLOQUEADA)
                return estado
            codigo_salida = int(r.detalles[0]) if r.detalles else 0
            totales, exitosas = _parsear_pytest(r.contenido)
            resultado_v = ctx.gate.evaluar_verificacion(codigo_salida, totales, exitosas, linea_base)
            entorno.repo.guardar_verificacion(
                Verificacion(
                    ejecucion_id=ejecucion_id, comando=" ".join(comando), codigo_salida=codigo_salida,
                    salida_capturada=r.contenido[:4000], pruebas_totales=totales, pruebas_exitosas=exitosas,
                    resultado=resultado_v,
                )
            )
            ultima_salida = r.contenido
            if resultado_v is not ResultadoVerificacion.EXITOSA:
                ok_total = False

        mensajes = estado["mensajes"] + [
            {"role": "user", "content": [{"text": f"Salida real de verificación:\n{ultima_salida[:2000]}"}]}
        ]
        if not ok_total:
            mensajes[-1]["content"][0]["text"] += "\n(VERIFICACIÓN FALLIDA -- analiza el error real, no supongas)"
        return {"ejecucion_id": ejecucion_id, "mensajes": mensajes}

    def _ruta_tras_verificacion(estado: EstadoGrafo) -> Literal["exitosa", "corregir", "agotado", "fin_directo"]:
        ejecucion_id = estado["ejecucion_id"]
        ejecucion = entorno.repo.obtener_ejecucion(ejecucion_id)
        if ejecucion.resultado is not None:
            return "fin_directo"

        n = _num_comandos(entorno, ejecucion_id)
        verificaciones = entorno.repo.listar_verificaciones(ejecucion_id)
        ultimas = verificaciones[-n:] if len(verificaciones) >= n else verificaciones
        todas_exitosas = bool(ultimas) and all(v.resultado is ResultadoVerificacion.EXITOSA for v in ultimas)
        if todas_exitosas:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.LISTO_PARA_REVISION)
            return "exitosa"

        solicitud = entorno.repo.obtener_solicitud(ejecucion.solicitud_id)
        if ejecucion.iteraciones_usadas >= solicitud.limite_iteraciones:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.COMPLETADO_PARCIALMENTE)
            return "agotado"

        if ejecucion.estado is not EstadoEjecucion.CORRIGIENDO:
            ejecucion = transicionar(ejecucion, EstadoEjecucion.CORRIGIENDO)
        ejecucion = ejecucion.model_copy(update={"iteraciones_usadas": ejecucion.iteraciones_usadas + 1})
        entorno.repo.actualizar_ejecucion(ejecucion)
        return "corregir"

    def nodo_analizar_error(estado: EstadoGrafo) -> EstadoGrafo:
        ejecucion_id = estado["ejecucion_id"]
        ctx = _construir_contexto(entorno, ejecucion_id)
        try:
            resultado = pedir_estructurado(
                ctx, "analizar_error", sistema=prompts.ANALIZAR_ERROR, mensajes=estado["mensajes"],
                nombre_tool="diagnostico", descripcion_tool="Entrega el diagnóstico de la falla",
                json_schema={"type": "object", "properties": {"causa_raiz": {"type": "string"}}, "required": ["causa_raiz"]},
                nivel_esfuerzo="high",
            )
        except PresupuestoAgotado:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.PRESUPUESTO_AGOTADO)
            return estado
        except ErrorSalidaModelo:
            _finalizar(entorno, ejecucion_id, ResultadoEjecucion.FALLIDO_CONTROLADO)
            return estado

        entorno.repo.guardar_decision_tecnica(
            DecisionTecnica(
                ejecucion_id=ejecucion_id, tipo=TipoDecisionTecnica.CORRECCION,
                descripcion=resultado["causa_raiz"][:2000], sustentada=False,
            )
        )
        mensajes = estado["mensajes"] + [{"role": "user", "content": [{"text": f"Diagnóstico: {resultado['causa_raiz']}"}]}]
        return {"ejecucion_id": ejecucion_id, "mensajes": mensajes}

    def nodo_construir_reporte(estado: EstadoGrafo) -> EstadoGrafo:
        # Determinista salvo la narrativa (03-arquitectura.md §7): el resultado
        # final YA quedó fijado por quien llamó a _finalizar más arriba.
        return estado

    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("interpretar_solicitud", nodo_interpretar_solicitud)
    grafo.add_node("descubrir_repo", nodo_descubrir_repo)
    grafo.add_node("consultar_fuentes", nodo_consultar_fuentes)
    grafo.add_node("evaluar_viabilidad", nodo_evaluar_viabilidad)
    grafo.add_node("proponer_plan", nodo_proponer_plan)
    grafo.add_node("compuerta_aprobacion", nodo_compuerta_aprobacion)
    grafo.add_node("generar_cambios", nodo_generar_cambios)
    grafo.add_node("ejecutar_verificaciones", nodo_ejecutar_verificaciones)
    grafo.add_node("analizar_error", nodo_analizar_error)
    grafo.add_node("proponer_correccion", nodo_proponer_correccion)
    grafo.add_node("construir_reporte", nodo_construir_reporte)

    grafo.add_edge(START, "interpretar_solicitud")
    grafo.add_edge("interpretar_solicitud", "descubrir_repo")
    grafo.add_edge("descubrir_repo", "consultar_fuentes")
    grafo.add_edge("consultar_fuentes", "evaluar_viabilidad")
    grafo.add_conditional_edges(
        "evaluar_viabilidad", _ruta_tras_viabilidad,
        {"proponer_plan": "proponer_plan", "construir_reporte": "construir_reporte", "fin_directo": "construir_reporte"},
    )
    grafo.add_edge("proponer_plan", "compuerta_aprobacion")
    grafo.add_conditional_edges(
        "compuerta_aprobacion", _ruta_tras_aprobacion,
        {"generar_cambios": "generar_cambios", "construir_reporte": "construir_reporte"},
    )
    grafo.add_edge("generar_cambios", "ejecutar_verificaciones")
    grafo.add_conditional_edges(
        "ejecutar_verificaciones", _ruta_tras_verificacion,
        {
            "exitosa": "construir_reporte", "agotado": "construir_reporte",
            "fin_directo": "construir_reporte", "corregir": "analizar_error",
        },
    )
    grafo.add_edge("analizar_error", "proponer_correccion")
    grafo.add_edge("proponer_correccion", "ejecutar_verificaciones")
    grafo.add_edge("construir_reporte", END)

    return grafo


def _num_comandos(entorno: Entorno, ejecucion_id: int) -> int:
    ejecucion = entorno.repo.obtener_ejecucion(ejecucion_id)
    solicitud = entorno.repo.obtener_solicitud(ejecucion.solicitud_id)
    estrategia = obtener_estrategia(solicitud.estrategia_id)
    return max(1, len(estrategia.command_profile().verificacion))


def _linea_base_pruebas(entorno: Entorno, ejecucion_id: int) -> int:
    """Número de pruebas ya existentes antes de cualquier cambio (RN-08):
    se toma de la primera verificación persistida, si la hay; si no, 0
    (el propio primer `run_tests` fija la línea base retroactivamente vía
    `evaluar_verificacion`, que solo exige >= línea base)."""
    verificaciones = entorno.repo.listar_verificaciones(ejecucion_id)
    return verificaciones[0].pruebas_totales if verificaciones else 0


def _parsear_pytest(salida: str) -> tuple[int, int]:
    """Parsea la línea resumen de pytest ('7 passed', '1 failed, 6 passed').
    Control 8: el conteo sale de la salida real, nunca de lo que afirme el
    modelo."""
    import re

    passed = re.search(r"(\d+) passed", salida)
    failed = re.search(r"(\d+) failed", salida)
    error = re.search(r"(\d+) error", salida)
    n_passed = int(passed.group(1)) if passed else 0
    n_failed = int(failed.group(1)) if failed else 0
    n_error = int(error.group(1)) if error else 0
    totales = n_passed + n_failed + n_error
    return totales, n_passed
