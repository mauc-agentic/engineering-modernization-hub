# ADR-004 — Persistencia

**Estado:** Aceptado — 2026-09-28

## Contexto

F1 necesita persistir solicitudes, ejecuciones, planes, decisiones, fuentes, verificaciones, llamadas al modelo y eventos de seguridad (`02-modelo-entidades.md`), con un escritor por ejecución y sin requisito de concurrencia masiva. F2 contempla multi-tenant y carga de producción.

## Decisión

**SQLite**, con acceso exclusivamente a través del puerto `RunRepository` definido en `emh/core`.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Postgres desde F1 | Añade infraestructura (servidor, credenciales, red) que F1 no necesita para un escritor por ejecución; queda como diseño de F2 (FR-034) sin costo de implementarlo ahora. |
| Archivos JSON planos | Sin transacciones: el requisito de que un bloqueo se persista en la misma transacción que la respuesta de bloqueo (NFR-013) se vuelve frágil sin ACID. |
| ORM completo (SQLAlchemy) | Para el volumen de F1, añade una capa de abstracción sobre otra abstracción (`RunRepository` ya es el puerto de portabilidad); SQL parametrizado directo es más fácil de auditar línea por línea, lo cual importa en un sistema con requisitos de auditabilidad estrictos. |

## Evaluación

| Dimensión | Evaluación |
|---|---|
| **Seguridad** | SQL parametrizado (nunca interpolación de cadenas) evita inyección SQL; el archivo de base de datos vive fuera del workspace que ve el modelo, así que el contenido de la base no es alcanzable por el agente salvo a través del puerto. |
| **Portabilidad** | `emh/core` conoce `RunRepository` (interfaz), no SQLite; migrar a Postgres es implementar el puerto de nuevo (NFR-016). |
| **Costo** | Cero infraestructura y cero licencias. |
| **Operación** | Un archivo, sin servicio que levantar; se hace *backup* copiando el archivo. |
| **Escalabilidad** | Un escritor por ejecución es suficiente para la demo (NFR-020 pide 2 ejecuciones concurrentes, no cientos); SQLite con `WAL` soporta eso sin cambios. El límite real de SQLite para producción multi-tenant es la razón por la que Postgres queda en F2. |
| **Experiencia del desarrollador** | Inspeccionar el estado de una demo es `sqlite3 emh.db` sin instalar nada adicional; útil durante la sustentación en vivo. |

## Consecuencias

- `emh/persistence` es el único paquete que importa `sqlite3`.
- El esquema (`02-modelo-entidades.md`) se traduce a tablas con claves foráneas activadas (`PRAGMA foreign_keys = ON`) y modo `WAL` para permitir lectura concurrente con la escritura del *checkpointer* de LangGraph.
- El *checkpointer* de LangGraph puede compartir el mismo archivo `.db` que `RunRepository` sin compartir tablas (ADR-003).
