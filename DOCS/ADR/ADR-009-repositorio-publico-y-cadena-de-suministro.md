# ADR-009 — Repositorio público y seguridad de la cadena de suministro

**Estado:** Aceptado — 2026-09-29

## Contexto
El entregable se revisa desde GitHub y el caso pide no exponer secretos. Un repositorio público multiplica el riesgo (credenciales, datos personales, dependencias comprometidas) y exige que solo el propietario pueda cambiar `main`.

## Decisión
Repositorio **público con licencia MIT**, historial reescrito antes de publicar (sin credenciales ni datos personales; correo de autor `noreply`), y controles del propio repositorio: rulesets en `main` (sin force-push ni borrado, historial lineal, PR con CI verde, solo propietario), escaneo de secretos con *push protection*, Dependabot (sin cambiar Python mayor/menor), CodeQL, acciones de CI fijadas por hash, token de workflow de solo lectura, CODEOWNERS, `SECURITY.md`, `CONTRIBUTING.md`, código de conducta y plantilla de PR. Los commits referencian IDs del catálogo (hook `commit-msg` y job `commits`).

## Consecuencias
- Cualquiera ve la arquitectura y sus limitaciones documentadas; no hay secretos que ver.
- `*.tfplan` y estado de Terraform se ignoran (contienen datos de cuenta).
- Requisitos: NFR-022, NFR-028, C-022.
