# Auditoría de alineación — 2026-09-29

Alcance: código, pruebas, infraestructura, documentación AIUP, README, scripts, dashboard y slides. Criterio: un solo vocabulario ([`GLOSARIO.md`](GLOSARIO.md)) y cifras que coinciden con el código.

## Resultado

| Comprobación | Resultado |
|---|---|
| Suite completa (`pytest`) | 205 verdes + 1 omitida a propósito |
| Escenarios y unitarias, 3 corridas consecutivas (NFR-018) | 159 verdes + 1 omitida, las 3 veces |
| `ruff` (reglas de seguridad incluidas) | sin hallazgos |
| `import-linter` (6 capas) | 3 contratos, 0 rotos |
| `terraform fmt` / `validate` | correcto |
| Secretos en el árbol y en el historial | solo *canaries* de las pruebas (`AKIA…` de ejemplo) y los patrones del detector |
| Datos personales en el árbol | ninguno; correo de autor `noreply` |
| Archivos sensibles versionados (`*.tfplan`, `tfstate`, `.env`, `*.pem`) | ninguno |
| Coherencia documentación–código (`tests/docs/`) | 8 pruebas verdes |
| Matriz de trazabilidad | válida y al día (`TRAZABILIDAD.md`) |

## Desviaciones encontradas y cerradas

| # | Hallazgo | Corrección | Requisito |
|---|---|---|---|
| 1 | `search_docs` era la única herramienta que no consultaba `PolicyGate` | `PolicyGate.verificar_dominio_fuente`; prueba AST que exige que **toda** herramienta registrada use la compuerta | NFR-002 |
| 2 | El reporte mostraba el costo como `float` crudo | Redondeo a 4 decimales, con prueba | NFR-010 |
| 3 | La identidad del aprobador no estaba marcada como simulada en el código | Marca `SIMULATED:` en el esquema; prueba de documentación | NFR-019 |
| 4 | Documentos con el sinónimo antiguo de `ejecucion_id`, cifras de pruebas distintas (166/172/174) y «36 filas de FR» | Un término (`ejecucion_id`), una cifra (validada por prueba), recuento real (41 FR) | NFR-029 |
| 5 | Los 71 requisitos seguían `Open`; sin requisitos para traza, dashboard, observabilidad, URL protegida, repo público ni Python 3.12 | Estados actualizados con evidencia; añadidos FR-041–044, NFR-026–029, C-021–022 | AIUP |
| 6 | Faltaban casos de prueba, glosario, índice y la decisión del repositorio público | TC-001…TC-004, `GLOSARIO.md`, `DOCS/README.md`, ADR-009 | AIUP |
| 7 | Casos de uso en `Aprobado` tras implementarse | Pasan a `Done` | AIUP |

## Requisitos en `In Progress` (honestidad)

C-009, C-010, C-011, C-016, C-017 y NFR-011 dependen de la entrega y la sustentación (video, presentación en vivo): no se pueden verificar antes. NFR-029 sigue `In Progress` hasta que la suite documental corra en CI.

## Limitaciones conocidas (no son defectos)

Sin alta disponibilidad (FR-043, Fase 2), sin autenticación real del aprobador (FR-039, Fase 2), sin despliegue continuo (FR-044, Fase 2); el sandbox de la nube conserva salida HTTPS (ADR-006).
