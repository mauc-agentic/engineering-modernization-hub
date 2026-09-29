"""Esquemas de la API (DOCS/00-vision.md §2, NFR-021)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SolicitudEntrada(BaseModel):
    repositorio_url: str = Field(examples=["https://github.com/example/ledger-service"], max_length=500)
    commit_referencia: str = Field(examples=["a1b2c3d"], max_length=64)
    estrategia_id: str = Field(examples=["python_dependency_upgrade"], max_length=100)
    objetivo: str = Field(examples=["Actualizar PyYAML de 5.3.1 a 6.0.2"], max_length=500)
    version_esperada: str = Field(examples=["PyYAML==6.0.2"], max_length=100)
    restricciones: str | None = Field(default=None, max_length=2000)
    limite_tiempo_segundos: int = Field(examples=[720], gt=0, le=3600)
    limite_iteraciones: int = Field(examples=[3], gt=0, le=10)
    limite_costo_usd: float = Field(examples=[1.0], gt=0, le=1000)
    solicitante: str = Field(examples=["dev:ana@example.com"], max_length=255)


class SolicitudRespuesta(BaseModel):
    ejecucion_id: int
    estado: str


class AprobacionEntrada(BaseModel):
    """SIMULATED: `aprobador` es una identidad DECLARADA por quien llama, sin autenticación (RN-14).
    Se registra tal cual en la decisión; la identidad verificada llega con SSO en la Fase 2 (FR-039)."""

    plan_id: int
    plan_hash: str = Field(max_length=64)
    decision: Literal["APROBADO", "RECHAZADO"]
    aprobador: str = Field(examples=["dev:ana@example.com"], max_length=255)
    comentario: str | None = Field(default=None, max_length=2000)


class ErrorRespuesta(BaseModel):
    """Formato ÚNICO de error de toda la API (NFR-021): siempre viaja dentro de `detail`."""

    codigo: str = Field(examples=["NO_ENCONTRADO"])
    mensaje: str
    ejecucion_id: int | None = None
    campos: list[str] | None = Field(default=None, description="Campos inválidos, solo en errores de validación.")


class ErrorHTTP(BaseModel):
    detail: ErrorRespuesta


class EjecucionRespuesta(BaseModel):
    ejecucion_id: int
    estado: str = Field(examples=["ESPERANDO_APROBACION"])
    resultado: str | None = Field(default=None, examples=["LISTO_PARA_REVISION"])
    motivo_bloqueo: str | None = None
    iteraciones_usadas: int
    costo_estimado_usd: float


class AnalisisViabilidadRespuesta(BaseModel):
    veredicto: str = Field(examples=["VIABLE"])
    impacto_detectado: str
    evidencia: str


class PlanRespuesta(BaseModel):
    plan_id: int
    hash: str
    estado: str = Field(examples=["PROPUESTO"])
    pasos: list[str]
    rutas_declaradas: list[str]
    comandos_verificacion: list[list[str]]
    riesgos: str | None = None


class AprobacionRespuesta(BaseModel):
    ejecucion_id: int
    decision_registrada: str


class VerificacionRespuesta(BaseModel):
    comando: str
    codigo_salida: int
    resultado: str = Field(examples=["EXITOSA"])
    pruebas_totales: int
    pruebas_exitosas: int
    salida_capturada: str
    ejecutado_en: str


class EventoSeguridadRespuesta(BaseModel):
    regla: str
    accion_intentada: str
    origen: str = Field(examples=["MODELO"])
    severidad: str = Field(examples=["CRITICA"])
    registrado_en: str


class TramoRespuesta(BaseModel):
    tipo: Literal["nodo", "modelo", "herramienta"]
    nombre: str
    ok: bool
    duracion_ms: int
    desplazamiento_ms: int
    tokens_entrada: int
    tokens_salida: int
    detalle: str | None = None


class ResumenTrazaRespuesta(BaseModel):
    duracion_total_ms: int
    llamadas_modelo: int
    llamadas_herramienta: int
    tokens_entrada: int
    tokens_salida: int
    errores: int


class TrazaRespuesta(BaseModel):
    tramos: list[TramoRespuesta]
    resumen: ResumenTrazaRespuesta


class ReporteRespuesta(BaseModel):
    """Reporte en dos partes (hechos + narrativa); la forma exacta la fija `ReportRenderer`."""

    model_config = {"extra": "allow"}

    ejecucion: dict[str, Any]
