-- Esquema SQLite de EMH (DOCS/02-modelo-entidades.md). ADR-004: SQL directo,
-- sin ORM; el mismo esquema lo reutiliza el adaptador de RDS Postgres
-- (ADR-007) casi sin cambios (tipos JSON -> jsonb, INTEGER PK -> SERIAL).

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS solicitud (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    repositorio_url         TEXT NOT NULL,
    commit_referencia       TEXT NOT NULL,
    estrategia_id           TEXT NOT NULL,
    objetivo                TEXT NOT NULL,
    version_esperada        TEXT NOT NULL,
    restricciones           TEXT,
    limite_tiempo_segundos  INTEGER NOT NULL,
    limite_iteraciones      INTEGER NOT NULL,
    limite_costo_usd        REAL NOT NULL,
    solicitante              TEXT NOT NULL,
    creado_en                TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ejecucion (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id          INTEGER NOT NULL REFERENCES solicitud(id),
    estado                TEXT NOT NULL,
    resultado             TEXT,
    motivo_bloqueo        TEXT,
    tokens_consumidos     INTEGER NOT NULL DEFAULT 0,
    costo_estimado_usd    REAL NOT NULL DEFAULT 0,
    iteraciones_usadas    INTEGER NOT NULL DEFAULT 0,
    iniciado_en           TEXT NOT NULL,
    finalizado_en         TEXT
);

CREATE TABLE IF NOT EXISTS analisis_viabilidad (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id        INTEGER NOT NULL REFERENCES ejecucion(id),
    veredicto           TEXT NOT NULL,
    impacto_detectado   TEXT NOT NULL,
    evidencia           TEXT NOT NULL,
    creado_en           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id            INTEGER NOT NULL REFERENCES ejecucion(id),
    version                 INTEGER NOT NULL,
    hash                    TEXT NOT NULL UNIQUE,
    pasos                   TEXT NOT NULL,             -- JSON: list[str]
    rutas_declaradas        TEXT NOT NULL,              -- JSON: list[str]
    comandos_verificacion   TEXT NOT NULL,               -- JSON: list[list[str]]
    riesgos                 TEXT,
    estado                  TEXT NOT NULL,
    creado_en               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_aprobacion (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id        INTEGER NOT NULL REFERENCES plan(id),
    plan_hash      TEXT NOT NULL,
    decision       TEXT NOT NULL,
    aprobador      TEXT NOT NULL,
    comentario     TEXT,
    decidido_en    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_tecnica (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id   INTEGER NOT NULL REFERENCES ejecucion(id),
    tipo           TEXT NOT NULL,
    descripcion    TEXT NOT NULL,
    sustentada     INTEGER NOT NULL DEFAULT 0,
    creado_en      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fuente (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id      INTEGER NOT NULL REFERENCES ejecucion(id),
    tipo              TEXT NOT NULL,
    url               TEXT NOT NULL,
    hash_contenido    TEXT NOT NULL,
    resumen           TEXT NOT NULL,
    consultada_en     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cita_fuente (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_tecnica_id    INTEGER NOT NULL REFERENCES decision_tecnica(id),
    fuente_id              INTEGER NOT NULL REFERENCES fuente(id),
    extracto               TEXT
);

CREATE TABLE IF NOT EXISTS verificacion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id        INTEGER NOT NULL REFERENCES ejecucion(id),
    comando             TEXT NOT NULL,
    codigo_salida       INTEGER NOT NULL,
    salida_capturada    TEXT NOT NULL,
    pruebas_totales     INTEGER NOT NULL DEFAULT 0,
    pruebas_exitosas    INTEGER NOT NULL DEFAULT 0,
    resultado           TEXT NOT NULL,
    ejecutado_en        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evento_seguridad (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id        INTEGER NOT NULL REFERENCES ejecucion(id),
    regla               TEXT NOT NULL,
    accion_intentada    TEXT NOT NULL,
    origen              TEXT NOT NULL,
    severidad           TEXT NOT NULL,
    registrado_en       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llamada_modelo (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id      INTEGER NOT NULL REFERENCES ejecucion(id),
    nodo              TEXT NOT NULL,
    tokens_entrada    INTEGER NOT NULL,
    tokens_salida     INTEGER NOT NULL,
    duracion_ms       INTEGER NOT NULL,
    creado_en         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traza (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ejecucion_id      INTEGER NOT NULL REFERENCES ejecucion(id),
    tipo              TEXT NOT NULL,
    nombre            TEXT NOT NULL,
    inicio            TEXT NOT NULL,
    duracion_ms       INTEGER NOT NULL,
    ok                INTEGER NOT NULL DEFAULT 1,
    tokens_entrada    INTEGER NOT NULL DEFAULT 0,
    tokens_salida     INTEGER NOT NULL DEFAULT 0,
    detalle           TEXT
);

CREATE INDEX IF NOT EXISTS idx_traza_ejecucion ON traza(ejecucion_id);
CREATE INDEX IF NOT EXISTS idx_ejecucion_solicitud ON ejecucion(solicitud_id);
CREATE INDEX IF NOT EXISTS idx_plan_ejecucion ON plan(ejecucion_id);
CREATE INDEX IF NOT EXISTS idx_verificacion_ejecucion ON verificacion(ejecucion_id);
CREATE INDEX IF NOT EXISTS idx_evento_ejecucion ON evento_seguridad(ejecucion_id);
CREATE INDEX IF NOT EXISTS idx_fuente_ejecucion ON fuente(ejecucion_id);
CREATE INDEX IF NOT EXISTS idx_decision_tecnica_ejecucion ON decision_tecnica(ejecucion_id);
CREATE INDEX IF NOT EXISTS idx_cita_decision ON cita_fuente(decision_tecnica_id);
CREATE INDEX IF NOT EXISTS idx_llamada_ejecucion ON llamada_modelo(ejecucion_id);
