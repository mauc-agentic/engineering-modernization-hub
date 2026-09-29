"""Entidades de dominio.

Traducción directa de DOCS/02-modelo-entidades.md a pydantic. Estos modelos no
saben nada de SQLite, Postgres, FastAPI ni Docker: son datos puros más las
validaciones que ya declaraba el modelo de entidades (RN-11, RN-16).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Enumeraciones (columnas "Values: ..." del modelo de entidades)
# ---------------------------------------------------------------------------


class EstadoEjecucion(StrEnum):
    DESCUBRIMIENTO = "DESCUBRIMIENTO"
    ANALISIS = "ANALISIS"
    PLANEACION = "PLANEACION"
    ESPERANDO_APROBACION = "ESPERANDO_APROBACION"
    APLICANDO_CAMBIOS = "APLICANDO_CAMBIOS"
    VERIFICANDO = "VERIFICANDO"
    CORRIGIENDO = "CORRIGIENDO"
    FINALIZADA = "FINALIZADA"


class ResultadoEjecucion(StrEnum):
    """Los cinco resultados posibles del caso (RN-11)."""

    LISTO_PARA_REVISION = "LISTO_PARA_REVISION"
    COMPLETADO_PARCIALMENTE = "COMPLETADO_PARCIALMENTE"
    BLOQUEADO = "BLOQUEADO"
    FALLIDO_CONTROLADO = "FALLIDO_CONTROLADO"
    PRESUPUESTO_AGOTADO = "PRESUPUESTO_AGOTADO"


class MotivoBloqueo(StrEnum):
    PLAN_RECHAZADO = "PLAN_RECHAZADO"
    INVIABLE = "INVIABLE"
    ACCION_BLOQUEADA = "ACCION_BLOQUEADA"


class VeredictoViabilidad(StrEnum):
    VIABLE = "VIABLE"
    INVIABLE = "INVIABLE"


class EstadoPlan(StrEnum):
    PROPUESTO = "PROPUESTO"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    SUPERSEDIDO = "SUPERSEDIDO"


class DecisionAprobacionValor(StrEnum):
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class TipoDecisionTecnica(StrEnum):
    VIABILIDAD = "VIABILIDAD"
    PLAN = "PLAN"
    CAMBIO = "CAMBIO"
    CORRECCION = "CORRECCION"


class TipoFuente(StrEnum):
    REPOSITORIO = "REPOSITORIO"
    DOCUMENTACION_OFICIAL = "DOCUMENTACION_OFICIAL"
    RELEASE_NOTES = "RELEASE_NOTES"
    GUIA_MIGRACION = "GUIA_MIGRACION"
    REGISTRO_PAQUETES = "REGISTRO_PAQUETES"
    AVISO_SEGURIDAD = "AVISO_SEGURIDAD"
    RESULTADO_COMPILACION_PRUEBAS = "RESULTADO_COMPILACION_PRUEBAS"


class ResultadoVerificacion(StrEnum):
    EXITOSA = "EXITOSA"
    FALLIDA = "FALLIDA"


class OrigenEvento(StrEnum):
    MODELO = "MODELO"
    HERRAMIENTA = "HERRAMIENTA"
    REPOSITORIO = "REPOSITORIO"


class SeveridadEvento(StrEnum):
    INFO = "INFO"
    ADVERTENCIA = "ADVERTENCIA"
    CRITICA = "CRITICA"


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


class Solicitud(BaseModel):
    id: int | None = None
    repositorio_url: str = Field(max_length=500)
    commit_referencia: str = Field(max_length=64)
    estrategia_id: str = Field(max_length=100)
    objetivo: str = Field(max_length=500)
    version_esperada: str = Field(max_length=100)
    restricciones: str | None = Field(default=None, max_length=2000)
    limite_tiempo_segundos: int = Field(gt=0, le=3600)
    limite_iteraciones: int = Field(gt=0, le=10)
    limite_costo_usd: float = Field(gt=0, le=1000)
    solicitante: str = Field(max_length=255)
    creado_en: datetime = Field(default_factory=utcnow)


class Ejecucion(BaseModel):
    id: int | None = None
    solicitud_id: int
    estado: EstadoEjecucion = EstadoEjecucion.DESCUBRIMIENTO
    resultado: ResultadoEjecucion | None = None
    motivo_bloqueo: MotivoBloqueo | None = None
    tokens_consumidos: int = Field(default=0, ge=0)
    costo_estimado_usd: float = Field(default=0.0, ge=0)
    iteraciones_usadas: int = Field(default=0, ge=0)
    iniciado_en: datetime = Field(default_factory=utcnow)
    finalizado_en: datetime | None = None

    @field_validator("resultado")
    @classmethod
    def _resultado_solo_si_finalizada(cls, v, info):
        estado = info.data.get("estado")
        if v is not None and estado != EstadoEjecucion.FINALIZADA:
            raise ValueError("resultado solo puede fijarse cuando estado=FINALIZADA (RN-11)")
        return v

    @field_validator("motivo_bloqueo")
    @classmethod
    def _motivo_solo_si_bloqueado(cls, v, info):
        resultado = info.data.get("resultado")
        if v is not None and resultado != ResultadoEjecucion.BLOQUEADO:
            raise ValueError("motivo_bloqueo solo puede fijarse cuando resultado=BLOQUEADO")
        return v


class AnalisisViabilidad(BaseModel):
    id: int | None = None
    ejecucion_id: int
    veredicto: VeredictoViabilidad
    impacto_detectado: str = Field(max_length=4000)
    evidencia: str = Field(max_length=4000)
    creado_en: datetime = Field(default_factory=utcnow)


class Plan(BaseModel):
    id: int | None = None
    ejecucion_id: int
    version: int = Field(gt=0, le=20)
    hash: str = Field(max_length=64)
    pasos: list[str]
    rutas_declaradas: list[str]
    comandos_verificacion: list[list[str]]
    riesgos: str | None = Field(default=None, max_length=2000)
    estado: EstadoPlan = EstadoPlan.PROPUESTO
    creado_en: datetime = Field(default_factory=utcnow)


class DecisionAprobacion(BaseModel):
    id: int | None = None
    plan_id: int
    plan_hash: str = Field(max_length=64)
    decision: DecisionAprobacionValor
    aprobador: str = Field(max_length=255)
    comentario: str | None = Field(default=None, max_length=2000)
    decidido_en: datetime = Field(default_factory=utcnow)


class DecisionTecnica(BaseModel):
    id: int | None = None
    ejecucion_id: int
    tipo: TipoDecisionTecnica
    descripcion: str = Field(max_length=2000)
    sustentada: bool = False
    creado_en: datetime = Field(default_factory=utcnow)


class Fuente(BaseModel):
    id: int | None = None
    ejecucion_id: int
    tipo: TipoFuente
    url: str = Field(max_length=500)
    hash_contenido: str = Field(max_length=64)
    resumen: str = Field(max_length=2000)
    consultada_en: datetime = Field(default_factory=utcnow)


class CitaFuente(BaseModel):
    id: int | None = None
    decision_tecnica_id: int
    fuente_id: int
    extracto: str | None = Field(default=None, max_length=1000)


class Verificacion(BaseModel):
    id: int | None = None
    ejecucion_id: int
    comando: str = Field(max_length=500)
    codigo_salida: int = Field(ge=0, le=255)
    salida_capturada: str = Field(max_length=4000)
    pruebas_totales: int = Field(default=0, ge=0, le=100000)
    pruebas_exitosas: int = Field(default=0, ge=0, le=100000)
    resultado: ResultadoVerificacion
    ejecutado_en: datetime = Field(default_factory=utcnow)


class EventoSeguridad(BaseModel):
    id: int | None = None
    ejecucion_id: int
    regla: str = Field(max_length=100)
    accion_intentada: str = Field(max_length=2000)
    origen: OrigenEvento
    severidad: SeveridadEvento
    registrado_en: datetime = Field(default_factory=utcnow)


class LlamadaModelo(BaseModel):
    id: int | None = None
    ejecucion_id: int
    nodo: str = Field(max_length=100)
    tokens_entrada: int = Field(ge=0, le=1_000_000)
    tokens_salida: int = Field(ge=0, le=1_000_000)
    duracion_ms: int = Field(ge=0, le=600_000)
    creado_en: datetime = Field(default_factory=utcnow)
