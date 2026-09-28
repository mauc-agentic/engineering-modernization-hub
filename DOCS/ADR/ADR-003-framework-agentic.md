# ADR-003 — Framework agéntico

**Estado:** Aceptado — 2026-09-28

## Contexto

El flujo de negocio (Solicitud → Descubrimiento → Análisis → Plan → **Aprobación** → Cambios → Pruebas → Reporte) es, en esencia, una máquina de estados con una compuerta de intervención humana y un bucle de corrección acotado. Necesita poder **interrumpirse** en la compuerta de aprobación y **reanudarse** más tarde con la decisión del desarrollador, potencialmente tras reiniciar el proceso.

## Decisión

**LangGraph** para `emh/agent`, con un *checkpointer* SQLite para persistir el estado de trabajo entre interrupciones.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Cadena de prompts hecha a mano (sin framework) | Reimplementa lo que LangGraph ya resuelve: interrupción/reanudación, *checkpointing* y aristas condicionales. Mayor riesgo de errores en la parte más sensible del sistema (el punto de aprobación). |
| CrewAI / AutoGen (equipos de agentes) | Están pensados para varios agentes colaborando con roles; el problema aquí es un flujo con estructura fija y una sola cadena de razonamiento por nodo, no una negociación entre agentes. Añadirían un modelo mental innecesario. |
| Un bucle `while` propio con banderas de estado | Sin `interrupt`/`resume` nativo, la pausa de aprobación exigiría persistencia manual de la pila de ejecución; LangGraph ya lo resuelve con su *checkpointer*. |

## Evaluación

| Dimensión | Evaluación |
|---|---|
| **Seguridad** | El grafo solo mueve datos y decide qué nodo sigue; no ejecuta nada por sí mismo. Cada nodo que produce un efecto pasa por `emh/harness` → `emh/policy`, fuera de LangGraph. LangGraph no es, ni necesita ser, un componente de seguridad. |
| **Portabilidad** | El núcleo (`emh/core`) no importa LangGraph; solo implementa el puerto `AgentRunner` sobre él en `emh/agent`. Cambiar de framework agéntico no toca el dominio (NFR-016). |
| **Costo** | Sin costo de licencia. El costo real es de tokens (ADR-002), no del framework. |
| **Operación** | El *checkpointer* SQLite comparte el mismo archivo que `RunRepository`, sin infraestructura adicional en F1. |
| **Escalabilidad** | El *checkpointer* de LangGraph es intercambiable (Postgres, Redis) para F2 sin rediseñar el grafo. |
| **Experiencia del desarrollador** | Aristas condicionales explícitas hacen que el bucle de corrección y la compuerta de aprobación sean legibles como grafo (ver `03-arquitectura.md` §4), en vez de banderas dispersas en código imperativo. |

## Consecuencias

- `emh/agent` es el único paquete que importa `langgraph`.
- La máquina de estados de negocio vive en `emh/core` (RN-11); el grafo de LangGraph pide transiciones, no las decide (ver `03-arquitectura.md` §3.1). Esto evita depender de LangGraph como fuente de verdad del estado del negocio, y hace trivial migrar de framework agéntico si hiciera falta.
- La compuerta de aprobación (UC-003) se implementa con un nodo que interrumpe el grafo (`interrupt`) hasta que el núcleo registra una `DECISION_APROBACION`; la API expone el `resume`.
