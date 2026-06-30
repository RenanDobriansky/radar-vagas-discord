from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from docx import Document

from radar_vagas.cli import main
from radar_vagas.config import FileConfigurationError, RuntimeSettings, load_profile_config
from radar_vagas.models import JobPosting, JobStatus, ResumeArtifact, WorkMode
from radar_vagas.notifications.discord import DiscordNotificationError
from radar_vagas.pipeline import PipelineOptions, PipelineSummary, run_pipeline
from radar_vagas.providers.base import ProviderCapabilities, ProviderRequestError
from radar_vagas.storage import JobHistoryStore
from radar_vagas.text_utils import make_job_fingerprint

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CANDIDATE_PROFILE_PATH = FIXTURES_DIR / "candidate_profile.yaml"


class StaticProvider:
    def __init__(self, jobs: list[JobPosting]) -> None:
        self.jobs = jobs

    def fetch_jobs(
        self,
        *,
        term: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
        category: str | None = None,
    ) -> list[JobPosting]:
        del term, location, page, results_per_page, category
        return list(self.jobs)


class FailingProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def fetch_jobs(
        self,
        *,
        term: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
        category: str | None = None,
    ) -> list[JobPosting]:
        del term, location, page, results_per_page, category
        raise self.error


class RecordingProvider:
    def __init__(
        self,
        jobs: list[JobPosting],
        *,
        capabilities: ProviderCapabilities | None = None,
    ) -> None:
        self.jobs = jobs
        self.capabilities = capabilities or ProviderCapabilities()
        self.calls: list[dict[str, object]] = []

    def fetch_jobs(
        self,
        *,
        term: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
        category: str | None = None,
    ) -> list[JobPosting]:
        self.calls.append(
            {
                "term": term,
                "location": location,
                "page": page,
                "results_per_page": results_per_page,
                "category": category,
            }
        )
        return list(self.jobs)


def build_settings() -> RuntimeSettings:
    return RuntimeSettings.model_validate(
        {
            "discord_webhook_url": "https://discord.example/webhook",
            "candidate_email": "renan.ficticio@example.com",
            "candidate_phone": "+55 41 99999-9999",
            "candidate_profile_path": str(CANDIDATE_PROFILE_PATH),
            "_env_file": None,
        }
    )


def build_profile_config():
    return load_profile_config()


def build_custom_profile_config(
    *,
    terms: list[str] | None = None,
    locations: list[str] | None = None,
    provider_results_per_query: int | None = None,
    maximum_notifications_per_run: int | None = None,
):
    config = build_profile_config()
    payload = config.model_dump(mode="python")
    if terms is not None:
        payload["search"]["terms"] = terms
    if locations is not None:
        payload["search"]["locations"] = locations
    if provider_results_per_query is not None:
        payload["search"]["provider_results_per_query"] = provider_results_per_query
    if maximum_notifications_per_run is not None:
        payload["search"]["maximum_notifications_per_run"] = maximum_notifications_per_run
    return type(config).model_validate(payload)


def build_job(
    *,
    provider_job_id: str,
    title: str = "Analista de BI Junior",
    company: str = "Empresa BI",
    location: str = "Curitiba - PR",
    url: str | None = None,
    description: str = (
        "Power BI, DAX, Power Query, SQL e Python para dashboards e indicadores."
    ),
) -> JobPosting:
    return JobPosting.model_validate(
        {
            "provider": "fixture",
            "provider_job_id": provider_job_id,
            "title": title,
            "company": company,
            "location": location,
            "work_mode": WorkMode.HYBRID,
            "employment_type": "CLT",
            "description": description,
            "salary": None,
            "published_at": "2026-06-25T08:00:00Z",
            "updated_at": "2026-06-25T10:00:00Z",
            "url": url or f"https://example.com/jobs/{provider_job_id}",
            "source_name": "Fixture",
            "search_term": "Analista de BI",
            "collected_at": "2026-06-25T11:30:00Z",
        }
    )


