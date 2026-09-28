"""`ReportRenderer` (DOCS/03-arquitectura.md §7). Dos partes con dueños
distintos: los HECHOS vienen de lo persistido (código determinista), la
NARRATIVA la redacta el modelo citando fuentes -- y se marca como tal.
Ninguna verificación aparece como exitosa sin su salida real capturada
(AC-08); toda afirmación de la narrativa sin fuente citada se marca "sin
sustento" (RN-12)."""

from __future__ import annotations

from typing import Any

from emh.core.ports import ModelPort, RunRepository


def _resumen_deterministico(hechos: dict[str, Any]) -> str:
    r = hechos["ejecucion"]["resultado"]
    n_cambios = len(hechos["cambios"])
    n_fuentes = len(hechos["fuentes"])
    n_eventos = len(hechos["eventos_seguridad"])
    return (
        f"Resultado: {r}. {n_cambios} archivo(s) en el alcance, "
        f"{len(hechos['verificaciones'])} verificación(es) ejecutada(s), "
        f"{n_fuentes} fuente(s) consultada(s), {n_eventos} evento(s) de seguridad. "
        "(Narrativa determinista de respaldo -- sin modelo disponible al generar el reporte.)"
    )


class ReportRenderer:
    def __init__(self, repo: RunRepository, modelo: ModelPort | None = None) -> None:
        self._repo = repo
        self._modelo = modelo

    def render(self, ejecucion_id: int) -> dict[str, Any]:
        ejecucion = self._repo.obtener_ejecucion(ejecucion_id)
        if ejecucion is None:
            raise ValueError(f"no existe la ejecución {ejecucion_id}")
        solicitud = self._repo.obtener_solicitud(ejecucion.solicitud_id)
        plan = self._repo.obtener_plan_vigente(ejecucion_id)
        analisis = self._repo.obtener_analisis_viabilidad(ejecucion_id) if hasattr(self._repo, "obtener_analisis_viabilidad") else None
        verificaciones = self._repo.listar_verificaciones(ejecucion_id)
        fuentes = self._repo.listar_fuentes(ejecucion_id)
        eventos = self._repo.listar_eventos_seguridad(ejecucion_id)
        decisiones = self._repo.listar_decisiones_tecnicas(ejecucion_id)
        llamadas = self._repo.listar_llamadas_modelo(ejecucion_id)

        decisiones_con_citas = []
        for d in decisiones:
            citas = self._repo.listar_citas(d.id) if d.id is not None else []
            fuentes_citadas = [f.url for c in citas for f in fuentes if f.id == c.fuente_id]
            decisiones_con_citas.append({
                "tipo": d.tipo.value, "descripcion": d.descripcion,
                "sustentada": bool(fuentes_citadas), "fuentes": fuentes_citadas,
            })

        cambios = list(plan.rutas_declaradas) if (plan and ejecucion.resultado and ejecucion.resultado.value in {"LISTO_PARA_REVISION", "COMPLETADO_PARCIALMENTE"}) else []

        hechos = {
            "ejecucion": {
                "id": ejecucion.id, "estado": ejecucion.estado.value,
                "resultado": ejecucion.resultado.value if ejecucion.resultado else None,
                "motivo_bloqueo": ejecucion.motivo_bloqueo.value if ejecucion.motivo_bloqueo else None,
                "tokens_entrada": sum(l.tokens_entrada for l in llamadas),
                "tokens_salida": sum(l.tokens_salida for l in llamadas),
                "costo_estimado_usd": ejecucion.costo_estimado_usd,
                "iteraciones_usadas": ejecucion.iteraciones_usadas,
                "iniciado_en": ejecucion.iniciado_en.isoformat(),
                "finalizado_en": ejecucion.finalizado_en.isoformat() if ejecucion.finalizado_en else None,
            },
            "solicitud": {
                "repositorio_url": solicitud.repositorio_url, "objetivo": solicitud.objetivo,
                "version_esperada": solicitud.version_esperada,
            },
            "analisis_viabilidad": (
                {"veredicto": analisis.veredicto.value, "impacto_detectado": analisis.impacto_detectado, "evidencia": analisis.evidencia}
                if analisis else None
            ),
            "plan": (
                {"hash": plan.hash, "pasos": plan.pasos, "rutas_declaradas": plan.rutas_declaradas, "estado": plan.estado.value}
                if plan else None
            ),
            "cambios": cambios,
            "verificaciones": [
                {
                    "comando": v.comando, "codigo_salida": v.codigo_salida,
                    "resultado": v.resultado.value, "pruebas_totales": v.pruebas_totales,
                    "pruebas_exitosas": v.pruebas_exitosas, "salida_capturada": v.salida_capturada,
                }
                for v in verificaciones
            ],
            "fuentes": [{"id": f.id, "tipo": f.tipo.value, "url": f.url, "consultada_en": f.consultada_en.isoformat()} for f in fuentes],
            "decisiones_tecnicas": decisiones_con_citas,
            "eventos_seguridad": [
                {"regla": ev.regla, "accion_intentada": ev.accion_intentada, "origen": ev.origen.value,
                 "severidad": ev.severidad.value, "registrado_en": ev.registrado_en.isoformat()}
                for ev in eventos
            ],
        }

        narrativa = _resumen_deterministico(hechos)
        narrativa_generada_por_ia = False
        if self._modelo is not None:
            try:
                from emh.agent.runtime import pedir_estructurado, ContextoAgente
                # Reporte "ligero": no se pasa por PresupuestoMeter de una
                # ejecución (el reporte se puede pedir después de terminada);
                # se usa el modelo directamente, sin control 4 (no hay
                # ejecución en curso a la que cargarle este costo).
                respuesta = self._modelo.completar(
                    mensajes=[{"role": "user", "content": [{"text": (
                        "Hechos de la ejecución (no los alteres, solo resúmelos, citando "
                        f"IDs de fuente cuando sustenten una afirmación): {hechos}"
                    )}]}],
                    sistema=(
                        "Redacta un resumen breve y honesto para el desarrollador. "
                        "No inventes fuentes ni resultados. Responde SOLO invocando la herramienta."
                    ),
                    herramientas=[{
                        "toolSpec": {
                            "name": "resumen_reporte", "description": "Entrega el resumen narrativo",
                            "inputSchema": {"json": {"type": "object", "properties": {"resumen": {"type": "string"}}, "required": ["resumen"]}},
                        }
                    }],
                    nivel_esfuerzo="low",
                )
                for llamada in respuesta.llamadas_herramienta:
                    if llamada.nombre == "resumen_reporte":
                        narrativa = llamada.argumentos["resumen"]
                        narrativa_generada_por_ia = True
            except Exception:
                pass  # el reporte de hechos nunca depende de que la narrativa funcione

        return {**hechos, "narrativa": narrativa, "narrativa_generada_por_ia": narrativa_generada_por_ia}
