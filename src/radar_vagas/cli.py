"""CLI minima do projeto Radar de Vagas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar_vagas import __version__
from radar_vagas.config import load_profile_config, load_runtime_settings
from radar_vagas.models import JobPosting
from radar_vagas.notifications.discord import DiscordNotificationError, send_test_message
from radar_vagas.providers.base import ProviderError
from radar_vagas.providers.jooble import JoobleProvider
from radar_vagas.providers.remotive import RemotiveProvider
from radar_vagas.resumes.generator import generate_resume_for_job
from radar_vagas.resumes.profile import load_resume_profile


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
    parser.add_argument(
        "--generate-resume",
        metavar="CAMINHO_JSON",
        help="Gera um curriculo DOCX a partir de uma vaga normalizada em JSON.",
    )
    parser.add_argument(
        "--save-resumes",
        action="store_true",
        help="No modo dry-run, gera curriculos de exemplo para inspecao.",
    )
    parser.add_argument(
        "--test-discord",
        action="store_true",
        help="Envia uma mensagem de teste para o webhook do Discord com um DOCX ficticio.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI placeholder sem acionar integracoes reais."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.test_discord:
        settings = load_runtime_settings()
        try:
            receipt = send_test_message(settings=settings)
        except DiscordNotificationError as exc:
            parser.exit(1, f"Erro ao testar Discord: {exc}\n")

        print(
            json.dumps(
                {
                    "message_id": receipt.message_id,
                    "status_code": receipt.status_code,
                    "attachment_name": receipt.attachment_name,
                    "attempts": receipt.attempts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.generate_resume:
        settings = load_runtime_settings()
        profile_config = load_profile_config()
        resume_profile = load_resume_profile(settings)
        job = _load_job_from_json(Path(args.generate_resume))
        artifact = generate_resume_for_job(
            job=job,
            resume_profile=resume_profile,
            config=profile_config,
        )
        print(
            json.dumps(
                {
                    "file_path": str(artifact.file_path),
                    "file_name": artifact.file_name,
                    "is_valid": artifact.is_valid,
                    "validation_errors": artifact.validation_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if artifact.is_valid else 1

    if args.dry_run and args.save_resumes and args.provider is None:
        settings = load_runtime_settings()
        profile_config = load_profile_config()
        resume_profile = load_resume_profile(settings)
        fixture_paths = [
            Path("tests/fixtures/jobs/bi_job.json"),
            Path("tests/fixtures/jobs/finance_job.json"),
            Path("tests/fixtures/jobs/data_engineering_job.json"),
        ]
        artifacts = []
        for fixture_path in fixture_paths:
            job = _load_job_from_json(fixture_path)
            artifacts.append(
                generate_resume_for_job(
                    job=job,
                    resume_profile=resume_profile,
                    config=profile_config,
                )
            )
        print(
            json.dumps(
                {
                    "generated": len(artifacts),
                    "artifacts": [
                        {
                            "file_path": str(artifact.file_path),
                            "file_name": artifact.file_name,
                            "is_valid": artifact.is_valid,
                        }
                        for artifact in artifacts
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

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


def _load_job_from_json(path: Path) -> JobPosting:
    return JobPosting.model_validate_json(path.read_text(encoding="utf-8"))