def build_resume_generator(
    *,
    invalid_ids: set[str] | None = None,
    failing_ids: set[str] | None = None,
):
    invalid_ids = invalid_ids or set()
    failing_ids = failing_ids or set()

    def _generate_resume(
        *,
        job: JobPosting,
        content: object,
        resume_profile: object,
        config: object,
        output_directory: Path,
    ) -> ResumeArtifact:
        del content, resume_profile, config
        if job.provider_job_id in failing_ids:
            raise RuntimeError("resume generation failed")

        output_directory.mkdir(parents=True, exist_ok=True)
        file_path = output_directory / f"resume_{job.provider_job_id}.docx"
        document = Document()
        document.add_paragraph(job.title)
        document.save(file_path)
        file_hash = sha256(file_path.read_bytes()).hexdigest()
        is_valid = job.provider_job_id not in invalid_ids
        return ResumeArtifact(
            job_fingerprint=make_job_fingerprint(job.title, job.company, job.location),
            target_title=job.title,
            company=job.company or "Empresa",
            file_path=file_path,
            file_name=file_path.name,
            file_sha256=file_hash,
            selected_skill_ids=["power_bi", "sql"],
            selected_experience_bullet_ids=["bullet-1"],
            selected_project_ids=["project-1"],
            validation_errors=[] if is_valid else ["invalid resume"],
            is_valid=is_valid,
        )

    return _generate_resume


def build_options(**overrides: object) -> PipelineOptions:
    payload = {
        "dry_run": False,
        "provider_names": ["jooble", "remotive"],
        "term": "Analista de BI",
        "location": "Curitiba",
        "max_jobs": 5,
        "save_resumes": False,
    }
    payload.update(overrides)
    return PipelineOptions(**payload)


def load_status_by_provider_job_id(history_path: Path) -> dict[str, JobStatus]:
    store = JobHistoryStore(history_path)
    return {
        record.provider_job_id or fingerprint: record.status
        for fingerprint, record in store.jobs.items()
    }


def load_record_by_provider_job_id(history_path: Path, provider_job_id: str):
    store = JobHistoryStore(history_path)
    for record in store.jobs.values():
        if record.provider_job_id == provider_job_id:
            return record
    raise KeyError(provider_job_id)


def capture_file_name(target: list[str]):
    def _sender(
        *,
        webhook_url: str,
        evaluated_job: object,
        resume_artifact: ResumeArtifact,
    ) -> None:
        del webhook_url, evaluated_job
        target.append(resume_artifact.file_name)

    return _sender


