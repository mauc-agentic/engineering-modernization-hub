# Trazabilidad requisito → código → prueba

> Generado por `scripts/generar_trazabilidad.py` desde `DOCS/trazabilidad.yaml`. No editar a mano.

| ID | Título | Estado | Código | Pruebas |
|---|---|---|---|---|
| FR-001 | Registrar solicitud | Verified | `emh/api/app.py`<br>`emh/api/schemas.py` | `tests/contract/test_api.py` |
| FR-002 | Validar solicitud | Verified | `emh/api/app.py` | `tests/contract/test_api.py` |
| FR-003 | Consultar estado y eventos | Verified | `emh/api/app.py` | `tests/contract/test_api.py` |
| FR-004 | Descubrir el repositorio | Verified | `emh/agent/graph.py`<br>`emh/harness/tools.py` | `tests/scenarios/test_grafo_exitoso_con_correccion.py` |
| FR-005 | Consultar fuentes oficiales | Verified | `emh/harness/tools.py`<br>`emh/policy/gate.py` | `tests/unit/test_harness_tools.py`<br>`tests/unit/test_strategies.py` |
| FR-006 | Analizar impacto | Verified | `emh/agent/graph.py`<br>`emh/agent/prompts.py` | `tests/scenarios/test_grafo_exitoso_con_correccion.py` |
| FR-007 | Determinar viabilidad técnica | Verified | `emh/agent/graph.py` | `tests/scenarios/test_grafo_inviable.py` |
| FR-008 | Notificar inviabilidad | Verified | `emh/agent/graph.py` | `tests/scenarios/test_grafo_inviable.py` |
| FR-009 | Proponer plan | Verified | `emh/agent/graph.py`<br>`emh/core/models.py` | `tests/scenarios/test_grafo_exitoso_con_correccion.py` |
| FR-010 | Revisar análisis y plan | Verified | `emh/api/app.py`<br>`frontend/index.html` | `tests/contract/test_api.py` |
| FR-011 | Aprobar o rechazar el plan | Verified | `emh/policy/gate.py`<br>`emh/api/app.py` | `tests/unit/test_policy_gate.py`<br>`tests/contract/test_api.py` |
| FR-012 | Generar cambios | Verified | `emh/agent/graph.py`<br>`emh/harness/tools.py` | `tests/scenarios/test_grafo_exitoso_con_correccion.py` |
| FR-013 | Validar el parche contra el alcance | Verified | `emh/policy/gate.py` | `tests/unit/test_policy_gate.py` |
| FR-014 | Crear o actualizar pruebas | Verified | `emh/policy/gate.py`<br>`emh/strategies/python_dependency_upgrade.py` | `tests/unit/test_policy_gate.py`<br>`tests/unit/test_strategies.py` |
| FR-015 | Ejecutar verificaciones | Verified | `emh/execution/docker_sandbox.py`<br>`emh/execution/fargate_sandbox.py` | `tests/contract/test_docker_sandbox.py`<br>`tests/unit/test_fargate_sandbox.py` |
| FR-016 | Consultar verificaciones | Verified | `emh/api/app.py` | `tests/contract/test_api.py` |
| FR-017 | Corregir errores de forma controlada | Verified | `emh/agent/graph.py` | `tests/scenarios/test_grafo_exitoso_con_correccion.py` |
| FR-018 | Terminar con un resultado claro | Verified | `emh/core/state_machine.py` | `tests/unit/test_state_machine.py` |
| FR-019 | Obtener el reporte | Verified | `emh/reporting/renderer.py` | `tests/unit/test_reporting.py` |
| FR-020 | Persistir y retomar el estado | Verified | `emh/persistence/sqlite_repo.py`<br>`emh/persistence/postgres_repo.py`<br>`emh/bootstrap.py` | `tests/contract/test_run_repository.py`<br>`tests/contract/test_checkpointer_persistente.py` |
| FR-021 | Registrar eventos de seguridad | Verified | `emh/policy/gate.py`<br>`emh/harness/tools.py` | `tests/unit/test_harness_tools.py`<br>`tests/scenarios/test_grafo_solicitud_insegura.py` |
| FR-022 | Resistir solicitudes inseguras | Verified | `emh/agent/prompts.py`<br>`emh/policy/gate.py` | `tests/scenarios/test_grafo_solicitud_insegura.py` |
| FR-023 | Controlar presupuestos | Verified | `emh/core/budget.py` | `tests/unit/test_budget.py` |
| FR-024 | Registrar una estrategia nueva | Verified | `emh/strategies/registry.py`<br>`emh/bootstrap.py` | `tests/unit/test_strategies.py` |
| FR-025 | Modernizar una dependencia Python | Verified | `emh/strategies/python_dependency_upgrade.py` | `tests/unit/test_strategies.py` |
| FR-026 | Ejecutar los escenarios obligatorios | Verified | `tests/scenarios` | `tests/scenarios/test_grafo_exitoso_con_correccion.py`<br>`tests/scenarios/test_grafo_inviable.py`<br>`tests/scenarios/test_grafo_solicitud_insegura.py` |
| FR-038 | Despliegue en AWS con Terraform *(promovido de F2 a F1 por D-9 de `00-vision.md`, 2026-09-28)* | Verified | `infra/ecs.tf`<br>`infra/rds.tf`<br>`infra/cloudfront.tf` | `.github/workflows/ci.yml` |
| FR-040 | Ejecutar con sandbox y persistencia en la nube | Verified | `emh/execution/fargate_sandbox.py`<br>`emh/persistence/postgres_repo.py` | `tests/unit/test_fargate_sandbox.py`<br>`tests/unit/test_bootstrap.py` |
| FR-041 | Traza de ejecución consultable | Verified | `emh/agent/traza.py` | `tests/unit/test_traza_otel.py`<br>`tests/scenarios/test_grafo_exitoso_con_correccion.py` |
| FR-042 | Dashboard de autoservicio | Verified | `frontend/index.html` | `tests/contract/test_api.py` |
| FR-030 | Autoservicio en Backstage | Deferred | — | — |
| FR-031 | CLI | Deferred | — | — |
| FR-032 | Estrategia de imagen base | Deferred | — | — |
| FR-033 | Estrategia de migración de framework | Deferred | — | — |
| FR-034 | Persistencia en Postgres con alta disponibilidad y multi-tenant | Deferred | — | — |
| FR-035 | Multi-tenant | Deferred | — | — |
| FR-036 | Métricas de adopción y DORA | Deferred | — | — |
| FR-037 | Colas y ejecución distribuida | Deferred | — | — |
| FR-039 | Autenticación y roles | Deferred | — | — |
| FR-043 | Alta disponibilidad de cómputo y datos | Deferred | — | — |
| FR-044 | Despliegue continuo | Deferred | — | — |
| NFR-001 | Cero secretos en contexto | Verified | `emh/policy/gate.py` | `tests/scenarios/test_grafo_solicitud_insegura.py`<br>`tests/unit/test_policy_gate.py` |
| NFR-002 | Toda acción pasa por la política | Verified | `emh/policy/gate.py`<br>`emh/harness/tools.py` | `tests/unit/test_toda_accion_pasa_por_la_politica.py` |
| NFR-003 | Cero cambios sin aprobación | Verified | `emh/policy/gate.py` | `tests/unit/test_policy_gate.py` |
| NFR-004 | Aislamiento del sandbox | Verified | `emh/execution/docker_sandbox.py` | `tests/contract/test_docker_sandbox.py` |
| NFR-005 | Red restringida | Verified | `emh/execution/docker_sandbox.py`<br>`infra/network.tf` | `tests/contract/test_docker_sandbox.py` |
| NFR-006 | Resistencia a inyección | Verified | `emh/agent/prompts.py`<br>`emh/policy/gate.py` | `tests/scenarios/test_grafo_solicitud_insegura.py` |
| NFR-007 | Toda ejecución termina | Verified | `emh/agent/runner.py` | `tests/scenarios/test_fallos_inducidos.py` |
| NFR-008 | Errores del modelo | Verified | `emh/agent/runtime.py`<br>`emh/models/bedrock.py` | `tests/scenarios/test_fallos_inducidos.py`<br>`tests/unit/test_reintentos_bedrock.py` |
| NFR-009 | Corte duro de presupuesto | Verified | `emh/core/budget.py` | `tests/unit/test_budget.py` |
| NFR-010 | Costo visible | Verified | `emh/reporting/renderer.py` | `tests/unit/test_reporting.py` |
| NFR-011 | Duración de la demo | In Progress | — | — |
| NFR-012 | Trazabilidad de fuentes | Verified | `emh/reporting/renderer.py` | `tests/unit/test_reporting.py` |
| NFR-013 | Trazabilidad de bloqueos | Verified | `emh/harness/tools.py`<br>`emh/persistence/sqlite_repo.py` | `tests/unit/test_harness_tools.py` |
| NFR-014 | Traza de llamadas | Verified | `emh/agent/traza.py` | `tests/unit/test_traza_otel.py` |
| NFR-015 | Extensibilidad del núcleo | Verified | `emh/strategies/registry.py`<br>`pyproject.toml` | `tests/unit/test_strategies.py` |
| NFR-016 | Portabilidad de proveedor y persistencia | Verified | `emh/core/ports.py`<br>`emh/bootstrap.py` | `tests/unit/test_bootstrap.py`<br>`tests/contract/test_run_repository.py` |
| NFR-017 | Reproducibilidad de la demo | Verified | `scripts/00-preparar.sh`<br>`scripts/01-pruebas.sh` | `.github/workflows/ci.yml` |
| NFR-018 | Pruebas de escenario estables | Verified | `emh/models/scripted.py` | `tests/unit/test_scripted_model.py` |
| NFR-019 | Honestidad de lo simulado | Verified | `emh/models/scripted.py`<br>`emh/api/schemas.py` | `tests/docs/test_coherencia.py` |
| NFR-020 | Aislamiento entre ejecuciones | Verified | `emh/persistence/sqlite_repo.py` | `tests/contract/test_run_repository.py` |
| NFR-021 | Contrato de la API | Verified | `emh/api/app.py`<br>`emh/api/schemas.py` | `tests/contract/test_api.py` |
| NFR-022 | Commits trazables | Verified | `scripts/verificar_commits.py`<br>`scripts/hooks/commit-msg` | `tests/unit/test_verificar_commits.py` |
| NFR-023 | Guardarraíl de costo en la nube | Verified | `infra/budget.tf` | `.github/workflows/ci.yml` |
| NFR-024 | Sin costo fijo olvidable | Verified | `infra/rds.tf`<br>`infra/alb.tf` | `.github/workflows/ci.yml` |
| NFR-025 | Portabilidad local/nube | Verified | `emh/bootstrap.py` | `tests/unit/test_bootstrap.py` |
| NFR-026 | Observabilidad del agente | Verified | `emh/agent/traza.py`<br>`infra/observabilidad.tf` | `tests/unit/test_traza_otel.py` |
| NFR-027 | URL pública protegida | Verified | `infra/cloudfront.tf`<br>`infra/alb.tf` | `.github/workflows/ci.yml` |
| NFR-028 | Seguridad del repositorio público | Verified | `.github/CODEOWNERS`<br>`.github/dependabot.yml`<br>`SECURITY.md` | `.github/workflows/ci.yml` |
| NFR-029 | Coherencia documentación–código | In Progress | — | — |
| C-001 | Lenguaje | Verified | — | — |
| C-002 | Interfaz | Verified | — | — |
| C-003 | Framework agentic | Verified | — | — |
| C-004 | Proveedor y modelo | Verified | — | — |
| C-005 | Runtime de ejecución | Verified | — | — |
| C-006 | Persistencia | Verified | — | — |
| C-007 | Una estrategia | Verified | — | — |
| C-008 | No específico | Verified | — | — |
| C-009 | Fecha de entrega | In Progress | — | — |
| C-010 | Dedicación | In Progress | — | — |
| C-011 | Sustentación | In Progress | — | — |
| C-012 | Solo Fase 1 | Verified | — | — |
| C-013 | Sin insumos del cliente | Verified | — | — |
| C-014 | Repositorio de la demo | Verified | — | — |
| C-015 | Metodología AIUP | Verified | — | — |
| C-016 | Orden de implementación | In Progress | — | — |
| C-017 | Entregables | In Progress | — | — |
| C-018 | Sin mocks disfrazados | Verified | — | — |
| C-019 | Infraestructura como código | Verified | — | — |
| C-020 | Presupuesto de nube | Verified | — | — |
| C-021 | Versión de Python | Verified | — | — |
| C-022 | Repositorio público y licencia | Verified | — | — |

Los requisitos `C-*` (restricciones), NFR-011, NFR-029 y los `Deferred` (Fase 2) no tienen prueba automática por diseño.
