"""Control 6 — Manejo de secretos (DOCS/05-politicas-y-controles.md §6).

Redacción por patrones de TODA salida de herramienta antes de que llegue al
modelo. Es una transformación pura (texto -> texto), no una Decision de
permitir/denegar: por eso vive aparte de `gate.py`.
"""

from __future__ import annotations

import re

_MARCADOR = "[REDACTADO]"

# Cada patrón cubre un tipo de secreto concreto (RN-07, NFR-001). Lista
# propia, no una librería de terceros -- decisión justificada en
# DOCS/05-politicas-y-controles.md, sección "Redacción de secretos".
_PATRONES: list[re.Pattern[str]] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9\-_.=]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    # Variables de entorno con nombres sensibles seguidas de un valor
    re.compile(
        r"(?im)^\s*[A-Z0-9_]*(SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|PRIVATE)[A-Z0-9_]*\s*=\s*\S+"
    ),
    re.compile(r"(?i)://[^:\s]+:[^@\s]+@"),  # credenciales en cadenas de conexión (user:pass@host)
]

# Nota deliberada: no hay un patrón genérico de "blob base64 largo". El caso
# pide una lista acotada y auditable (control 6); un patrón tan amplio
# redactaría también hashes de git, de lockfiles, etc., dañando la lectura
# legítima del repositorio sin ganar cobertura real de secretos.


def redactar(texto: str) -> str:
    """Devuelve `texto` con todo patrón de secreto reemplazado por un
    marcador. Idempotente y sin efectos secundarios."""
    resultado = texto
    for patron in _PATRONES:
        resultado = patron.sub(_MARCADOR, resultado)
    return resultado


def contiene_secreto(texto: str) -> bool:
    return any(p.search(texto) for p in _PATRONES)
