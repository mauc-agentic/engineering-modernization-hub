# ADR-008 — Observabilidad del agente (traza en el producto + OpenTelemetry a CloudWatch)

**Estado:** Aceptado — 2026-09-29. Complementa NFR-014 (trazabilidad de decisiones) y ADR-006 (despliegue).

## Contexto

Con el agente ya desplegado en AWS faltaba poder responder, para cada ejecución: qué nodos corrieron, cuánto tardó cada uno, qué herramientas y qué llamadas al modelo se hicieron, cuántos tokens costaron y dónde falló algo. Lo único disponible eran los logs de la API y las tablas de tokens (con `duracion_ms` guardado siempre en 0, un defecto). Se evaluó alojar el agente en **Amazon Bedrock AgentCore Runtime** para obtener observabilidad "de fábrica".

## Decisión

**No migrar a AgentCore Runtime; sí usar AgentCore Observability**, que según su documentación admite agentes alojados fuera de Runtime mediante el SDK de ADOT. Se añaden dos capas con un único punto de instrumentación (`emh/agent/traza.py::medir`):

**Capa A — traza en el producto.** Cada nodo del grafo, llamada al modelo y llamada a herramienta guarda un tramo (`traza`: tipo, nombre, inicio, duración real, tokens, ok, nota corta) en la misma base de datos (SQLite o Postgres). `GET /ejecuciones/{id}/traza` lo expone y el dashboard lo dibuja como una línea de tiempo con totales. Funciona igual en local y en AWS, sin servicios adicionales, y es parte de la trazabilidad que pide el caso.

**Capa B — OpenTelemetry → CloudWatch (AgentCore Observability).** `medir` emite además un span por tramo con jerarquía `ejecucion > nodo > modelo | herramienta`, atributos `gen_ai.*` (operación, sistema, tokens) y `session.id` (una sesión por ejecución). La imagen de la API instala `aws-opentelemetry-distro` (extra `observabilidad`) y arranca bajo `opentelemetry-instrument` cuando `AGENT_OBSERVABILITY_ENABLED=true`. La configuración (`infra/observabilidad.tf`, `infra/ecs.tf`) sigue la guía oficial para agentes fuera de Runtime: grupo de logs `/aws/bedrock-agentcore/runtimes/emh-agente`, stream `spans`, política de recurso para que X-Ray escriba allí y permisos de telemetría **solo para el rol de la API** (el del sandbox sigue vacío, NFR-004). ADOT además instrumenta automáticamente las llamadas a Bedrock (`chat us.amazon.nova-2-lite-v1:0`) y las peticiones HTTP.

## Privacidad

La traza y los spans guardan **nombres, tiempos, tokens y una nota corta ya redactada; nunca prompts, código del repositorio ni salidas** (una prueba lo verifica, incluido que el mensaje de una excepción no llega al span). Por eso no se activa `AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT`, que dejaría el contenido del modelo en los spans. La pausa de LangGraph por aprobación humana (`GraphInterrupt`) no se cuenta como error.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Migrar a AgentCore Runtime | Reescribe el despliegue (API, aprobación humana, CloudFront/ALB, sandbox, checkpointer) sin mejorar la seguridad; la observabilidad se obtiene sin migrar. Queda como evolución de Fase 2 (memoria e identidad administradas). |
| Solo logs de CloudWatch | No dan jerarquía ni duraciones por nodo, y se pierden en local. |
| ADOT Collector como sidecar | La documentación indica que no está soportado para observabilidad de agentes; solo el SDK. |
| Guardar prompts en la traza | Puede incluir código de clientes o instrucciones maliciosas; contradice el manejo de contenido no confiable. |

## Verificación (2026-09-29, en AWS)

- 174 pruebas verdes: traza de extremo a extremo en el escenario con corrección, contrato del repositorio contra SQLite y Postgres reales, endpoint, y spans con el SDK de OpenTelemetry en memoria (jerarquía, atributos, error, pausa, sin OpenTelemetry).
- Ejecución real 22 por la URL pública: la base de datos registró 18 tramos y CloudWatch recibió 19 spans (los 18 más la raíz `ejecucion`), con tokens en los del modelo.
- La cuenta ya tenía CloudWatch Transaction Search activo (destino CloudWatch Logs, muestreo 100 %), prerrequisito de la guía.

## Hallazgos del despliegue

- El endpoint OTLP de CloudWatch exige que el stream de spans exista; en Runtime lo crea el servicio, fuera de Runtime hay que crearlo (`aws_cloudwatch_log_stream.spans_agente`). `runtime-logs` lo crea el propio exportador.
- El simulador de políticas de IAM dio `implicitDeny` para los ARN de stream aunque la política era correcta; se comprobó con una tarea efímera del mismo rol que los tres endpoints OTLP responden 200. No fiarse del simulador para estos ARN.
- **Limitación conocida:** en la tarea de larga vida el exportador registra unos pocos `403 Forbidden` por minuto (lotes de spans y de logs/métricas) sin pérdida observada en las ejecuciones probadas; con la misma configuración una tarea efímera exporta sin errores. Causa no determinada; se deja como seguimiento.

## Cómo verlo

Consola de CloudWatch → **Application Signals → GenAI Observability** (`https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability`), o Logs Insights sobre `/aws/bedrock-agentcore/runtimes/emh-agente`. En el dashboard del producto: tarjeta "Traza de ejecución".