def test_pipeline_continues_when_one_provider_fails(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    sent_files: list[str] = []
    job = build_job(provider_job_id="job-1")

    summary = run_pipeline(
        options=build_options(),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={
            "jooble": lambda _settings: FailingProvider(ProviderRequestError("jooble failed")),
            "remotive": lambda _settings: StaticProvider([job]),
        },
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(sent_files),
    )

    statuses = load_status_by_provider_job_id(history_path)
    assert len(summary.provider_failures) == 1
    assert summary.provider_failures[0].provider == "jooble"
    assert summary.notifications_sent == 1
    assert sent_files == ["resume_job-1.docx"]
    assert statuses["job-1"] is JobStatus.NOTIFIED


def test_pipeline_queries_remotive_once_per_term_independent_of_locations(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    profile_config = build_custom_profile_config(
        terms=["BI Analyst", "Data Analyst"],
        locations=["Curitiba", "Pinhais", "Colombo"],
    )
    provider = RecordingProvider(
        [],
        capabilities=ProviderCapabilities(
            supports_location=False,
            supports_pagination=False,
            supports_category=True,
        ),
    )

    summary = run_pipeline(
        options=build_options(
            provider_names=["remotive"],
            term=None,
            location=None,
            max_jobs=None,
        ),
        settings=build_settings(),
        profile_config=profile_config,
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: provider},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name([]),
    )

    assert summary.queries_executed == 2
    assert len(provider.calls) == 2
    assert {call["term"] for call in provider.calls} == {"BI Analyst", "Data Analyst"}
    assert {call["location"] for call in provider.calls} == {""}


def test_pipeline_queries_jooble_for_each_term_and_location_combination(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    profile_config = build_custom_profile_config(
        terms=["BI Analyst", "Data Analyst"],
        locations=["Curitiba", "Pinhais", "Colombo"],
    )
    provider = RecordingProvider(
        [],
        capabilities=ProviderCapabilities(
            supports_location=True,
            supports_pagination=True,
            supports_category=False,
        ),
    )

    summary = run_pipeline(
        options=build_options(provider_names=["jooble"], term=None, location=None),
        settings=build_settings(),
        profile_config=profile_config,
        history_path=history_path,
        provider_factories={"jooble": lambda _settings: provider},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name([]),
    )

    assert summary.queries_executed == 6
    assert len(provider.calls) == 6
    assert {
        (call["term"], call["location"])
        for call in provider.calls
    } == {
        ("BI Analyst", "Curitiba"),
        ("BI Analyst", "Pinhais"),
        ("BI Analyst", "Colombo"),
        ("Data Analyst", "Curitiba"),
        ("Data Analyst", "Pinhais"),
        ("Data Analyst", "Colombo"),
    }


def test_pipeline_prefilter_discards_clearly_irrelevant_titles_without_persisting(
    tmp_path: Path,
) -> None:
    history_path = tmp_path / "seen_jobs.json"
    job = build_job(
        provider_job_id="job-1",
        title="Editor de Video",
        description="Captacao, edicao de video e motion design.",
    )

    summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name([]),
    )

    assert summary.prefiltered_jobs == 1
    assert summary.evaluated_jobs == 0
    assert summary.selected_jobs == 0
    assert JobHistoryStore(history_path).jobs == {}


def test_pipeline_prefilter_accepts_related_titles(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    job = build_job(provider_job_id="job-1", title="Analista de Performance")

    summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name([]),
    )

    assert summary.prefiltered_jobs == 0
    assert summary.evaluated_jobs == 1
    assert load_status_by_provider_job_id(history_path)["job-1"] is JobStatus.NOTIFIED


def test_pipeline_separates_results_per_query_from_maximum_notifications(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    profile_config = build_custom_profile_config(
        terms=["Analista de BI"],
        locations=["Curitiba"],
        provider_results_per_query=7,
        maximum_notifications_per_run=1,
    )
    provider = RecordingProvider(
        [
            build_job(provider_job_id="job-1", company="Empresa A"),
            build_job(provider_job_id="job-2", company="Empresa B"),
        ],
        capabilities=ProviderCapabilities(
            supports_location=False,
            supports_pagination=False,
            supports_category=True,
        ),
    )

    summary = run_pipeline(
        options=build_options(
            provider_names=["remotive"],
            term=None,
            location=None,
            max_jobs=None,
        ),
        settings=build_settings(),
        profile_config=profile_config,
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: provider},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name([]),
    )

    assert provider.calls[0]["results_per_page"] == 7
    assert summary.selected_jobs == 1
    assert summary.notifications_sent == 1


def test_pipeline_raises_when_resume_profile_cannot_be_loaded(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    job = build_job(provider_job_id="job-1")

    with pytest.raises(FileConfigurationError, match="candidate profile"):
        run_pipeline(
            options=build_options(provider_names=["remotive"]),
            settings=build_settings(),
            profile_config=build_profile_config(),
            history_path=history_path,
            provider_factories={"remotive": lambda _settings: StaticProvider([job])},
            resume_profile_loader=lambda settings: (_ for _ in ()).throw(
                FileConfigurationError("candidate profile failed to load")
            ),
        )


def test_pipeline_continues_when_resume_generation_fails(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    sent_files: list[str] = []
    jobs = [
        build_job(provider_job_id="job-1", company="Empresa A"),
        build_job(provider_job_id="job-2", company="Empresa B"),
    ]

    summary = run_pipeline(
        options=build_options(provider_names=["remotive"], max_jobs=2),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider(jobs)},
        resume_generator=build_resume_generator(failing_ids={"job-1"}),
        notification_sender=capture_file_name(sent_files),
    )

    statuses = load_status_by_provider_job_id(history_path)
    failed_record = load_record_by_provider_job_id(history_path, "job-1")
    assert summary.resume_failures == 1
    assert summary.notifications_sent == 1
    assert statuses["job-1"] is JobStatus.RETRY_PENDING
    assert failed_record.attempts == 1
    assert failed_record.last_error_code == "resume_generation_failed"
    assert statuses["job-2"] is JobStatus.NOTIFIED
    assert sent_files == ["resume_job-2.docx"]


def test_pipeline_marks_invalid_resume_and_schedules_retry(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    job = build_job(provider_job_id="job-1")
    notifications: list[str] = []

    summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(invalid_ids={"job-1"}),
        notification_sender=capture_file_name(notifications),
    )

    statuses = load_status_by_provider_job_id(history_path)
    failed_record = load_record_by_provider_job_id(history_path, "job-1")
    assert summary.invalid_resumes == 1
    assert summary.notifications_sent == 0
    assert notifications == []
    assert statuses["job-1"] is JobStatus.RETRY_PENDING
    assert failed_record.last_error_code == "resume_invalid"


def test_pipeline_marks_notification_failure_and_schedules_retry(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    job = build_job(provider_job_id="job-1")

    def failing_sender(
        *,
        webhook_url: str,
        evaluated_job: object,
        resume_artifact: object,
    ) -> None:
        del webhook_url, evaluated_job, resume_artifact
        raise DiscordNotificationError("discord offline")

    summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(),
        notification_sender=failing_sender,
    )

    statuses = load_status_by_provider_job_id(history_path)
    failed_record = load_record_by_provider_job_id(history_path, "job-1")
    assert summary.notification_failures == 1
    assert summary.notifications_sent == 0
    assert statuses["job-1"] is JobStatus.RETRY_PENDING
    assert failed_record.last_error_code == "discord_notification_failed"


def test_pipeline_processes_multiple_jobs_with_distinct_resumes(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    sent_files: list[str] = []
    jobs = [
        build_job(provider_job_id="job-1", company="Empresa A", title="Analista de BI Junior"),
        build_job(provider_job_id="job-2", company="Empresa B", title="Analista de Dados Junior"),
    ]

    summary = run_pipeline(
        options=build_options(provider_names=["remotive"], max_jobs=2),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider(jobs)},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(sent_files),
    )

    assert summary.notifications_sent == 2
    assert len(set(sent_files)) == 2
    assert summary.files_removed == 2


def test_pipeline_keeps_excess_eligible_jobs_queued_for_next_execution(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    sent_files: list[str] = []
    jobs = [
        build_job(provider_job_id="job-1", company="Empresa A"),
        build_job(provider_job_id="job-2", company="Empresa B"),
    ]

    first_summary = run_pipeline(
        options=build_options(provider_names=["remotive"], max_jobs=1),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider(jobs)},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(sent_files),
    )
    queued_record = load_record_by_provider_job_id(history_path, "job-2")

    second_summary = run_pipeline(
        options=build_options(provider_names=["remotive"], max_jobs=1),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(sent_files),
    )

    assert first_summary.notifications_sent == 1
    assert queued_record.status is JobStatus.QUEUED
    assert second_summary.notifications_sent == 1
    assert sent_files == ["resume_job-1.docx", "resume_job-2.docx"]
    assert load_status_by_provider_job_id(history_path)["job-2"] is JobStatus.NOTIFIED


def test_pipeline_retries_resume_failure_on_later_execution(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    sent_files: list[str] = []
    job = build_job(provider_job_id="job-1")

    first_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(failing_ids={"job-1"}),
        notification_sender=capture_file_name(sent_files),
        reference_time=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )
    second_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(sent_files),
        reference_time=datetime(2026, 6, 25, 13, 30, tzinfo=UTC),
    )

    assert first_summary.resume_failures == 1
    assert second_summary.notifications_sent == 1
    assert load_status_by_provider_job_id(history_path)["job-1"] is JobStatus.NOTIFIED
    assert sent_files == ["resume_job-1.docx"]


def test_pipeline_retries_notification_failure_on_later_execution(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    sent_files: list[str] = []
    job = build_job(provider_job_id="job-1")

    def failing_sender(
        *,
        webhook_url: str,
        evaluated_job: object,
        resume_artifact: object,
    ) -> None:
        del webhook_url, evaluated_job, resume_artifact
        raise DiscordNotificationError("discord offline")

    first_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(),
        notification_sender=failing_sender,
        reference_time=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )
    second_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(sent_files),
        reference_time=datetime(2026, 6, 25, 13, 30, tzinfo=UTC),
    )

    assert first_summary.notification_failures == 1
    assert second_summary.notifications_sent == 1
    assert load_status_by_provider_job_id(history_path)["job-1"] is JobStatus.NOTIFIED
    assert sent_files == ["resume_job-1.docx"]


