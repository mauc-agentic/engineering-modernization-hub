# 10 — Evolución hacia un producto interno de producción

| | |
|---|---|
| **Estado** | APROBADO el 2026-09-28 |
| **Alcance** | Fase 2 — solo diseño, con interfaces ya definidas en el código de F1 donde aplica. Nada de esta sección se implementa. |

Para cada elemento: qué es, por qué no entró en F1, y qué habría que tocar para agregarlo. El criterio general de F1 → F2 fue: **todo lo que el flujo necesita para ser completo, seguro y demostrable de extremo a extremo entra en F1; todo lo que escala ese flujo a más usuarios, más equipos o más tipos de modernización, sin cambiar su forma, queda en F2.**

---

## FR-030 — Autoservicio en Backstage

**Qué es:** un *plugin* de Backstage que envuelve la API de F1 (`emh/api`) en una experiencia de autoservicio dentro del portal de desarrollador de la organización: formulario para registrar la solicitud, vista del plan con botones de aprobar/rechazar, seguimiento del progreso.

**Por qué no entró en F1:** el caso ordena las interfaces de menor a mayor complejidad (API < CLI < Backstage); con 10–12 horas de dedicación, priorizar Backstage habría significado un flujo de UI sin la garantía de que el flujo de negocio detrás fuera completo y seguro.

**Qué habría que tocar:** nada en `emh/core`, `emh/policy`, `emh/harness`, `emh/agent` ni `emh/strategies`. Se añade un cliente HTTP del *plugin* de Backstage contra los mismos *endpoints* de `emh/api`; en el backend, quizás un *endpoint* adicional de agregación (p. ej. "mis solicitudes recientes") que es una consulta de solo lectura sobre `RunRepository`, sin lógica de negocio nueva.

## FR-031 — CLI

**Qué es:** un cliente de línea de comandos (`emh solicitar`, `emh aprobar`, `emh reporte`) que llama a la misma API.

**Por qué no entró en F1:** misma razón de orden de complejidad; el valor incremental sobre la API desnuda es de conveniencia, no de flujo.

**Qué habría que tocar:** un paquete nuevo, `emh-cli`, cliente puro de `emh/api`. Cero cambios en el resto del sistema.

## FR-032 — Estrategia de imagen base

**Qué es:** `BaseImageUpgradeStrategy`, ya diseñada por completo (con su código de ejemplo) en `06-estrategias.md` §3.

**Por qué no entró en F1:** el caso pide **una** estrategia funcionando de extremo a extremo en F1 y una explicación de cómo se agrega una segunda sin tocar el núcleo; implementarla habría duplicado esfuerzo de demo sin requisito adicional del caso.

**Qué habría que tocar:** exactamente lo descrito en `06-estrategias.md` §3.2 — un archivo nuevo y dos líneas fuera de él.

## FR-033 — Estrategia de migración de framework

**Qué es:** una estrategia para migraciones de framework a una versión mayor (p. ej. Flask 2 → 3, Django 4 → 5), con señales de configuración propias del framework y fuentes que incluyen su guía de migración oficial.

**Por qué no entró en F1:** mismo motivo que FR-032; además, es la modernización de mayor superficie de cambio (suele tocar más archivos que una dependencia o una imagen), lo que la hace la candidata menos adecuada para un prototipo con presupuesto de tiempo fijo.

**Qué habría que tocar:** el mismo patrón de FR-032. La diferencia de diseño frente a una dependencia simple es que su `scope_template` normalmente declara un conjunto de rutas más amplio (todo el árbol de código que usa APIs del framework), lo cual es una decisión de la estrategia, no del núcleo — el mecanismo de extensión no cambia.

## FR-034 — Persistencia en Postgres

**Qué es:** reemplazar el adaptador SQLite de `RunRepository` por uno de Postgres, para durabilidad y concurrencia de producción.

**Por qué no entró en F1:** SQLite basta para un escritor por ejecución y la escala de la demo (ADR-004); Postgres añade infraestructura que operar sin beneficio demostrable en el prototipo.

**Qué habría que tocar:** un adaptador nuevo en `emh/persistence` que implemente `RunRepository` contra Postgres (SQLAlchemy Core o `psycopg`), más migraciones de esquema. `emh/core` no cambia (NFR-016): es la prueba en vivo de que el puerto cumplió su propósito.

## FR-035 — Multi-tenant

**Qué es:** aislar datos, presupuestos y políticas por equipo u organización, para ofrecer el Hub a varios equipos sin que se afecten entre sí.

**Por qué no entró en F1:** el caso pide un prototipo funcional de un flujo, no una plataforma multi-organización; añadir aislamiento de *tenant* antes de validar el flujo habría sido invertir en la dimensión equivocada primero.

**Qué habría que tocar:** un `tenant_id` en cada entidad de `02-modelo-entidades.md`, filtrado en cada consulta de `RunRepository`, y un `tenant_id` en `ContextoPolitica` para que las *allowlists* y presupuestos puedan variar por equipo. Afecta a `emh/persistence` y a la construcción del contexto en `emh/policy`; no al mecanismo de los ocho controles en sí.

