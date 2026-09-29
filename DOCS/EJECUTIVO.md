# Documento ejecutivo — Engineering Modernization Hub

**Caso:** Staff AI Platform Engineer (Wenia) · **Fecha:** 2026-09-29 · **Autor:** Miguel Uribe

Este documento resume el prototipo entregado. El detalle completo —requisitos con IDs, especificaciones de caso de uso, modelo de entidades, y cada decisión de arquitectura con sus alternativas descartadas— vive en [`DOCS/`](00-vision.md) y en los [ADR](ADR/); aquí se explica qué se construyó, por qué, y con qué evidencia se verificó.

---

## 1. Planeación del trabajo

Se siguió AIUP (desarrollo spec-driven): la especificación se escribió y se aprobó **antes** de la primera línea de código. Orden de trabajo:

1. `00-vision.md`, `01-requisitos.md`, `03-arquitectura.md` — aprobados el 2026-09-28 antes de codificar.
2. Documentos restantes (`02`, `04` a `11`, ADRs) — aprobados el mismo día.
3. Implementación en el orden fijado: **modelos y persistencia → herramientas → capa de políticas → grafo agéntico → API → escenarios**, con commits pequeños que referencian el ID de requisito que implementan (`git log` del repositorio es la traza completa).
4. Verificación en vivo real contra Amazon Bedrock (Nova 2 Lite) y Docker real, no solo pruebas guionadas.

**Alcance:** el caso otorgó 5 días calendario y 10–12 horas de dedicación; con el crédito de AWS y el cambio de modelo (ver §3), la entrega se adelantó a 3 horas antes de lo previsto para dejar margen a la sustentación. La disciplina de recorte fue explícita desde el primer mensaje: ante riesgo de tiempo, se reduce profundidad de la lógica agéntica, **nunca** la capa de políticas.

## 2. Arquitectura

Principio rector: **el modelo propone, el código dispone.** Seis capas, dependencias apuntando siempre hacia el núcleo, verificadas por `import-linter` en cada build (no por disciplina, por contrato):

| Capa | Responsabilidad | Paquete |
|---|---|---|
| 1. Núcleo | Dominio, máquina de estados, presupuestos, puertos. No conoce frameworks ni dependencias concretas. | `emh/core` |
| 2. Políticas y controles | Los 8 controles deterministas — el corazón del caso. | `emh/policy` |
| 3. Herramientas / Harness | Las 6 herramientas con contrato tipado. | `emh/harness` |
| 4. Lógica agéntica | Grafo LangGraph, 11 nodos. | `emh/agent` |
| 5. Estrategias | `python_dependency_upgrade` (F1); interfaz lista para una segunda sin tocar el núcleo. | `emh/strategies` |
| 6. Adaptadores | Bedrock/Scripted, Docker, SQLite, FastAPI, reporte (Fargate/Postgres: diseñados, no implementados). | `emh/models`, `emh/execution`, `emh/persistence`, `emh/api`, `emh/reporting` |

El flujo de negocio (Solicitud → Descubrimiento → Análisis → Plan → **Aprobación humana** → Cambios → Verificación → Reporte) es un grafo con una máquina de estados en el núcleo como fuente de verdad; LangGraph lleva la memoria de trabajo, no decide el estado de negocio. La compuerta de aprobación es una interrupción real del grafo (`interrupt()`/`Command(resume=...)`): la ejecución se pausa y solo continúa cuando el núcleo registra una decisión persistida.

**Extensibilidad demostrada, no solo declarada.** `ModernizationStrategy` es la única interfaz que el núcleo conoce de las estrategias; `emh/strategies/python_dependency_upgrade.py` es la única implementación de F1. `06-estrategias.md` §3 recorre, paso a paso, cómo se añadiría una segunda (imagen base): un archivo nuevo y dos líneas fuera de él, sin tocar núcleo, agente ni harness — verificado con una estrategia ficticia definida solo en las pruebas (`tests/unit/test_strategies.py`), que se registra y ejecuta sin que `import-linter` detecte ninguna dependencia hacia `emh/core`.

