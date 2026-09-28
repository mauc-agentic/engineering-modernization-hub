# ADR-002 — Proveedor y modelo de inferencia

**Estado:** Aceptado — 2026-09-28. **Supersede** la elección inicial de "Amazon Bedrock con Claude" del brief de trabajo (decisión D-3 de `00-vision.md`).

## Contexto

El presupuesto de inferencia de esta implementación lo cubre el autor, no Wenia. El objetivo es completar el flujo de extremo a extremo — incluidos los cuatro escenarios obligatorios y el bucle de corrección — dentro de ese presupuesto, sin que el costo de tokens obligue a recortar alcance. El caso marca Bedrock como un plus si está bien sustentado, y dice explícitamente que una solución sin Bedrock puede aprobar si demuestra alta calidad en las dimensiones base — es decir, Bedrock no es obligatorio, pero si se usa, la elección concreta del modelo dentro de Bedrock sí debe justificarse.

## Decisión

**Amazon Nova 2 Lite** (`us.amazon.nova-2-lite-v1:0`, *inference profile* de EE. UU.) en **Amazon Bedrock**, accedido con `boto3` mediante la API **Converse** (no `langchain-aws`, ver más abajo).

Verificado el 2026-09-28: cuenta `123456789012`, región `us-east-1`, llamada `converse` con *tool use* exitosa (25 tokens de salida, 912 de entrada en la prueba de humo).

### Precio confirmado (2026-09-28)

| | Precio |
|---|---|
| Tokens de entrada | USD 0.30 / 1M tokens |
| Tokens de salida | USD 2.50 / 1M tokens |
| Ventana de contexto | hasta 1 000 000 de tokens de entrada |
| Modalidades | texto, imágenes, video, *function calling* |

**Presupuesto disponible:** USD 100 en créditos de la cuenta de AWS del autor, para *todo* lo que se monte en la nube (inferencia + cualquier infraestructura de Terraform, ver ADR-006), no solo para tokens.

**Estimación de costo por ejecución completa** (Ejemplo A, `09-escenarios.md` §2, con el intento fallido y la corrección incluidos): del orden de 12 a 15 llamadas al modelo a través de los nodos del grafo, con contexto acotado por archivo (no se satura la ventana de 1 M) — estimado ≈ 150 000 tokens de entrada y ≈ 30 000 de salida por ejecución completa:

```
costo ≈ 150 000 × 0.30 / 1 000 000 + 30 000 × 2.50 / 1 000 000
      ≈ 0.045 + 0.075 = USD 0.12 por ejecución completa
```

Con el límite de costo por solicitud fijado en D-4 (USD 1.00), hay margen de sobra incluso si una ejecución particular duplica o triplica esta estimación (p. ej. por más iteraciones de corrección o un análisis de impacto más largo). Con el presupuesto total de USD 100, esto deja cientos de ejecuciones completas disponibles solo en inferencia — el resto del presupuesto queda para la infraestructura de Terraform (ADR-006).

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Claude (Sonnet/Haiku) en Bedrock | Mayor costo por token que Nova 2 Lite; el caso no exige un modelo concreto, exige que la elección esté sustentada. Con presupuesto propio, Nova 2 Lite maximiza cuántas ejecuciones completas (incluidos escenarios con bucle de corrección) caben en el mismo gasto. |
| Nova Lite (v1, no "2") | Nova 2 Lite es más reciente, con ventana de contexto de un millón de tokens y niveles de esfuerzo de razonamiento configurables (`low`/`medium`/`high`), útiles para escalar el pensamiento solo en los nodos que lo necesitan (análisis de impacto, diagnóstico de errores) y mantenerlo bajo en los nodos mecánicos. |
| Nova Micro | Más barato aún, pero sin *tool use* fiable para flujos con seis herramientas y esquemas anidados en las pruebas preliminares; el riesgo de reintentos por salidas mal formadas (NFR-008) anula el ahorro. |
| `langchain-aws` como capa de acceso | Añade una dependencia y una abstracción intermedia sobre una única llamada (`converse`) que `boto3` ya expone completa, con soporte nativo de *tool use* y conteo exacto de tokens en la respuesta. Para un solo proveedor, la capa de LangChain no aporta valor y sí más superficie que mantener. `ModelPort` ya es la abstracción de portabilidad (NFR-016); no hace falta una segunda. |
| Proveedor externo (OpenAI, Anthropic API directa) | El código del cliente saldría de la red de AWS; el caso mismo señala esto como razón para preferir Bedrock cuando se sustenta. |

## Evaluación

| Dimensión | Evaluación |
|---|---|
| **Seguridad** | La inferencia ocurre dentro de la cuenta y la red de AWS del autor; no hay una clave de API de un tercero que gestionar ni credenciales adicionales que redactar. El acceso se controla con IAM. |
| **Portabilidad** | `ModelPort` (núcleo) es la única interfaz que el agente conoce; cambiar a otro modelo o proveedor es implementar el puerto de nuevo, sin tocar `emh/core` ni `emh/agent` (NFR-016). |
| **Costo** | Nova 2 Lite es la opción de menor costo por token dentro de Bedrock que sostiene *tool use* fiable en las pruebas preliminares; es la variable que más importa dado que el presupuesto es personal. Los niveles de esfuerzo de razonamiento permiten bajar el costo aún más en los nodos que no lo necesitan. |
| **Operación** | Un solo *endpoint* (Converse), sin infraestructura propia que desplegar u operar; los límites de tasa y disponibilidad los gestiona AWS. |
| **Escalabilidad** | El *inference profile* (`us.amazon.nova-2-lite-v1:0`) enruta la carga entre regiones de EE. UU.; suficiente para F1 y para el crecimiento de F2 sin cambio de diseño. |
| **Experiencia del desarrollador** | Ventana de un millón de tokens reduce la necesidad de resumir agresivamente el contexto del repositorio; el conteo de tokens viene en cada respuesta de `converse`, lo que simplifica `PresupuestoMeter` (RN-06) sin tokenizar por separado. |

## Consecuencias

- `emh/models` implementa `ModelPort` con `boto3` puro (`bedrock-runtime`, operación `converse`), sin `langchain-aws` ni `langgraph`'s LLM wrappers.
- El grafo de `emh/agent` (LangGraph) sigue siendo el framework agéntico (ADR-003); LangGraph orquesta nodos y estado, no la llamada al modelo en sí, que pasa por `ModelPort`.
- Los prompts (`emh/agent`) se diseñan cortos y estructurados (salida JSON vía *tool use* siempre que sea posible) para aprovechar el menor costo por token sin perder fiabilidad de parseo.
- Los niveles de esfuerzo de razonamiento se configuran por nodo: `low` para pasos mecánicos (listar archivos, resumir una fuente), `high` para el diagnóstico de errores y la construcción del plan.
- El identificador del modelo permanece en configuración (`C-004` no cambia en ese sentido), solo cambia el valor por defecto.

### Hallazgo de la primera ejecución en vivo (2026-09-28)

Con `reasoningConfig` activo (todos los niveles, incluido `low`), la API Converse de Nova 2 Lite rechaza una conversación cuyo último mensaje sea del asistente (`ValidationException: Assistant prefill is not supported when reasoningConfig type is 'enabled'`). Esto ocurre cuando un bucle de exploración termina con una respuesta de texto libre del modelo en vez de una llamada a herramienta. `emh/agent/runtime.py` cierra siempre la conversación con un turno de usuario sintético antes de la siguiente llamada estructurada (`_asegurar_termina_en_turno_de_usuario`).
