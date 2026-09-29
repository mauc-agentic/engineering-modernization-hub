# TC-002 — Modernización inviable (escenario 2)

**Estado:** Automated · **Casos de uso:** UC-002, UC-005 · **Requisitos:** FR-007, FR-008, FR-018

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Registrar Flask 2.0.3 → 3.0 con la restricción «Python 3.7 fijo» | Ejecución aceptada |
| 2 | Consultar viabilidad | `INVIABLE`, con la evidencia de PyPI (Flask 3 exige Python ≥ 3.8) |
| 3 | Consultar plan y cambios | No hay plan ni cambios; el código no se toca |

**Automatización:** `tests/scenarios/test_grafo_inviable.py`.