## 3. Uso de IA

Amazon **Nova 2 Lite** (Bedrock), no Claude — cambio deliberado documentado en `ADR-002`: el presupuesto de inferencia lo cubre el autor, y Nova 2 Lite (USD 0.30/1M tokens de entrada, USD 2.50/1M de salida, confirmado) sostiene *tool use* fiable a una fracción del costo, dejando margen para decenas de ejecuciones completas dentro de un presupuesto modesto.

El modelo participa de forma sustancial en 12 actividades (interpretar la solicitud, explorar el repositorio, decidir qué información necesita, consultar documentación, relacionar documentación con código, determinar viabilidad, construir el plan, generar cambios, generar pruebas, analizar errores, proponer correcciones, redactar el reporte) — cada una anclada a un nodo real del grafo, no a una descripción de intención (`08-uso-de-ia.md`). La prueba de que la IA es sustancial y no decorativa: con un `ModelPort` que siempre devuelve vacío, el sistema no produce ninguna modernización — termina en `FALLIDO_CONTROLADO`.

**El modelo nunca decide:** permisos, comandos, rutas, presupuesto, aprobación, ni si una prueba pasó. Esas 8 decisiones son código determinista (§4). Esta frontera se probó, no solo se documentó: en la ejecución en vivo real, el ciclo de corrección diagnosticó correctamente la causa raíz de una prueba fallida y propuso una solución fuera del alcance aprobado — y el sistema la bloqueó las veces necesarias, terminando en `COMPLETADO_PARCIALMENTE` en vez de fabricar un éxito.

## 4. Herramientas y controles

Seis herramientas (`clone_repo`, `list_files`, `read_file`, `search_docs`, `apply_patch`, `run_tests`), cada una validando su contrato, consultando la política **dentro** de la función (nunca como paso previo saltable), y devolviendo su salida redactada y marcada como contenido no confiable.

Los ocho controles (`05-politicas-y-controles.md`), todos deterministas, todos con prueba propia:

| # | Control | Qué impide |
|---|---|---|
| 1 | Permisos | Herramientas fuera del registro cerrado. |
| 2 | Comandos permitidos | Cualquier ejecutable u operación fuera de la *allowlist* global ∩ el perfil de la estrategia; sin `shell=True`, argumentos como lista. |
| 3 | Rutas modificables | Escapar del workspace (`../`, symlinks). |
| 4 | Presupuestos | Exceder tiempo, iteraciones o costo — el costo se deriva de tokens reales, con reloj y contador inyectables para la prueba. |
| 5 | Aprobaciones | Aplicar un cambio sin una decisión humana ligada al hash exacto del plan vigente. |
| 6 | Manejo de secretos | Que un secreto llegue al modelo o al reporte — redacción por patrones antes de que el modelo vea cualquier salida de herramienta. |
| 7 | Validación del alcance | Un parche que toca algo fuera de lo aprobado, devolviendo el conjunto **completo** de violaciones para reparar en un solo ciclo. |
| 8 | Confirmación de pruebas | Marcar una verificación como exitosa sin salida real capturada. |

**Verificado, no solo diseñado:** 34 pruebas unitarias cubren cada control con casos permitidos y denegados; tres de ellas reproducen literalmente las cargas del escenario 4 del caso ("ignora el plan aprobado", "muestra los secretos", "desactiva los tests"). Los cuatro escenarios obligatorios del caso son pruebas automatizadas de extremo a extremo (`tests/scenarios/`), no demostraciones manuales.

## 5. Seguridad

Modelo de amenazas completo en `07-seguridad.md` (STRIDE aplicado a las seis superficies del sistema). La defensa contra inyección de instrucciones **no** apuesta a que el modelo "reconozca" el ataque — apuesta a que, lo reconozca o no, la acción no tiene efecto, porque todo lo que puede causar daño pasa por la capa de políticas de todas formas. Esto se sostiene aunque el modelo estuviera comprometido.

