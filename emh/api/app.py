"""API REST (C-002, FastAPI). Traduce HTTP al núcleo; no contiene lógica de
negocio (DOCS/03-arquitectura.md §3.6). La ejecución corre en segundo plano
(`BackgroundTasks`); el cliente consulta por sondeo (UC-001 a UC-005)."""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from emh.api.schemas import (
    AprobacionEntrada,
    ErrorRespuesta,
    SolicitudEntrada,
    SolicitudRespuesta,
)
from emh.bootstrap import Aplicacion
from emh.core.models import DecisionAprobacion, Ejecucion, Solicitud
from emh.strategies.registry import obtener_estrategia


def _error(codigo: str, mensaje: str, run_id: int | None = None) -> dict:
    return ErrorRespuesta(codigo=codigo, mensaje=mensaje, run_id=run_id).model_dump()


def crear_app(aplicacion: Aplicacion) -> FastAPI:
    app = FastAPI(title="Engineering Modernization Hub", version="0.1.0")

    # CORS abierto a propósito para el dashboard de demo (frontend/index.html,
    # servido como archivo local o localhost): no hay autenticación real en
    # F1 (RN-14) y el Hub no se expone públicamente en esta configuración.
    # NO usar así en un despliegue real (ver DOCS/07-seguridad.md).
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )
    app.state.aplicacion = aplicacion

    @app.post("/solicitudes", response_model=SolicitudRespuesta, status_code=201)
    def registrar_solicitud(entrada: SolicitudEntrada, background: BackgroundTasks):
        # FR-002: validar que la estrategia exista antes de registrar (UC-001 A2)
        if obtener_estrategia(entrada.estrategia_id) is None:
            raise HTTPException(422, detail=_error("ESTRATEGIA_NO_SOPORTADA", f"'{entrada.estrategia_id}' no está registrada"))

        solicitud = aplicacion.repo.guardar_solicitud(Solicitud(**entrada.model_dump()))
        ejecucion = aplicacion.repo.guardar_ejecucion(Ejecucion(solicitud_id=solicitud.id))
        background.add_task(aplicacion.runner.run, ejecucion.id)
        return SolicitudRespuesta(ejecucion_id=ejecucion.id, estado=ejecucion.estado.value)

    @app.get("/ejecuciones/{ejecucion_id}")
    def obtener_ejecucion(ejecucion_id: int):
        e = aplicacion.repo.obtener_ejecucion(ejecucion_id)
        if e is None:
            raise HTTPException(404, detail=_error("NO_ENCONTRADO", "ejecución no encontrada", ejecucion_id))
        return {
            "ejecucion_id": e.id, "estado": e.estado.value,
            "resultado": e.resultado.value if e.resultado else None,
            "motivo_bloqueo": e.motivo_bloqueo.value if e.motivo_bloqueo else None,
            "iteraciones_usadas": e.iteraciones_usadas, "costo_estimado_usd": e.costo_estimado_usd,
        }

    @app.get("/ejecuciones/{ejecucion_id}/analisis-viabilidad")
    def obtener_analisis(ejecucion_id: int):
        analisis = aplicacion.repo.obtener_analisis_viabilidad(ejecucion_id)
        if analisis is None:
            raise HTTPException(404, detail=_error("NO_ENCONTRADO", "aún no hay análisis de viabilidad", ejecucion_id))
        return {
            "veredicto": analisis.veredicto.value, "impacto_detectado": analisis.impacto_detectado,
            "evidencia": analisis.evidencia,
        }

    @app.get("/ejecuciones/{ejecucion_id}/plan")
    def obtener_plan(ejecucion_id: int):
        plan = aplicacion.repo.obtener_plan_vigente(ejecucion_id)
        if plan is None:
            raise HTTPException(404, detail=_error("NO_ENCONTRADO", "aún no hay plan propuesto", ejecucion_id))
        return {
            "plan_id": plan.id, "hash": plan.hash, "estado": plan.estado.value,
            "pasos": plan.pasos, "rutas_declaradas": plan.rutas_declaradas,
            "comandos_verificacion": plan.comandos_verificacion, "riesgos": plan.riesgos,
        }

    @app.post("/ejecuciones/{ejecucion_id}/aprobacion", status_code=202)
    def aprobar_o_rechazar(ejecucion_id: int, entrada: AprobacionEntrada, background: BackgroundTasks):
        ejecucion = aplicacion.repo.obtener_ejecucion(ejecucion_id)
        if ejecucion is None:
            raise HTTPException(404, detail=_error("NO_ENCONTRADO", "ejecución no encontrada", ejecucion_id))
        plan = aplicacion.repo.obtener_plan_vigente(ejecucion_id)
        if plan is None or plan.id != entrada.plan_id:
            raise HTTPException(409, detail=_error("PLAN_NO_VIGENTE", "el plan indicado ya no es el vigente", ejecucion_id))

        aplicacion.repo.guardar_decision_aprobacion(DecisionAprobacion(
            plan_id=entrada.plan_id, plan_hash=entrada.plan_hash, decision=entrada.decision,
            aprobador=entrada.aprobador, comentario=entrada.comentario,
        ))
        background.add_task(aplicacion.runner.resume, ejecucion_id)
        return {"ejecucion_id": ejecucion_id, "decision_registrada": entrada.decision}

    @app.get("/ejecuciones/{ejecucion_id}/verificaciones")
    def listar_verificaciones(ejecucion_id: int):
        return [
            {
                "comando": v.comando, "codigo_salida": v.codigo_salida, "resultado": v.resultado.value,
                "pruebas_totales": v.pruebas_totales, "pruebas_exitosas": v.pruebas_exitosas,
                "salida_capturada": v.salida_capturada, "ejecutado_en": v.ejecutado_en.isoformat(),
            }
            for v in aplicacion.repo.listar_verificaciones(ejecucion_id)
        ]

    @app.get("/ejecuciones/{ejecucion_id}/eventos")
    def listar_eventos(ejecucion_id: int):
        return [
            {
                "regla": ev.regla, "accion_intentada": ev.accion_intentada, "origen": ev.origen.value,
                "severidad": ev.severidad.value, "registrado_en": ev.registrado_en.isoformat(),
            }
            for ev in aplicacion.repo.listar_eventos_seguridad(ejecucion_id)
        ]

    @app.get("/ejecuciones/{ejecucion_id}/traza")
    def obtener_traza(ejecucion_id: int):
        """Observabilidad de la ejecución: cada nodo, llamada al modelo y herramienta
        con su duración real, tokens y resultado. Sin contenido de prompts ni archivos."""
        if aplicacion.repo.obtener_ejecucion(ejecucion_id) is None:
            raise HTTPException(404, detail=_error("NO_ENCONTRADO", "ejecución no encontrada", ejecucion_id))
        trazas = aplicacion.repo.listar_trazas(ejecucion_id)
        t0 = min((t.inicio for t in trazas), default=None)
        tramos = [
            {
                "tipo": t.tipo, "nombre": t.nombre, "ok": t.ok, "duracion_ms": t.duracion_ms,
                "desplazamiento_ms": int((t.inicio - t0).total_seconds() * 1000),
                "tokens_entrada": t.tokens_entrada, "tokens_salida": t.tokens_salida, "detalle": t.detalle,
            }
            for t in trazas
        ]
        fin = max((x["desplazamiento_ms"] + x["duracion_ms"] for x in tramos), default=0)
        return {
            "tramos": tramos,
            "resumen": {
                "duracion_total_ms": fin,
                "llamadas_modelo": sum(1 for t in trazas if t.tipo == "modelo"),
                "llamadas_herramienta": sum(1 for t in trazas if t.tipo == "herramienta"),
                "tokens_entrada": sum(t.tokens_entrada for t in trazas),
                "tokens_salida": sum(t.tokens_salida for t in trazas),
                "errores": sum(1 for t in trazas if not t.ok),
            },
        }

    @app.get("/ejecuciones/{ejecucion_id}/reporte")
    def obtener_reporte(ejecucion_id: int):
        try:
            return aplicacion.reporte.render(ejecucion_id)
        except ValueError:
            raise HTTPException(404, detail=_error("NO_ENCONTRADO", "ejecución no encontrada", ejecucion_id))

    return app


def app_factory() -> FastAPI:
    """Fábrica de cero argumentos, para `uvicorn emh.api.app:app_factory
    --factory` (contenedor/producción). `EMH_MODO_SIMULADO=1` la arma con
    `ScriptedModel` en vez de Bedrock real."""
    return crear_app(Aplicacion())
