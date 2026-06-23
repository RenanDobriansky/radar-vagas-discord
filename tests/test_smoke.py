"""Testes smoke da etapa de inicializacao."""

from __future__ import annotations

import subprocess
import sys

import radar_vagas


def test_package_import_exposes_version() -> None:
    assert radar_vagas.__version__ == "0.1.0"


def test_python_module_entrypoint_runs_successfully() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "radar_vagas"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Radar de Vagas inicializado" in result.stdout
