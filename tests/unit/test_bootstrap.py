"""Regresión del hallazgo en vivo #8 (el bootstrap con sandbox real debe
activar el wheelhouse) y selección de adaptadores por EMH_ENV (NFR-025)."""

import pytest

from emh.bootstrap import Aplicacion


def test_bootstrap_activa_wheelhouse_con_sandbox_real(tmp_path):
    app = Aplicacion(data_dir=tmp_path, modo_simulado=True)
    try:
        assert app.entorno.usar_wheelhouse is True
    finally:
        app.cerrar()


def test_env_local_usa_sqlite_y_docker(tmp_path, monkeypatch):
    monkeypatch.delenv("EMH_ENV", raising=False)
    app = Aplicacion(data_dir=tmp_path, modo_simulado=True)
    try:
        assert type(app.repo).__name__ == "SqliteRunRepository"
        assert type(app.sandbox).__name__ == "DockerSandbox"
    finally:
        app.cerrar()


def test_env_aws_usa_postgres_y_fargate_sin_tocar_el_nucleo(tmp_path, monkeypatch):
    import emh.execution.fargate_sandbox as fs
    import emh.persistence.postgres_repo as pg

    capturado = {}

    class PgFalso:
        def __init__(self, dsn):
            capturado["dsn"] = dsn

    class FargateFalso:
        def __init__(self, **kw):
            capturado["fargate"] = kw

    monkeypatch.setattr(pg, "PostgresRunRepository", PgFalso)
    monkeypatch.setattr(fs, "FargateSandbox", FargateFalso)
    for k, v in {
        "EMH_ENV": "aws", "EMH_DB_HOST": "db.interna", "EMH_DB_NAME": "emh", "EMH_DB_USER": "emh_app",
        "EMH_DB_PASSWORD": "p@ss/word", "EMH_ECS_CLUSTER": "c", "EMH_SANDBOX_TASK_DEFINITION": "td",
        "EMH_SUBNET_IDS": "s1,s2", "EMH_SANDBOX_SECURITY_GROUP": "sg", "EMH_JOBS_BUCKET": "b",
    }.items():
        monkeypatch.setenv(k, v)

    Aplicacion(data_dir=tmp_path, modo_simulado=True)
    assert capturado["dsn"] == "postgresql://emh_app:p%40ss%2Fword@db.interna:5432/emh?sslmode=require"
    assert capturado["fargate"]["subredes"] == ["s1", "s2"]
    assert capturado["fargate"]["bucket"] == "b"


def test_env_aws_sin_variable_obligatoria_falla_con_mensaje_claro(tmp_path, monkeypatch):
    monkeypatch.setenv("EMH_ENV", "aws")
    monkeypatch.delenv("EMH_DB_USER", raising=False)
    with pytest.raises(RuntimeError, match="EMH_DB_USER"):
        Aplicacion(data_dir=tmp_path, modo_simulado=True)


def test_env_invalido_se_rechaza(tmp_path, monkeypatch):
    monkeypatch.setenv("EMH_ENV", "nube")
    with pytest.raises(ValueError, match="EMH_ENV"):
        Aplicacion(data_dir=tmp_path, modo_simulado=True)
