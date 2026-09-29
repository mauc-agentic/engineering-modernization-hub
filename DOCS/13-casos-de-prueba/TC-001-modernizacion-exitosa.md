# TC-001 — Modernización exitosa (escenario 1)

**Estado:** Automated · **Casos de uso:** UC-001, UC-002, UC-003, UC-004, UC-005 · **Requisitos:** FR-001, FR-007, FR-009, FR-011, FR-012, FR-015, FR-018, FR-019

**Precondición:** repositorio de la demo con PyYAML 5.3.1; el objetivo pide 6.0.2.

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Registrar la solicitud (`scripts/02-enviar.sh` o dashboard) | 202, ejecución en `ANALISIS` |
| 2 | Consultar viabilidad y plan | `VIABLE` con fuentes; plan con hash |
| 3 | Aprobar el plan | Decisión ligada al hash |
| 4 | Esperar la ejecución | Parche aplicado dentro del alcance; verificaciones ejecutadas de verdad |
| 5 | Obtener el reporte | `LISTO_PARA_REVISION`, fuentes citadas, costo con 4 decimales |

**Automatización:** `tests/scenarios/test_grafo_exitoso_con_correccion.py` (modelo guionado, siempre en CI) y ejecución real en AWS (slide 9).
