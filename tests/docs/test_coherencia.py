"""NFR-029: la documentación habla el mismo idioma que el código. Estas pruebas fallan si una cifra, un
nombre o un ID de la documentación se desvía de la realidad (SIMULATED de la identidad del aprobador incluido, NFR-019)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from emh.harness.tools import HERRAMIENTAS_REGISTRADAS

RAIZ = Path(__file__).resolve().parents[2]
DOCS = sorted((RAIZ / "DOCS").rglob("*.md")) + [RAIZ / "README.md", RAIZ / "CONTRIBUTING.md"]
CATALOGO = (RAIZ / "DOCS/01-requisitos.md").read_text(encoding="utf-8")
IDS_DEL_CATALOGO = set(re.findall(r"^\| ((?:FR|NFR|C)-\d+)", CATALOGO, re.M))
ESTADOS_REQ = {"Open", "In Progress", "Implemented", "Verified", "Deferred", "Rejected"}


def test_los_documentos_no_usan_sinonimos_prohibidos_del_glosario():
    for doc in DOCS:
        if doc.name == "GLOSARIO.md":
            continue
        assert "run_id" not in doc.read_text(encoding="utf-8"), f"{doc.name}: usa `run_id`; el término es `ejecucion_id`"


def test_todo_id_citado_en_la_documentacion_existe_en_el_catalogo():
    for doc in DOCS:
        if doc.name in ("00-vision.md", "01-requisitos.md"):
            continue
        for rid in set(re.findall(r"\b(?:FR|NFR|C)-\d{3}\b", doc.read_text(encoding="utf-8"))):
            assert rid in IDS_DEL_CATALOGO, f"{doc.name} cita {rid}, que no existe en 01-requisitos.md"


def test_los_estados_de_requisitos_son_del_vocabulario_aiup():
    estados = re.findall(r"^\| (?:FR|NFR|C)-\d+ .*\| ([A-Za-z ]+) \|$", CATALOGO, re.M)
    assert estados and set(estados) <= ESTADOS_REQ


def test_las_cifras_del_readme_coinciden_con_el_codigo():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    recogidas = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--ignore=tests/docs"],
        cwd=RAIZ, capture_output=True, text=True, check=True,
    ).stdout
    total = int(re.search(r"(\d+) tests? collected", recogidas).group(1)) + len(
        re.findall(r"^def test_", Path(__file__).read_text(encoding="utf-8"), re.M))
    m = re.search(r"(\d+) pruebas verdes \(más (\d+) omitidas? a propósito\)", readme)
    assert m, "el README debe decir «N pruebas verdes (más M omitida a propósito)»"
    assert int(m.group(1)) + int(m.group(2)) == total, "cifra de pruebas del README desactualizada"
    assert len(HERRAMIENTAS_REGISTRADAS) == 6


def test_la_identidad_del_aprobador_esta_marcada_como_simulada():
    assert "SIMULATED" in (RAIZ / "emh/api/schemas.py").read_text(encoding="utf-8")


def test_cada_adr_declara_estado_y_cada_caso_de_uso_un_estado_valido():
    for adr in (RAIZ / "DOCS/ADR").glob("ADR-*.md"):
        assert re.search(r"^\*\*Estado:\*\* (Aceptado|Propuesto|Sustituido)", adr.read_text(encoding="utf-8"), re.M), adr.name
    for uc in (RAIZ / "DOCS/04-casos-de-uso").glob("UC-*.md"):
        assert re.search(r"^\*\*Estado:\*\* (Draft|Reviewed|Approved|Implemented|Tested|Done|Obsolete)\b",
                         uc.read_text(encoding="utf-8"), re.M), uc.name


def test_la_matriz_de_trazabilidad_es_valida_y_esta_al_dia():
    r = subprocess.run([sys.executable, "scripts/generar_trazabilidad.py", "--comprobar"],
                       cwd=RAIZ, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_todo_adr_y_caso_de_prueba_esta_en_el_indice():
    indice = (RAIZ / "DOCS/README.md").read_text(encoding="utf-8")
    for f in [*(RAIZ / "DOCS/ADR").glob("ADR-*.md"), *(RAIZ / "DOCS/13-casos-de-prueba").glob("TC-*.md")]:
        assert f.name in indice, f"{f.name} no está en DOCS/README.md"
