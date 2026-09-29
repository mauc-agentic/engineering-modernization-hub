# TC-003 — Verificación fallida y corrección (escenario 3)

**Estado:** Automated · **Casos de uso:** UC-004 · **Requisitos:** FR-013, FR-015, FR-017, FR-023

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Aprobar un plan cuyo parche rompe pruebas | La primera verificación falla con salida real |
| 2 | El agente analiza el error y propone una corrección | Nuevo parche validado contra el alcance aprobado |
| 3 | Re-verificar | Pruebas en verde |
| 4 | Variante: la corrección siempre falla | Al llegar al límite de iteraciones, resultado `PRESUPUESTO_AGOTADO` o `COMPLETADO_PARCIALMENTE`, nunca «exitoso» |

**Automatización:** `tests/scenarios/test_grafo_exitoso_con_correccion.py`, `tests/scenarios/test_fallos_inducidos.py`.
