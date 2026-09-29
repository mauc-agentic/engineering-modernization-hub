"""NFR-022: la regla de commits trazables, probada como función pura y como script."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("verificar_commits", RAIZ / "scripts" / "verificar_commits.py")
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)


def test_un_commit_de_implementacion_sin_id_se_rechaza():
    assert vc.evaluar("feat(api): endpoint nuevo") is not None
    assert vc.evaluar("fix: corregir el hash\n\nsin referencia") is not None


def test_un_commit_de_implementacion_con_id_se_acepta_en_asunto_o_cuerpo():
    assert vc.evaluar("feat(api): endpoint de traza (NFR-014)") is None
    assert vc.evaluar("fix: hash del plan\n\nImplementa FR-011 y RN-16") is None
    for ident in ("FR-001", "NFR-022", "C-006", "D-9", "ADR-008", "AC-04", "UC-004", "RN-01", "TC-001"):
        assert vc.evaluar(f"test: caso ({ident})") is None, ident


def test_los_commits_que_no_son_de_implementacion_estan_exentos():
    for asunto in ("docs: actualizar README", "chore: dependencias", "ci: nuevo job", "build: imagen", "Merge branch 'x'", 'Revert "feat: x"'):
        assert vc.evaluar(asunto) is None, asunto


def test_el_script_valida_un_rango_real_de_git(tmp_path):
    def git(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], capture_output=True, text=True, check=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a").write_text("1")
    git("add", "a")
    git("commit", "-q", "-m", "docs: base")
    base = git("rev-parse", "HEAD").stdout.strip()
    (tmp_path / "a").write_text("2")
    git("commit", "-qam", "feat: sin id")
    malo = subprocess.run([sys.executable, str(RAIZ / "scripts/verificar_commits.py"), f"{base}..HEAD"], cwd=tmp_path, capture_output=True, text=True)
    assert malo.returncode == 1 and "NFR-022" in malo.stderr
    (tmp_path / "a").write_text("3")
    git("commit", "-qam", "feat: con id (FR-001)")
    git("reset", "-q", "--soft", base)
    git("commit", "-qm", "feat: reescrito (FR-001)")
    bueno = subprocess.run([sys.executable, str(RAIZ / "scripts/verificar_commits.py"), f"{base}..HEAD"], cwd=tmp_path, capture_output=True, text=True)
    assert bueno.returncode == 0, bueno.stderr
