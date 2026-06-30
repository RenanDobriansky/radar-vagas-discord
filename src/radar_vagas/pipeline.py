"""Orquestracao principal do pipeline de busca, filtragem e notificacao."""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from radar_vagas.config import (
    ProfileConfig,
    RuntimeSettings,
    load_profile_config,
    load_runtime_settings,
)
from radar_vagas.deduplication import deduplicate_jobs
from radar_vagas.models import EvaluatedJob, JobPosting, JobStatus, Priority, ResumeArtifact
from radar_vagas.notifications.discord import DiscordNotificationError, send_job_notification
from radar_vagas.providers.base import JobProvider, ProviderError
from radar_vagas.providers.jooble import JoobleProvider
from radar_vagas.providers.remotive import RemotiveProvider
from radar_vagas.resumes.content_selector import select_resume_content
from radar_vagas.resumes.generator import generate_resume
from radar_vagas.resumes.keyword_extractor import extract_job_keywords
from radar_vagas.resumes.profile import ResumeProfile, load_resume_profile
from radar_vagas.scoring import evaluate_job
from radar_vagas.storage import DEFAULT_HISTORY_PATH, JobHistoryStore, StoredJobRecord

logger = logging.getLogger(__name__)

ProviderFactory = Callable[[RuntimeSettings], JobProvider]
ResumeProfileLoader = Callable[[RuntimeSettings], ResumeProfile]
ResumeGenerator = Callable[..., ResumeArtifact]
NotificationSender = Callable[..., object]


@dataclass(slots=True)
class PipelineOptions:
    """Opcoes operacionais do pipeline principal."""

    dry_run: bool = False
    provider_names: list[str] | None = None
    minimum_score: int | None = None
    max_jobs: int | None = None
    save_resumes: bool = False
    term: str | None = None
    location: str | None = None
    results_per_page: int | None = None
    category: str | None = None


@dataclass(slots=True)
class ProviderFailure:
    """Falha isolada ao executar uma fonte ou consulta."""

    provider: str
    term: str | None
    location: str | None
    error: str


