# Cómo contribuir

Gracias por el interés. Este es un prototipo mantenido por una sola persona, así que las
contribuciones se revisan con mejor esfuerzo.

## Flujo

1. Haz un *fork* y crea una rama desde `main`.
2. Haz cambios pequeños con su prueba. Para probar en local:
   ```bash
   uv venv --python 3.12 && uv pip install -e ".[dev,postgres]" && source .venv/bin/activate
   ruff check emh sandbox tests && lint-imports && pytest -q -m "not live"
   ```
3. Abre un *pull request* contra `main`. El CI (`pruebas` y `terraform`) debe pasar; `main` no
   admite *force-push* ni historial no lineal.

## Reglas que no se negocian

- **Los 8 controles deterministas** (`DOCS/05-politicas-y-controles.md`) no se debilitan: el
  modelo propone, el código dispone. Un cambio que le dé al modelo una decisión que hoy toma el
  código no se acepta.
- **Cero secretos, correos personales o IDs de cuenta** en código, documentos, planes de
  Terraform ni mensajes de commit. Usa placeholders (`tu-correo@example.com`, `123456789012`).
- Lo que produce el modelo, los repositorios y las fuentes externas son **contenido no confiable**.
- Los cambios en `infra/` se acompañan de `terraform fmt`, `terraform validate` y el plan revisado.

## Vulnerabilidades

No abras un issue público: sigue [`SECURITY.md`](SECURITY.md).

## Commits trazables

Cada commit de implementación cita un ID de `DOCS/01-requisitos.md` (p. ej. `fix(politica): … (NFR-002)`). Activa el hook local una vez:

```bash
cp scripts/hooks/commit-msg .git/hooks/commit-msg && chmod +x .git/hooks/commit-msg
```

El job `commits` de CI hace la misma comprobación. Antes de abrir un PR: `pytest`, `ruff check .`, `lint-imports` y, si tocaste `DOCS/`, `python scripts/generar_trazabilidad.py`.
