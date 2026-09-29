"""NFR-008: el cliente de Bedrock reintenta errores transitorios (límite de tasa, 5xx) con espera exponencial."""


def test_el_cliente_bedrock_reintenta_con_espera_exponencial(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secreto")
    from emh.models.bedrock import REINTENTOS_TRANSITORIOS, BedrockModel

    assert REINTENTOS_TRANSITORIOS == 3
    # En botocore `max_attempts` cuenta REINTENTOS: 3 reintentos = 4 intentos en total.
    # Modo `standard` = espera exponencial con jitter.
    retries = BedrockModel(region="us-east-1")._cliente.meta.config.retries
    assert retries["mode"] == "standard"
    assert retries["total_max_attempts"] == 4
