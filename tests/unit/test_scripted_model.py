from __future__ import annotations

import pytest

from emh.core.ports import RespuestaModelo
from emh.models.scripted import ScriptedModel


def test_devuelve_respuestas_en_orden():
    respuestas = [
        RespuestaModelo(texto="uno", llamadas_herramienta=[], tokens_entrada=1, tokens_salida=1),
        RespuestaModelo(texto="dos", llamadas_herramienta=[], tokens_entrada=1, tokens_salida=1),
    ]
    modelo = ScriptedModel(respuestas)
    assert modelo.completar(mensajes=[]).texto == "uno"
    assert modelo.completar(mensajes=[]).texto == "dos"


def test_agotar_el_guion_lanza_indexerror():
    modelo = ScriptedModel([RespuestaModelo(texto="x", llamadas_herramienta=[], tokens_entrada=1, tokens_salida=1)])
    modelo.completar(mensajes=[])
    with pytest.raises(IndexError):
        modelo.completar(mensajes=[])


def test_registra_mensajes_recibidos_para_inspeccion():
    modelo = ScriptedModel([RespuestaModelo(texto="x", llamadas_herramienta=[], tokens_entrada=1, tokens_salida=1)])
    modelo.completar(mensajes=[{"role": "user", "content": [{"text": "hola"}]}])
    assert modelo.mensajes_recibidos[0][0]["content"][0]["text"] == "hola"
