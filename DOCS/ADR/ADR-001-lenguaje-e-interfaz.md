# ADR-001 — Lenguaje e interfaz de F1

**Estado:** Aceptado — 2026-09-28

## Contexto

El caso pide justificar la elección de lenguaje e interfaz considerando seguridad, portabilidad, costo, operación, escalabilidad y experiencia del desarrollador (DX), y ordena las interfaces de menor a mayor complejidad: API, CLI, Backstage.

## Decisión

**Python 3.11+** como lenguaje, con **FastAPI** como interfaz de F1 (API REST con OpenAPI).

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| TypeScript/Node.js | El ecosistema de LangGraph y de SDKs de Bedrock es más maduro en Python; el equipo de plataforma objetivo (ingeniería) ya usa Python en tooling interno. |
| CLI como interfaz de F1 | El caso ordena API antes que CLI por complejidad; una API deja la puerta abierta a que la CLI y Backstage (F2) sean clientes delgados sobre ella, sin reimplementar lógica. |
| Flask/Django para la API | FastAPI genera OpenAPI automáticamente (NFR-021) y valida con pydantic, que ya se usa para los contratos de herramientas y del núcleo — un solo sistema de tipos en todo el proyecto. |

## Evaluación

| Dimensión | Evaluación |
|---|---|
| **Seguridad** | pydantic valida cada payload en el borde de la API antes de que llegue al dominio; reduce errores de deserialización que podrían convertirse en vectores de inyección. |
| **Portabilidad** | Python corre igual en el host de desarrollo, en CI y en el contenedor; sin dependencias de plataforma. |
| **Costo** | Sin licencias; el costo del prototipo es casi enteramente inferencia (ver ADR-002). |
| **Operación** | Un solo proceso ASGI (uvicorn) para F1; sin infraestructura adicional que operar. |
| **Escalabilidad** | FastAPI + ASGI soporta *async* nativo, útil cuando F2 mueva la ejecución a colas; no es el cuello de botella de F1 (lo es el contenedor Docker por ejecución). |
| **Experiencia del desarrollador** | OpenAPI generado automáticamente da al desarrollador solicitante una forma explorable de la API sin documentación manual (NFR-021). |

## Consecuencias

- `emh/api` depende de FastAPI y pydantic; el resto de `emh` no depende de ninguno de los dos salvo a través de los modelos de dominio compartidos (pydantic también se usa en `emh/core` para las entidades, lo cual es una dependencia de librería, no de framework).
- CLI y Backstage (F2) se diseñan como clientes de esta misma API (`10-evolucion-producto.md`).
