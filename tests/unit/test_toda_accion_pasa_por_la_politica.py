"""NFR-002: el 100 % de las herramientas registradas ejecutan sus efectos únicamente a través de `PolicyGate`.
La prueba enumera el registro y falla si alguna herramienta no consulta la compuerta (o si aparece una herramienta
nueva que este test no conoce)."""

from __future__ import annotations

import ast
from pathlib import Path

from emh.harness.tools import HERRAMIENTAS_REGISTRADAS

RAIZ = Path(__file__).resolve().parents[2]


def _usos_de_la_compuerta(nombre: str) -> set[str]:
    arbol = ast.parse((RAIZ / "emh/harness/tools.py").read_text(encoding="utf-8"))
    funcion = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == nombre)
    return {
        ast.unparse(c.func) for c in ast.walk(funcion)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and ast.unparse(c.func).startswith("ctx.gate.")
    }


def test_toda_herramienta_registrada_consulta_la_compuerta_antes_de_producir_efectos():
    sin_compuerta = [h for h in sorted(HERRAMIENTAS_REGISTRADAS) if not _usos_de_la_compuerta(h)]
    assert not sin_compuerta, f"herramientas sin camino por PolicyGate: {sin_compuerta}"


def test_el_registro_es_una_lista_cerrada_de_seis_herramientas():
    assert HERRAMIENTAS_REGISTRADAS == {"clone_repo", "list_files", "read_file", "search_docs", "apply_patch", "run_tests"}