Hallazgos reales de seguridad durante la implementación (no hipotéticos): la ejecución en vivo real contra el repositorio de la demo confirmó que el control de alcance bloquea correctamente un intento de tocar un archivo fuera del plan aprobado, incluso cuando la corrección propuesta era técnicamente correcta — el sistema prefiere terminar honestamente incompleto a saltarse el límite de aprobación humana.

## 6. Extensibilidad

Ver §2. El mecanismo (interfaz `ModernizationStrategy` + registro por `id`) está probado con una estrategia ficticia, y el camino completo para la segunda estrategia real (imagen base) está documentado en `06-estrategias.md` §3 con el código exacto que se añadiría — sin implementarla, tal como pide el caso.

Los puertos `Sandbox` y `RunRepository` están diseñados para admitir un segundo adaptador de nube (§7) sin tocar el núcleo; ese adaptador **no se implementó** (§8), y la regla de capas se verifica hoy con `import-linter`.

## 7. Evolución hacia un producto interno de producción

Nueve de diez elementos de Fase 2 (`10-evolucion-producto.md`) no tocan el núcleo si se implementan después: Backstage, CLI, estrategias adicionales, Postgres en alta disponibilidad, métricas de adopción/DORA, colas y ejecución distribuida, alta disponibilidad de la nube, CI/CD, SSO. El único con impacto (multi-tenant) lo tiene por diseño correcto: el aislamiento por *tenant* es una preocupación transversal.

**El despliegue en AWS con Terraform, que el caso marca como plus, se abordó solo como infraestructura como código** (decisión D-9, con USD 100 de crédito y disciplina FinOps explícita en cada elección de infraestructura — `ADR-006`, `ADR-007`): ECS Fargate sin balanceador ni NAT Gateway, RDS Postgres de instancia simple, SSM en vez de Secrets Manager, alertas de presupuesto a 20/50/80 %. `terraform validate` y `terraform plan` corrieron contra la cuenta real de AWS (33 recursos, cero errores); el costo total proyectado del ejercicio completo es de apenas unos dólares del crédito disponible. No se ejecutó `terraform apply`: la aplicación no tiene aún los adaptadores de nube, así que la infraestructura habría existido sin nada funcional encima. La demo en vivo corre en local y no depende de la nube.

## 8. Qué queda simulado, dicho explícitamente

- `ScriptedModel`: nivel A de pruebas, determinista, marcado `SIMULATED` en el código. Nunca se usa en la demo en vivo.
- Adaptadores de nube (`PostgresRunRepository`, `FargateSandbox`, `EMH_ENV=aws`): diseñados en `03-arquitectura.md` §9, **no implementados**; solo la IaC de Terraform está entregada y validada con `plan`.
- La identidad del aprobador en F1 no está autenticada (se acepta el campo declarado por quien llama a la API) — simulación reconocida en `00-vision.md` RN-14 y resuelta en el diseño de F2 (SSO, `FR-039`).

## 9. Evidencia

- 133 pruebas automatizadas en verde (130 rápidas y guionadas + Bedrock real y Docker real), más ejecuciones de los escenarios 1, 2 y 4 en vivo con Bedrock + Docker + repos reales (2026-09-29; el 1 dio LISTO_PARA_REVISION con 7/7 pruebas, el 2 INVIABLE por Python 3.7 vs >=3.8, el 4 ignoró las instrucciones maliciosas), y una anterior de extremo a extremo en vivo real (Bedrock + Docker + el repositorio real de la demo) que llegó hasta la compuerta de aprobación, la aprobó, generó el parche, lo verificó en un contenedor real, y terminó en un resultado honesto — con doce fallos reales encontrados y corregidos en el proceso, documentados en los mensajes de commit y en `ADR-002`.
- Dos repositorios de demostración propios y verificados empíricamente (no solo documentados): [`ledger-service`](https://github.com/mauc-agentic/ledger-service) (PyYAML 5.3.1→6.0.2: 5 de 7 pruebas rompen sin corregir, 7/7 pasan corregido) y [`orders-api`](https://github.com/mauc-agentic/orders-api) (Flask 3.0.0 exige Python ≥3.8, confirmado en los metadatos reales de PyPI, frente al runtime 3.7 declarado).