@dataclass(slots=True)
class PipelineSummary:
    """Resumo estruturado da execucao do pipeline."""

    dry_run: bool
    provider_names: list[str]
    queries_executed: int = 0
    fetched_jobs: int = 0
    deduplicated_jobs: int = 0
    execution_duplicates: int = 0
    skipped_existing_jobs: int = 0
    evaluated_jobs: int = 0
    rejected_jobs: int = 0
    eligible_jobs: int = 0
    selected_jobs: int = 0
    resumes_generated: int = 0
    invalid_resumes: int = 0
    resume_failures: int = 0
    notifications_sent: int = 0
    notification_failures: int = 0
    history_records_pruned: int = 0
    files_removed: int = 0
    generated_files: list[str] = field(default_factory=list)
    provider_failures: list[ProviderFailure] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Converte o resumo para um payload serializavel."""
        payload = asdict(self)
        payload["provider_failures"] = [asdict(item) for item in self.provider_failures]
        return payload


def run_pipeline(
    *,
    options: PipelineOptions,
    settings: RuntimeSettings | None = None,
    profile_config: ProfileConfig | None = None,
    history_path: Path | str = DEFAULT_HISTORY_PATH,
    provider_factories: dict[str, ProviderFactory] | None = None,
    resume_profile_loader: ResumeProfileLoader = load_resume_profile,
    resume_generator: ResumeGenerator = generate_resume,
    notification_sender: NotificationSender = send_job_notification,
    reference_time: datetime | None = None,
) -> PipelineSummary:
    """Executa o fluxo principal de ponta a ponta."""
    runtime_settings = settings or load_runtime_settings()
    base_config = profile_config or load_profile_config()
    effective_config = _apply_overrides(base_config, options)
    factories = provider_factories or _default_provider_factories()
    selected_providers = _resolve_provider_names(options, factories)
    summary = PipelineSummary(
        dry_run=options.dry_run,
        provider_names=selected_providers,
    )
    now = reference_time.astimezone(UTC) if reference_time else datetime.now(UTC)
    history = JobHistoryStore(history_path, dry_run=options.dry_run)
    temporary_directory = _build_temporary_directory(options)

    try:
        pending_jobs = _load_pending_jobs(history=history, reference_time=now)
        fetched_jobs = _fetch_jobs(
            selected_providers=selected_providers,
            factories=factories,
            settings=runtime_settings,
            config=effective_config,
            options=options,
            summary=summary,
        )
        deduplication_result = deduplicate_jobs(fetched_jobs)
        summary.execution_duplicates = len(deduplication_result.duplicates)
        summary.deduplicated_jobs = len(deduplication_result.unique_jobs)

        unseen_jobs: list[JobPosting] = []
        for job in deduplication_result.unique_jobs:
            if history.find_match(job) is not None:
                summary.skipped_existing_jobs += 1
                continue
            unseen_jobs.append(job)

        evaluated_jobs: list[EvaluatedJob] = []
        for job in unseen_jobs:
            evaluated_job = evaluate_job(job, effective_config, reference_time=now)
            summary.evaluated_jobs += 1
            if evaluated_job.is_eligible:
                evaluated_jobs.append(evaluated_job)
                if not options.dry_run:
                    history.record_job(
                        job,
                        status=JobStatus.QUEUED,
                        score=evaluated_job.score,
                        seen_at=now,
                        fingerprint=evaluated_job.fingerprint,
                        evaluated_job=evaluated_job,
                    )
            else:
                summary.rejected_jobs += 1
                if not options.dry_run:
                    history.record_job(
                        job,
                        status=JobStatus.REJECTED,
                        score=evaluated_job.score,
                        seen_at=now,
                        fingerprint=evaluated_job.fingerprint,
                        evaluated_job=evaluated_job,
                    )

        pending_jobs.sort(key=lambda item: _evaluated_job_sort_key(item, now))
        evaluated_jobs.sort(key=lambda item: _evaluated_job_sort_key(item, now))
        ordered_candidates = pending_jobs + evaluated_jobs
        summary.eligible_jobs = len(ordered_candidates)
        selected_jobs = ordered_candidates[: effective_config.search.maximum_jobs_per_run]
        summary.selected_jobs = len(selected_jobs)

        if selected_jobs:
            resume_profile = resume_profile_loader(runtime_settings)
            output_directory = _resolve_output_directory(
                config=effective_config,
                runtime_settings=runtime_settings,
                options=options,
                temporary_directory=temporary_directory,
            )
            preserve_resumes = _should_preserve_resumes(config=effective_config, options=options)

            for evaluated_job in selected_jobs:
                _process_selected_job(
                    evaluated_job=evaluated_job,
                    config=effective_config,
                    resume_profile=resume_profile,
                    runtime_settings=runtime_settings,
                    history=history,
                    summary=summary,
                    now=now,
                    options=options,
                    output_directory=output_directory,
                    preserve_resumes=preserve_resumes,
                    resume_generator=resume_generator,
                    notification_sender=notification_sender,
                )
    finally:
        removed = history.prune(reference_time=now)
        summary.history_records_pruned = len(removed)
        history.save()
        if temporary_directory is not None and temporary_directory.exists():
            shutil.rmtree(temporary_directory, ignore_errors=True)

    logger.info("pipeline summary: %s", summary.to_dict())
    return summary


def _fetch_jobs(
    *,
    selected_providers: list[str],
    factories: dict[str, ProviderFactory],
    settings: RuntimeSettings,
    config: ProfileConfig,
    options: PipelineOptions,
    summary: PipelineSummary,
) -> list[JobPosting]:
    all_jobs: list[JobPosting] = []
    terms = _resolve_terms(config, options)
    locations = _resolve_locations(config, options)
    results_per_page = options.results_per_page or config.search.maximum_jobs_per_run

    for provider_name in selected_providers:
        factory = factories[provider_name]
        try:
            provider = factory(settings)
        except ProviderError as exc:
            _register_provider_failure(
                summary=summary,
                provider=provider_name,
                term=None,
                location=None,
                error=str(exc),
            )
            continue

        for term in terms:
            for location in locations:
                summary.queries_executed += 1
                try:
                    jobs = _fetch_provider_jobs(
                        provider=provider,
                        provider_name=provider_name,
                        term=term,
                        location=location,
                        results_per_page=results_per_page,
                        category=options.category,
                    )
                except ProviderError as exc:
                    _register_provider_failure(
                        summary=summary,
                        provider=provider_name,
                        term=term,
                        location=location,
                        error=str(exc),
                    )
                    continue

                all_jobs.extend(jobs)
                summary.fetched_jobs += len(jobs)

    return all_jobs


def _fetch_provider_jobs(
    *,
    provider: JobProvider,
    provider_name: str,
    term: str,
    location: str,
    results_per_page: int,
    category: str | None,
) -> list[JobPosting]:
    if provider_name == "remotive" and isinstance(provider, RemotiveProvider):
        return provider.fetch_jobs(
            term=term,
            location=location,
            page=1,
            results_per_page=results_per_page,
            category=category,
        )

    return provider.fetch_jobs(
        term=term,
        location=location,
        page=1,
        results_per_page=results_per_page,
    )


def _process_selected_job(
    *,
    evaluated_job: EvaluatedJob,
    config: ProfileConfig,
    resume_profile: ResumeProfile,
    runtime_settings: RuntimeSettings,
    history: JobHistoryStore,
    summary: PipelineSummary,
    now: datetime,
    options: PipelineOptions,
    output_directory: Path,
    preserve_resumes: bool,
    resume_generator: ResumeGenerator,
    notification_sender: NotificationSender,
) -> None:
    artifact: ResumeArtifact | None = None
    try:
        extraction = extract_job_keywords(evaluated_job.job, config)
        selected_content = select_resume_content(
            job=evaluated_job.job,
            extraction=extraction,
            resume_profile=resume_profile,
            config=config,
        )
        artifact = resume_generator(
            job=evaluated_job.job,
            content=selected_content,
            resume_profile=resume_profile,
            config=config,
            output_directory=output_directory,
        )
        summary.generated_files.append(str(artifact.file_path))

        if not artifact.is_valid:
            summary.invalid_resumes += 1
            if not options.dry_run:
                history.record_failure(
                    evaluated_job.job,
                    score=evaluated_job.score,
                    error_code="resume_invalid",
                    error_message="Resume validation failed before notification",
                    seen_at=now,
                    fingerprint=evaluated_job.fingerprint,
                    evaluated_job=evaluated_job,
                )
            return

        summary.resumes_generated += 1
        if not options.dry_run:
            history.record_job(
                evaluated_job.job,
                status=JobStatus.RESUME_GENERATED,
                score=evaluated_job.score,
                seen_at=now,
                fingerprint=evaluated_job.fingerprint,
                evaluated_job=evaluated_job,
            )

        if options.dry_run or not config.resume.attach_to_discord:
            return

        try:
            notification_sender(
                webhook_url=runtime_settings.discord_webhook_url or "",
                evaluated_job=evaluated_job,
                resume_artifact=artifact,
            )
        except DiscordNotificationError:
            summary.notification_failures += 1
            history.record_failure(
                evaluated_job.job,
                score=evaluated_job.score,
                error_code="discord_notification_failed",
                error_message="Discord notification failed",
                seen_at=now,
                fingerprint=evaluated_job.fingerprint,
                evaluated_job=evaluated_job,
            )
            return

        summary.notifications_sent += 1
        history.record_job(
            evaluated_job.job,
            status=JobStatus.NOTIFIED,
            score=evaluated_job.score,
            seen_at=now,
            notified_at=now,
            fingerprint=evaluated_job.fingerprint,
            evaluated_job=evaluated_job,
        )
    except Exception as exc:
        logger.exception(
            "resume processing failed: title=%r company=%r",
            evaluated_job.job.title,
            evaluated_job.job.company,
        )
        summary.resume_failures += 1
        if not options.dry_run:
            history.record_failure(
                evaluated_job.job,
                score=evaluated_job.score,
                error_code="resume_generation_failed",
                error_message=f"Resume generation failed ({type(exc).__name__})",
                seen_at=now,
                fingerprint=evaluated_job.fingerprint,
                evaluated_job=evaluated_job,
            )
        return
    finally:
        if artifact is not None and artifact.file_path.exists() and not preserve_resumes:
            artifact.file_path.unlink(missing_ok=True)
            summary.files_removed += 1


def _default_provider_factories() -> dict[str, ProviderFactory]:
    return {
        "jooble": lambda settings: JoobleProvider(api_key=settings.jooble_api_key or ""),
        "remotive": lambda _settings: RemotiveProvider(),
    }


def _resolve_provider_names(
    options: PipelineOptions,
    factories: dict[str, ProviderFactory],
) -> list[str]:
    available = sorted(factories.keys())
    if not options.provider_names:
        return available

    selected: list[str] = []
    for provider_name in options.provider_names:
        normalized = provider_name.strip().casefold()
        if normalized not in available:
            raise ValueError(f"Unsupported provider: {provider_name}")
        if normalized not in selected:
            selected.append(normalized)
    return selected


def _apply_overrides(config: ProfileConfig, options: PipelineOptions) -> ProfileConfig:
    payload = config.model_dump(mode="python")
    payload["search"]["minimum_score"] = (
        options.minimum_score
        if options.minimum_score is not None
        else config.search.minimum_score
    )
    payload["search"]["maximum_jobs_per_run"] = (
        options.max_jobs
        if options.max_jobs is not None
        else config.search.maximum_jobs_per_run
    )
    payload["search"]["terms"] = _resolve_terms(config, options)
    payload["search"]["locations"] = _resolve_locations(config, options)
    return ProfileConfig.model_validate(payload)


def _resolve_terms(config: ProfileConfig, options: PipelineOptions) -> list[str]:
    if options.term and options.term.strip():
        return [options.term.strip()]
    return config.search.terms


def _resolve_locations(config: ProfileConfig, options: PipelineOptions) -> list[str]:
    if options.location and options.location.strip():
        return [options.location.strip()]
    return config.search.locations


def _register_provider_failure(
    *,
    summary: PipelineSummary,
    provider: str,
    term: str | None,
    location: str | None,
    error: str,
) -> None:
    logger.warning(
        "provider failure: provider=%s term=%r location=%r error=%s",
        provider,
        term,
        location,
        error,
    )
    summary.provider_failures.append(
        ProviderFailure(
            provider=provider,
            term=term,
            location=location,
            error=error,
        )
    )


def _build_temporary_directory(options: PipelineOptions) -> Path | None:
    if options.dry_run and not options.save_resumes:
        return Path(tempfile.mkdtemp(prefix="radar_vagas_"))
    return None


def _resolve_output_directory(
    *,
    config: ProfileConfig,
    runtime_settings: RuntimeSettings,
    options: PipelineOptions,
    temporary_directory: Path | None,
) -> Path:
    if temporary_directory is not None:
        return temporary_directory
    if runtime_settings.resume_output_directory is not None:
        return runtime_settings.resume_output_directory
    del options
    return Path(config.resume.output_directory)


def _should_preserve_resumes(*, config: ProfileConfig, options: PipelineOptions) -> bool:
    if options.save_resumes:
        return True
    return config.resume.keep_generated_files and not options.dry_run


def _load_pending_jobs(
    *,
    history: JobHistoryStore,
    reference_time: datetime,
) -> list[EvaluatedJob]:
    return [
        _record_to_evaluated_job(record)
        for record in history.get_processable_records(reference_time=reference_time)
    ]


def _record_to_evaluated_job(record: StoredJobRecord) -> EvaluatedJob:
    score = record.score or 0
    priority = record.priority or _priority_from_score(score)
    return EvaluatedJob(
        job=record.job_snapshot.model_copy(deep=True),
        score=score,
        priority=priority,
        matched_skills=record.matched_skills.copy(),
        missing_skills=record.missing_skills.copy(),
        extracted_keywords=record.extracted_keywords.copy(),
        relevant_domains=record.relevant_domains.copy(),
        rejection_reasons=record.rejection_reasons.copy(),
        is_eligible=True,
        fingerprint=record.fingerprint,
        score_explanation=record.score_explanation or "Queued from persisted history",
    )


def _evaluated_job_sort_key(
    item: EvaluatedJob,
    reference_time: datetime,
) -> tuple[float, float, str]:
    timestamp = item.job.updated_at or item.job.published_at or reference_time
    return (-item.score, -timestamp.timestamp(), item.job.title)


def _priority_from_score(score: int) -> Priority:
    if score >= 85:
        return Priority.HIGH
    if score >= 70:
        return Priority.GOOD
    return Priority.BELOW_THRESHOLD
