#!/usr/bin/env python3
"""Genera DOCS/TRAZABILIDAD.md desde DOCS/trazabilidad.yaml y valida la matriz (NFR-029).

Uso: python scripts/generar_trazabilidad.py [--comprobar]
  --comprobar  no escribe; sale con 1 si la matriz es inválida o el .md no está al día.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
FILA = re.compile(r"^\| ((?:FR|NFR|C)-\d+) \| (.*?) \|.*\| (Open|In Progress|Implemented|Verified|Deferred|Rejected) \|$")


def catalogo() -> dict[str, tuple[str, str]]:
    filas = {}
    for linea in (RAIZ / "DOCS/01-requisitos.md").read_text(encoding="utf-8").splitlines():
        m = FILA.match(linea)
        if m:
            filas[m.group(1)] = (m.group(2), m.group(3))
    return filas


def problemas(cat: dict, matriz: dict) -> list[str]:
    malos = []
    for rid, (_, estado) in cat.items():
        if estado in ("Verified", "Implemented") and rid.split("-")[0] != "C" and rid not in matriz and rid != "NFR-011":
            malos.append(f"{rid} está {estado} y no tiene entrada en trazabilidad.yaml")
    for rid, datos in matriz.items():
        if rid not in cat:
            malos.append(f"{rid} está en trazabilidad.yaml pero no en 01-requisitos.md")
        if not datos.get("pruebas"):
            malos.append(f"{rid} no declara pruebas")
        for ruta in [*datos.get("codigo", []), *datos.get("pruebas", [])]:
            if not (RAIZ / ruta).exists():
                malos.append(f"{rid}: no existe {ruta}")
    return malos


def render(cat: dict, matriz: dict) -> str:
    out = ["# Trazabilidad requisito → código → prueba", "",
           "> Generado por `scripts/generar_trazabilidad.py` desde `DOCS/trazabilidad.yaml`. No editar a mano.", "",
           "| ID | Título | Estado | Código | Pruebas |", "|---|---|---|---|---|"]
    for rid, (titulo, estado) in cat.items():
        d = matriz.get(rid, {})
        cod = "<br>".join(f"`{c}`" for c in d.get("codigo", [])) or "—"
        pru = "<br>".join(f"`{c}`" for c in d.get("pruebas", [])) or "—"
        out.append(f"| {rid} | {titulo} | {estado} | {cod} | {pru} |")
    out += ["", "Los requisitos `C-*` (restricciones), NFR-011, NFR-029 y los `Deferred` (Fase 2) no tienen prueba automática por diseño."]
    return "\n".join(out) + "\n"


def main() -> int:
    cat = catalogo()
    matriz = yaml.safe_load((RAIZ / "DOCS/trazabilidad.yaml").read_text(encoding="utf-8"))["requisitos"]
    malos = problemas(cat, matriz)
    destino = RAIZ / "DOCS/TRAZABILIDAD.md"
    texto = render(cat, matriz)
    if "--comprobar" in sys.argv:
        if not destino.exists() or destino.read_text(encoding="utf-8") != texto:
            malos.append("DOCS/TRAZABILIDAD.md no está al día: ejecuta scripts/generar_trazabilidad.py")
    elif not malos:
        destino.write_text(texto, encoding="utf-8")
    for m in malos:
        print("ERROR:", m)
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