def test_pipeline_respects_next_retry_at(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    notifications: list[str] = []
    job = build_job(provider_job_id="job-1")

    run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(failing_ids={"job-1"}),
        notification_sender=capture_file_name(notifications),
        reference_time=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )
    second_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(notifications),
        reference_time=datetime(2026, 6, 25, 12, 30, tzinfo=UTC),
    )

    record = load_record_by_provider_job_id(history_path, "job-1")
    assert second_summary.selected_jobs == 0
    assert second_summary.notifications_sent == 0
    assert record.status is JobStatus.RETRY_PENDING
    assert notifications == []


def test_pipeline_moves_failed_job_to_dead_letter_after_retry_limit(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    notifications: list[str] = []
    job = build_job(provider_job_id="job-1")

    run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(failing_ids={"job-1"}),
        notification_sender=capture_file_name(notifications),
        reference_time=datetime(2026, 6, 25, 12, 0, tzinfo=UTC),
    )
    run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([])},
        resume_generator=build_resume_generator(failing_ids={"job-1"}),
        notification_sender=capture_file_name(notifications),
        reference_time=datetime(2026, 6, 25, 13, 30, tzinfo=UTC),
    )
    third_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([])},
        resume_generator=build_resume_generator(failing_ids={"job-1"}),
        notification_sender=capture_file_name(notifications),
        reference_time=datetime(2026, 6, 25, 15, 30, tzinfo=UTC),
    )

    record = load_record_by_provider_job_id(history_path, "job-1")
    assert third_summary.resume_failures == 1
    assert record.status is JobStatus.DEAD_LETTER
    assert record.attempts == 3
    assert record.next_retry_at is None


