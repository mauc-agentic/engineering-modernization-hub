"""Adaptador RDS Postgres de `RunRepository` (ADR-007, `EMH_ENV=aws`).

Reutiliza TODA la lógica de `SqliteRunRepository`: las consultas son SQL
estándar parametrizado, así que solo cambia la conexión. `_ConexionPg`
imita la parte de la API de `sqlite3.Connection` que el repositorio usa
(`execute`, `commit`, `close`, `lastrowid`, filas por nombre) y traduce los
marcadores `?` a `%s`. El esquema se deriva de `schema.sql` (única fuente de
verdad) en vez de duplicarlo, para que ambos adaptadores no diverjan.
"""

from __future__ import annotations

import re
import threading
from types import SimpleNamespace

import psycopg
from psycopg.rows import dict_row

from emh.persistence.sqlite_repo import _SCHEMA_PATH, SqliteRunRepository


def esquema_postgres() -> str:
    """`schema.sql` traducido: sin PRAGMA, claves seriales y doble precisión."""
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    sql = re.sub(r"^PRAGMA .*$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)  # los comentarios pueden llevar ';' 
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    return sql.replace(" REAL ", " DOUBLE PRECISION ")


class _ConexionPg:
    """Una conexión con autocommit (cada sentencia es su propia transacción,
    como en el uso de SQLite: nunca queda una transacción abierta colgada) y
    un candado: FastAPI ejecuta las tareas en un pool de hilos."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._candado = threading.Lock()
        self._conn = self._conectar()

    def _conectar(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, autocommit=True, row_factory=dict_row)

    def execute(self, sql: str, params: tuple = ()) -> SimpleNamespace:
        es_insert = sql.lstrip().upper().startswith("INSERT")
        if es_insert and "RETURNING" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        sql = sql.replace("?", "%s")
        with self._candado:
            for intento in (1, 2):
                try:
                    cur = self._conn.execute(sql, params)
                    filas = cur.fetchall() if cur.description else []
                    break
                except psycopg.OperationalError:
                    # conexión caída (reinicio de RDS, tiempo de inactividad): una reconexión
                    if intento == 2:
                        raise
                    self._conn = self._conectar()
        return SimpleNamespace(
            lastrowid=filas[0]["id"] if es_insert and filas else None,
            fetchone=lambda: filas[0] if filas else None,
            fetchall=lambda: filas,
        )

    def executescript(self, script: str) -> None:
        with self._candado:
            for sentencia in (s.strip() for s in script.split(";")):
                if sentencia:
                    self._conn.execute(sentencia)

    def commit(self) -> None:  # autocommit: nada que confirmar
        return None

    def close(self) -> None:
        self._conn.close()


class PostgresRunRepository(SqliteRunRepository):
    """Misma semántica que el adaptador local, contra RDS Postgres."""

    def __init__(self, dsn: str) -> None:
        self._conn = _ConexionPg(dsn)
        self._conn.executescript(esquema_postgres())
