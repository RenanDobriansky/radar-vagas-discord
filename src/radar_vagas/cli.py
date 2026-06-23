"""CLI minima do projeto Radar de Vagas."""

from __future__ import annotations

import argparse

from radar_vagas import __version__


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser da linha de comando para esta fase inicial."""
    parser = argparse.ArgumentParser(
        prog="radar_vagas",
        description="Inicializacao do projeto Radar de Vagas.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI placeholder sem acionar integracoes reais."""
    parser = build_parser()
    parser.parse_args(argv)
    print("Radar de Vagas inicializado. Integracoes reais ainda nao foram implementadas.")
    return 0