def test_pipeline_repeated_execution_skips_notified_history_duplicates(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    sent_files: list[str] = []
    job = build_job(provider_job_id="job-1")
    factories = {"remotive": lambda _settings: StaticProvider([job])}
    generator = build_resume_generator()

    first_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories=factories,
        resume_generator=generator,
        notification_sender=capture_file_name(sent_files),
    )
    second_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories=factories,
        resume_generator=generator,
        notification_sender=capture_file_name(sent_files),
    )

    assert first_summary.notifications_sent == 1
    assert second_summary.skipped_existing_jobs == 1
    assert second_summary.notifications_sent == 0
    assert sent_files == ["resume_job-1.docx"]


def test_pipeline_repeated_execution_discards_prefiltered_duplicates_without_persisting(
    tmp_path: Path,
) -> None:
    history_path = tmp_path / "seen_jobs.json"
    job = build_job(
        provider_job_id="job-1",
        title="Analista Comercial",
        description="Excel e reporting operacional.",
    )

    first_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name([]),
    )
    second_summary = run_pipeline(
        options=build_options(provider_names=["remotive"]),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name([]),
    )

    assert first_summary.prefiltered_jobs == 1
    assert second_summary.prefiltered_jobs == 1
    assert second_summary.skipped_existing_jobs == 0
    assert JobHistoryStore(history_path).jobs == {}


def test_pipeline_dry_run_does_not_persist_history_or_send_notifications(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    job = build_job(provider_job_id="job-1")
    notifications: list[str] = []

    summary = run_pipeline(
        options=build_options(provider_names=["remotive"], dry_run=True),
        settings=build_settings(),
        profile_config=build_profile_config(),
        history_path=history_path,
        provider_factories={"remotive": lambda _settings: StaticProvider([job])},
        resume_generator=build_resume_generator(),
        notification_sender=capture_file_name(notifications),
    )

    assert summary.resumes_generated == 1
    assert summary.notifications_sent == 0
    assert notifications == []
    assert not history_path.exists()
    assert summary.files_removed == 1
    assert all(not Path(path).exists() for path in summary.generated_files)


def test_cli_runs_pipeline_with_overrides(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_options: dict[str, object] = {}
    monkeypatch.setattr("radar_vagas.cli.load_runtime_settings", build_settings)

    def fake_run_pipeline(
        *,
        options: PipelineOptions,
        settings: RuntimeSettings,
    ) -> PipelineSummary:
        captured_options["provider_names"] = options.provider_names
        captured_options["dry_run"] = options.dry_run
        captured_options["minimum_score"] = options.minimum_score
        captured_options["max_jobs"] = options.max_jobs
        captured_options["save_resumes"] = options.save_resumes
        captured_options["term"] = options.term
        captured_options["location"] = options.location
        del settings
        return PipelineSummary(
            dry_run=options.dry_run,
            provider_names=options.provider_names or ["jooble", "remotive"],
            selected_jobs=1,
            notifications_sent=0,
        )

    monkeypatch.setattr("radar_vagas.cli.run_pipeline", fake_run_pipeline)

    exit_code = main(
        [
            "--dry-run",
            "--provider",
            "remotive",
            "--minimum-score",
            "75",
            "--max-jobs",
            "2",
            "--term",
            "Analista de BI",
            "--location",
            "Curitiba",
            "--save-resumes",
        ]
    )

    payload = main_payload(capsys)
    assert exit_code == 0
    assert payload["selected_jobs"] == 1
    assert captured_options == {
        "provider_names": ["remotive"],
        "dry_run": True,
        "minimum_score": 75,
        "max_jobs": 2,
        "save_resumes": True,
        "term": "Analista de BI",
        "location": "Curitiba",
    }


def main_payload(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    captured = capsys.readouterr()
    return json.loads(captured.out)
