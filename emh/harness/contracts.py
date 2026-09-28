"""Contratos de las seis herramientas (DOCS/03-arquitectura.md §3.3).

Cada herramienta valida sus argumentos contra un esquema pydantic ANTES de
cualquier efecto (control 1). Ningún argumento llega como cadena libre que
se interprete después: los tipos aquí son el contrato completo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


class ArgsCloneRepo(BaseModel):
    repositorio_url: str = Field(max_length=500)
    commit_referencia: str = Field(max_length=64)


class ArgsListFiles(BaseModel):
    ruta: str = Field(default=".", max_length=500)


class ArgsReadFile(BaseModel):
    ruta: str = Field(max_length=500)


class ArgsSearchDocs(BaseModel):
    consulta: str = Field(max_length=500)
    dominio: str = Field(max_length=200)


class CambioArchivoArgs(BaseModel):
    ruta: str = Field(max_length=500)
    operacion: Literal["crear", "modificar", "borrar"]
    contenido_nuevo: str | None = None


class ArgsApplyPatch(BaseModel):
    cambios: list[CambioArchivoArgs]


class ArgsRunTests(BaseModel):
    comando: list[str]


@dataclass
class ResultadoHerramienta:
    ok: bool
    contenido: str = ""
    motivo_rechazo: str | None = None
    regla: str | None = None
    detalles: list[str] = field(default_factory=list)
    no_confiable: bool = True  # RN-09: todo contenido externo es dato, no instrucción
