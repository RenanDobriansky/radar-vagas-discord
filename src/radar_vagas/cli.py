"""CLI principal do projeto Radar de Vagas."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from radar_vagas import __version__
from radar_vagas.config import ConfigurationError, load_profile_config, load_runtime_settings
from radar_vagas.models import JobPosting
from radar_vagas.notifications.discord import DiscordNotificationError, send_test_message
from radar_vagas.pipeline import PipelineOptions, run_pipeline
from radar_vagas.resumes.generator import generate_resume_for_job
from radar_vagas.resumes.profile import load_resume_profile


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser da linha de comando."""
    parser = argparse.ArgumentParser(
        prog="radar_vagas",
        description="Busca, prioriza e prepara vagas aderentes ao perfil configurado.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=["jooble", "remotive"],
        help="Limita a execucao aos providers informados. Pode ser repetido.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa o pipeline sem enviar mensagens nem persistir historico.",
    )
    parser.add_argument(
        "--term",
        default=None,
        help="Sobrescreve os termos configurados com um unico termo de busca.",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Sobrescreve as localizacoes configuradas com uma unica localizacao.",
    )
    parser.add_argument("--page", type=int, default=1, help="Mantido por compatibilidade.")
    parser.add_argument(
        "--results-per-page",
        type=int,
        default=None,
        help="Quantidade desejada de resultados por consulta.",
    )
    parser.add_argument(
        "--category",
        default="",
        help="Categoria opcional suportada pelo provider Remotive quando aplicavel.",
    )
    parser.add_argument(
        "--minimum-score",
        type=int,
        default=None,
        help="Sobrescreve o score minimo configurado.",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Sobrescreve a quantidade maxima de vagas processadas.",
    )
    parser.add_argument(
        "--generate-resume",
        metavar="CAMINHO_JSON",
        help="Gera um curriculo DOCX a partir de uma vaga normalizada em JSON.",
    )
    parser.add_argument(
        "--save-resumes",
        action="store_true",
        help="Preserva os curriculos gerados; sem esta opcao os temporarios sao removidos.",
    )
    parser.add_argument(
        "--test-discord",
        action="store_true",
        help="Envia uma mensagem de teste para o webhook do Discord com um DOCX ficticio.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Ativa logs detalhados da execucao.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI do projeto Radar de Vagas."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(verbose=args.verbose)

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

    try:
        settings = load_runtime_settings()
        summary = run_pipeline(
            options=PipelineOptions(
                dry_run=args.dry_run,
                provider_names=args.provider,
                minimum_score=args.minimum_score,
                max_jobs=args.max_jobs,
                save_resumes=args.save_resumes,
                term=args.term,
                location=args.location,
                results_per_page=args.results_per_page,
                category=args.category or None,
            ),
            settings=settings,
        )
    except (ConfigurationError, DiscordNotificationError, ValueError) as exc:
        parser.exit(1, f"Erro na execucao do pipeline: {exc}\n")

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _load_job_from_json(path: Path) -> JobPosting:
    return JobPosting.model_validate_json(path.read_text(encoding="utf-8"))


def _configure_logging(*, verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    if verbose:
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
