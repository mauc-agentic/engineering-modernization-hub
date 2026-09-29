"""Fixtures compartidas por las pruebas de contrato."""

from __future__ import annotations

import os
import time

import pytest


@pytest.fixture(scope="session")
def postgres_admin_dsn():
    """Postgres 16 efímero en Docker (o el DSN de EMH_TEST_PG_DSN si existe)."""
    dsn = os.environ.get("EMH_TEST_PG_DSN")
    if dsn:
        yield dsn
        return
    try:
        import docker
        import psycopg

        cliente = docker.from_env()
        cliente.ping()
    except Exception:
        pytest.skip("Docker/psycopg no disponibles para Postgres")
    contenedor = cliente.containers.run(
        "postgres:16", environment={"POSTGRES_PASSWORD": "test"}, ports={"5432/tcp": None},
        detach=True, remove=True,
    )
    try:
        for _ in range(60):
            contenedor.reload()
            puerto = (contenedor.ports.get("5432/tcp") or [{}])[0].get("HostPort")
            if puerto:
                try:
                    psycopg.connect(f"postgresql://postgres:test@localhost:{puerto}/postgres", connect_timeout=2).close()
                    break
                except Exception:
                    pass
            time.sleep(1)
        else:
            pytest.skip("Postgres de prueba no arrancó")
        yield f"postgresql://postgres:test@localhost:{puerto}/postgres"
    finally:
        contenedor.stop(timeout=2)
