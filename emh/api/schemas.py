"""Esquemas de la API (DOCS/00-vision.md §2, NFR-021)."""

from __future__ import annotations

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
    plan_id: int
    plan_hash: str = Field(max_length=64)
    decision: str = Field(examples=["APROBADO", "RECHAZADO"])
    aprobador: str = Field(examples=["dev:ana@example.com"], max_length=255)
    comentario: str | None = Field(default=None, max_length=2000)


class ErrorRespuesta(BaseModel):
    codigo: str
    mensaje: str
    run_id: int | None = None
