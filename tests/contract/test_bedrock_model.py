"""Nivel B — contra Amazon Bedrock REAL (Nova 2 Lite, ADR-002). Requiere
credenciales AWS válidas; se salta si no las hay."""

from __future__ import annotations

import boto3
import pytest
from botocore.exceptions import NoCredentialsError

from emh.models.bedrock import BedrockModel


def _credenciales_disponibles() -> bool:
    try:
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _credenciales_disponibles(), reason="sin credenciales AWS"),
]


def test_completar_sin_herramientas():
    modelo = BedrockModel()
    r = modelo.completar(
        mensajes=[{"role": "user", "content": [{"text": "Responde solo con la palabra: listo"}]}],
        nivel_esfuerzo="low",
    )
    assert r.texto is not None
    assert r.tokens_entrada > 0
    assert r.tokens_salida > 0


def test_completar_con_tool_use_real():
    herramientas = [
        {
            "toolSpec": {
                "name": "read_file",
                "description": "Lee un archivo del repositorio",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"ruta": {"type": "string"}},
                        "required": ["ruta"],
                    }
                },
            }
        }
    ]
    modelo = BedrockModel()
    r = modelo.completar(
        mensajes=[{"role": "user", "content": [{"text": "Lee el archivo requirements.txt del repositorio."}]}],
        herramientas=herramientas,
        nivel_esfuerzo="low",
    )
    assert len(r.llamadas_herramienta) == 1
    assert r.llamadas_herramienta[0].nombre == "read_file"
    assert "ruta" in r.llamadas_herramienta[0].argumentos
