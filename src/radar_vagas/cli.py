"""CLI minima do projeto Radar de Vagas."""

from __future__ import annotations

import argparse
import json

from radar_vagas import __version__
from radar_vagas.config import load_runtime_settings
from radar_vagas.providers.base import ProviderError
from radar_vagas.providers.jooble import JoobleProvider
from radar_vagas.providers.remotive import RemotiveProvider


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
    parser.add_argument(
        "--provider",
        choices=["jooble", "remotive"],
        help="Executa um diagnostico simples do provider informado.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa a busca sem integrar com Discord.",
    )
    parser.add_argument(
        "--term",
        default="Analista de Dados",
        help="Termo da consulta do provider.",
    )
    parser.add_argument(
        "--location",
        default="Curitiba",
        help="Localizacao da consulta do provider.",
    )
    parser.add_argument("--page", type=int, default=1, help="Pagina da consulta.")
    parser.add_argument(
        "--results-per-page",
        type=int,
        default=20,
        help="Quantidade desejada de resultados por pagina.",
    )
    parser.add_argument(
        "--category",
        default="",
        help="Categoria opcional suportada pelo provider quando aplicavel.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI placeholder sem acionar integracoes reais."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.provider == "jooble":
        if not args.dry_run:
            parser.error("Use --dry-run com --provider jooble para o diagnostico provisório.")

        settings = load_runtime_settings()
        try:
            provider = JoobleProvider(api_key=settings.jooble_api_key or "")
            jobs = provider.fetch_jobs(
                term=args.term,
                location=args.location,
                page=args.page,
                results_per_page=args.results_per_page,
            )
        except ProviderError as exc:
            parser.exit(1, f"Erro no provider Jooble: {exc}\n")

        summary = {
            "provider": "jooble",
            "term": args.term,
            "location": args.location,
            "page": args.page,
            "results_per_page": args.results_per_page,
            "fetched": len(jobs),
            "jobs": [
                {
                    "provider_job_id": job.provider_job_id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    "url": str(job.url),
                }
                for job in jobs
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.provider == "remotive":
        if not args.dry_run:
            parser.error("Use --dry-run com --provider remotive para o diagnostico provisório.")

        try:
            provider = RemotiveProvider()
            jobs = provider.fetch_jobs(
                term=args.term,
                location=args.location,
                page=args.page,
                results_per_page=args.results_per_page,
                category=args.category or None,
            )
        except ProviderError as exc:
            parser.exit(1, f"Erro no provider Remotive: {exc}\n")

        summary = {
            "provider": "remotive",
            "term": args.term,
            "location": args.location,
            "category": args.category or None,
            "page": args.page,
            "results_per_page": args.results_per_page,
            "fetched": len(jobs),
            "jobs": [
                {
                    "provider_job_id": job.provider_job_id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    "url": str(job.url),
                }
                for job in jobs
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print("Radar de Vagas inicializado. Integracoes reais ainda nao foram implementadas.")
    return 0
