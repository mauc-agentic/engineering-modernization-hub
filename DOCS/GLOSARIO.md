# Glosario — un solo vocabulario

Estos términos se usan **igual** en el código, la API, la base de datos, la documentación, las slides y el dashboard. Si aparece un sinónimo, es un defecto (lo vigila `tests/docs/`).

| Término | Significado | Nombre en código/API | No usar |
|---|---|---|---|
| **Solicitud** | Petición del desarrollador: repositorio, objetivo, versión, restricciones y límites. | `Solicitud`, `POST /solicitudes` | ticket, request |
| **Ejecución** | Una corrida del flujo para una solicitud. Termina en un **resultado**. | `Ejecucion`, `ejecucion_id` | run, `run_id`, job |
| **Resultado** | Estado final: `LISTO_PARA_REVISION`, `COMPLETADO_PARCIALMENTE`, `BLOQUEADO`, `FALLIDO_CONTROLADO`, `PRESUPUESTO_AGOTADO`. | `resultado` | éxito/fracaso genéricos |
| **Viabilidad** | Veredicto `VIABLE` o `INVIABLE` con evidencia. | `AnalisisViabilidad` | factibilidad |
| **Plan** | Pasos, rutas modificables, comando de verificación y riesgos, con **hash**. | `Plan`, `plan_hash` | propuesta |
| **Aprobación** | Decisión humana `APROBADO`/`RECHAZADO` ligada al hash del plan. | `Aprobacion` | confirmación |
| **Verificación** | Ejecución real de un comando en el sandbox, con salida capturada. | `Verificacion` | test run |
| **Evento de seguridad** | Bloqueo persistido de una acción por la política (regla, origen, acción). | `EventoSeguridad` | alerta, incidente |
| **Traza** | Tramos con duración y tokens (sin contenido) de nodos, modelo y herramientas. | `Traza`, `/traza` | log, telemetría (salvo el transporte OTel) |
| **PolicyGate** | Compuerta determinista con los 8 controles; el modelo no decide ninguno. | `emh.policy.gate.PolicyGate` | guardrails, filtro |
| **Herramienta** | Función del *harness* que el modelo puede pedir: `clone_repo`, `list_files`, `read_file`, `search_docs`, `apply_patch`, `run_tests`. | `HERRAMIENTAS_REGISTRADAS` | plugin, skill |
| **Estrategia** | Módulo que aporta a una modernización: soporte, señales, fuentes, perfil de comandos, alcance y prompts. | `ModernizationStrategy` | plugin |
| **Sandbox** | Entorno aislado donde corre el código del repo: Docker local, tarea Fargate en la nube. | `Sandbox` | contenedor (a secas) |
| **Fase 1 / Fase 2** | F1 se implementa y demuestra; F2 solo diseño (estado `Deferred`). | `Fase` | MVP, v2 |
| **SIMULATED** | Marca en código y docs de todo lo que no es real (modelo guionado, identidad del aprobador). | `SIMULATED:` | mock (sin marca) |

## Estados por artefacto AIUP

| Artefacto | Estados |
|---|---|
| Requisito | `Open`, `In Progress`, `Implemented`, `Verified`, `Deferred`, `Rejected` |
| Caso de uso | `Draft`, `Reviewed`, `Approved`, `Implemented`, `Tested`, `Done`, `Obsolete` |
| Caso de prueba | `Draft`, `Reviewed`, `Approved`, `Automated`, `Obsolete` |
| ADR | `Propuesto`, `Aceptado`, `Sustituido` |

## Cifras vigentes (fuente única: se validan con pruebas)

- Capas: **6**. Controles deterministas: **8**. Herramientas: **6**. Nodos del grafo: **11**.
- Prueba completa: ver el README (`pytest`); la cifra se comprueba en `tests/docs/`.
