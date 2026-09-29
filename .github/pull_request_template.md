## Qué cambia y por qué

## Checklist de seguridad
- [ ] No incluye secretos, credenciales, correos ni IDs de cuenta (usar placeholders).
- [ ] No debilita ninguno de los 8 controles deterministas (`DOCS/05-politicas-y-controles.md`).
- [ ] Lo que el modelo genera sigue tratándose como contenido no confiable.
- [ ] `ruff check`, `lint-imports` y `pytest -m "not live"` pasan.
- [ ] Si toca `infra/`: `terraform fmt`, `terraform validate` y el plan revisado.