## FR-036 — Métricas de adopción y DORA

**Qué es:** paneles de cuántas modernizaciones se solicitan, su tasa de éxito, tiempo de ciclo, y métricas DORA derivadas (frecuencia de despliegue, tiempo de recuperación) para los repositorios modernizados.

**Por qué no entró en F1:** es una capacidad de negocio sobre datos que el sistema recién empezaría a generar; antes de medir adopción hace falta que haya algo que adoptar.

**Qué habría que tocar:** un adaptador de solo lectura sobre `RunRepository` (o un almacén de métricas separado alimentado por eventos) que agrega `EJECUCION`, `VERIFICACION` y `LLAMADA_MODELO` ya persistidos. No requiere cambios en el núcleo ni en la captura de datos de F1: los campos necesarios (`iniciado_en`, `finalizado_en`, `resultado`, `iteraciones_usadas`) ya existen.

## FR-037 — Colas y ejecución distribuida

**Qué es:** encolar solicitudes y distribuir ejecuciones entre varios *workers*, para atender carga concurrente sin degradar el servicio.

**Por qué no entró en F1:** con NFR-020 (2 ejecuciones concurrentes) como techo de F1, un solo proceso basta; una cola introduce infraestructura (broker) sin carga que la justifique todavía.

**Qué habría que tocar:** `AgentRunner.run()` ya es la unidad de trabajo (un `run_id`); se envuelve en una tarea de cola (p. ej. Celery, o colas nativas de AWS en F2 con SQS) que invoca lo mismo que hoy invoca la API en segundo plano. El *checkpointer* de LangGraph (ADR-003) ya soporta reanudar desde otro proceso, lo cual es precisamente lo que un *worker* distribuido necesita.

## FR-038 — Despliegue en AWS con Terraform — **promovido a F1 (D-9, 2026-09-28)**

**Qué es:** infraestructura como código para desplegar el Hub (API, base de datos, *runner* de contenedores) en AWS.

**Por qué se promovió de F2 a F1:** el caso lo marca como un plus; el autor decidió tomarlo, con USD 100 de crédito disponibles y disciplina FinOps explícita en cada decisión (`ADR-006`, `ADR-007`). Deja de estar en esta sección porque ya no es diseño sin implementar — ver `03-arquitectura.md` §9. Se conserva esta entrada para no romper la numeración y como registro de que la decisión de alcance cambió después de la primera aprobación.

**Lo que sigue en F2, sin implementar:** alta disponibilidad (Multi-AZ en RDS, varias réplicas de la tarea de la API detrás de un balanceador), *pipeline* de CI/CD que corra `terraform apply` automáticamente, y entornos separados (`staging`/`producción`) — todo lo que un despliegue de demo de un día no necesita pero un producto interno sí.

## FR-039 — Autenticación y roles

**Qué es:** autenticación real de usuarios (SSO) y separación del rol de solicitante y aprobador, resolviendo la simulación de identidad de F1 (RN-14, `07-seguridad.md` §2, amenaza de suplantación).

**Por qué no entró en F1:** el caso no exige autenticación de usuarios; la identidad se acepta declarada y se marca explícitamente como simulación, sin inventar un sistema de login que distraiga presupuesto del flujo central.

**Qué habría que tocar:** middleware de autenticación en `emh/api` (OIDC/SSO), un campo `aprobador_verificado` en `DECISION_APROBACION` que reemplace la confianza en el campo declarado, y una regla de autorización que impida que el mismo usuario que registra la solicitud sea, por defecto, quien la aprueba (separación de funciones), configurable por política organizacional.

---

## Resumen de impacto en el núcleo

| Elemento de F2 | ¿Toca `emh/core`? |
|---|---|
| Backstage, CLI | No |
| Estrategia de imagen base, de framework | No (`06-estrategias.md` §3 lo demuestra) |
| Postgres | No (solo el adaptador `emh/persistence`) |
| Multi-tenant | Sí, mínimamente: un campo `tenant_id` en las entidades y en `ContextoPolitica` |
| Métricas de adopción/DORA | No |
| Colas y ejecución distribuida | No (envuelve `AgentRunner`, no lo modifica) |
| Terraform/AWS *(ya en F1, ver arriba)* | No (son adaptadores nuevos, mismos puertos) |
| Alta disponibilidad, CI/CD, entornos separados (lo que queda de FR-038 en F2) | No |
| SSO y roles | No en el dominio central; sí en `emh/api` (borde) |

De los nueve elementos que quedan en F2 tras promover FR-038, ocho no tocan el núcleo; el único con impacto (multi-tenant) lo tiene por diseño — el aislamiento por *tenant* es, correctamente, una preocupación transversal que toca dónde se filtran los datos, no la lógica de negocio en sí.
