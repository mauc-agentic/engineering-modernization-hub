"""`BedrockModel` — Amazon Nova 2 Lite vía la API Converse de `boto3`
(ADR-002). Acceso verificado el 2026-09-28 con una llamada Converse con
*tool use* real."""

from __future__ import annotations

from typing import Any

import boto3

from emh.core.ports import LlamadaHerramientaPropuesta, ModelPort, NivelEsfuerzo, RespuestaModelo  # noqa: F401

MODEL_ID_DEFECTO = "us.amazon.nova-2-lite-v1:0"
REGION_DEFECTO = "us-east-1"


class BedrockModel:
    def __init__(
        self,
        model_id: str = MODEL_ID_DEFECTO,
        region: str = REGION_DEFECTO,
        cliente: Any | None = None,
    ) -> None:
        self._model_id = model_id
        self._cliente = cliente or boto3.client("bedrock-runtime", region_name=region)

    def completar(
        self,
        *,
        mensajes: list[dict[str, Any]],
        sistema: str | None = None,
        herramientas: list[dict[str, Any]] | None = None,
        nivel_esfuerzo: NivelEsfuerzo = "low",
    ) -> RespuestaModelo:
        kwargs: dict[str, Any] = {"modelId": self._model_id, "messages": mensajes}
        if sistema:
            kwargs["system"] = [{"text": sistema}]
        if herramientas:
            kwargs["toolConfig"] = {"tools": herramientas}
        kwargs["additionalModelRequestFields"] = {
            "reasoningConfig": {"type": "enabled", "maxReasoningEffort": nivel_esfuerzo}
        }

        respuesta = self._cliente.converse(**kwargs)

        texto: str | None = None
        llamadas: list[LlamadaHerramientaPropuesta] = []
        for bloque in respuesta["output"]["message"].get("content", []):
            if "text" in bloque:
                texto = (texto or "") + bloque["text"]
            if "toolUse" in bloque:
                tu = bloque["toolUse"]
                llamadas.append(
                    LlamadaHerramientaPropuesta(
                        id=tu["toolUseId"], nombre=tu["name"], argumentos=tu.get("input", {})
                    )
                )

        uso = respuesta.get("usage", {})
        return RespuestaModelo(
            texto=texto, llamadas_herramienta=llamadas,
            tokens_entrada=uso.get("inputTokens", 0), tokens_salida=uso.get("outputTokens", 0),
        )
