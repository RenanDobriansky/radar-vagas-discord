"""Persistencia local do historico de vagas em JSON."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from json import JSONDecodeError
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

from radar_vagas.deduplication import (
    DuplicateReason,
    make_job_identity_fingerprint,
    make_normalized_job_url,
    make_provider_job_key,
)
from radar_vagas.models import EvaluatedJob, JobPosting, JobStatus, Priority, utc_now

HISTORY_VERSION = 2
DEFAULT_HISTORY_PATH = Path("data/seen_jobs.json")
DEFAULT_MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SCHEDULE = (
    timedelta(hours=1),
    timedelta(hours=2),
    timedelta(hours=4),
)
FINAL_JOB_STATUSES = {
    JobStatus.REJECTED,
    JobStatus.NOTIFIED,
    JobStatus.DEAD_LETTER,
}
PROCESSABLE_JOB_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RETRY_PENDING,
    JobStatus.RESUME_GENERATED,
}


class HistoryStorageError(RuntimeError):
    """Falha ao carregar, validar ou persistir o historico local."""


def _normalize_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_error_message(message: str | None) -> str | None:
    if message is None:
        return None
    cleaned = " ".join(str(message).split())
    return cleaned or None


class StoredJobRecord(BaseModel):
    """Registro persistido para uma vaga ja processada ou enfileirada."""

    provider: str
    provider_job_id: str | None = None
    title: str
    company: str | None = None
    url: str
    normalized_url: str
    fingerprint: str
    job_snapshot: JobPosting
    score: int | None = Field(default=None, ge=0, le=100)
    priority: Priority | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    extracted_keywords: list[str] = Field(default_factory=list)
    relevant_domains: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    score_explanation: str | None = None
    status: JobStatus
    attempts: int = Field(default=0, ge=0)
    last_error_code: str | None = None
    last_error_message: str | None = None
    next_retry_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    notified_at: datetime | None = None

    @field_validator(
        "first_seen_at",
        "last_seen_at",
        "notified_at",
        "next_retry_at",
        mode="before",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | str | None) -> datetime | None:
        return _normalize_datetime(value)

    @field_validator("last_error_message", mode="before")
    @classmethod
    def sanitize_error_message(cls, value: str | None) -> str | None:
        return _normalize_error_message(value)


class HistoryDocument(BaseModel):
    """Documento JSON persistido em `data/seen_jobs.json`."""

    version: int = HISTORY_VERSION
    jobs: dict[str, StoredJobRecord] = Field(default_factory=dict)


class LegacyStoredJobRecordV1(BaseModel):
    """Schema legado da versao 1 do historico."""

    provider: str
    provider_job_id: str | None = None
    title: str
    company: str | None = None
    url: str
    normalized_url: str
    fingerprint: str
    score: int | None = Field(default=None, ge=0, le=100)
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    notified_at: datetime | None = None

    @field_validator("first_seen_at", "last_seen_at", "notified_at", mode="before")
    @classmethod
    def normalize_timestamps(cls, value: datetime | str | None) -> datetime | None:
        return _normalize_datetime(value)


class LegacyHistoryDocumentV1(BaseModel):
    """Documento JSON persistido no formato legado v1."""

    version: int = 1
    jobs: dict[str, LegacyStoredJobRecordV1] = Field(default_factory=dict)


@dataclass(slots=True)
class HistoryLookupResult:
    """Representa um match encontrado no historico."""

    record: StoredJobRecord
    reason: DuplicateReason
    matched_key: str


class JobHistoryStore:
    """Repositorio local de historico com escrita atomica em JSON."""

    def __init__(
        self,
        path: Path | str = DEFAULT_HISTORY_PATH,
        *,
        dry_run: bool = False,
        retention_days: int = 180,
        max_retry_attempts: int = DEFAULT_MAX_RETRY_ATTEMPTS,
    ) -> None:
        self.path = Path(path)
        self.dry_run = dry_run
        self.retention_days = retention_days
        self.max_retry_attempts = max_retry_attempts
        self._migration_source_version: int | None = None
        self._migration_backup_created = False
        self._document = self._load_document()
        self._rebuild_indexes()

    @property
    def version(self) -> int:
        return self._document.version

    @property
    def jobs(self) -> dict[str, StoredJobRecord]:
        return self._document.jobs

    def _empty_document(self) -> HistoryDocument:
        return HistoryDocument(version=HISTORY_VERSION, jobs={})

    def _build_backup_path(self, *, suffix: str) -> Path:
        timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"{self.path.stem}.{timestamp}.{suffix}{self.path.suffix}.bak"
        backup_path = self.path.with_name(backup_name)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        return backup_path

    def _backup_existing_file(self, *, suffix: str) -> Path | None:
        if not self.path.exists():
            return None

        backup_path = self._build_backup_path(suffix=suffix)
        shutil.copy2(self.path, backup_path)
        return backup_path

    def _load_document(self) -> HistoryDocument:
        if not self.path.exists():
            return self._empty_document()

        try:
            raw_document = json.loads(self.path.read_text(encoding="utf-8"))
        except (JSONDecodeError, OSError) as exc:
            self._backup_existing_file(suffix="invalid")
            if isinstance(exc, OSError):
                raise HistoryStorageError(
                    f"Could not read history file: {self.path}"
                ) from exc
            return self._empty_document()

        if not isinstance(raw_document, dict):
            self._backup_existing_file(suffix="invalid")
            raise HistoryStorageError(f"Invalid history document in {self.path}")

        raw_version = raw_document.get("version", 1)
        if raw_version == HISTORY_VERSION:
            try:
                return HistoryDocument.model_validate(raw_document)
            except ValidationError as exc:
                self._backup_existing_file(suffix="invalid")
                raise HistoryStorageError(f"Invalid history document in {self.path}") from exc

        if raw_version != 1:
            self._backup_existing_file(suffix="unsupported")
            raise HistoryStorageError(
                f"Unsupported history version {raw_version} in {self.path}"
            )

        try:
            legacy_document = LegacyHistoryDocumentV1.model_validate(raw_document)
        except ValidationError as exc:
            self._backup_existing_file(suffix="invalid")
            raise HistoryStorageError(f"Invalid history document in {self.path}") from exc

        self._migration_source_version = 1
        migrated_jobs = {
            fingerprint: self._migrate_record_v1(record)
            for fingerprint, record in legacy_document.jobs.items()
        }
        return HistoryDocument(version=HISTORY_VERSION, jobs=migrated_jobs)

    def _migrate_record_v1(self, record: LegacyStoredJobRecordV1) -> StoredJobRecord:
        status, attempts, last_error_code, last_error_message, next_retry_at = (
            self._map_legacy_status(record)
        )
        job_snapshot = self._build_migrated_job_snapshot(record)
        score = record.score
        priority = _priority_from_score(score)
        score_explanation = (
            "Migrated from history version 1"
            if score is not None
            else "Migrated from history version 1 without stored score"
        )

        return StoredJobRecord(
            provider=record.provider,
            provider_job_id=record.provider_job_id,
            title=record.title,
            company=record.company,
            url=record.url,
            normalized_url=record.normalized_url,
            fingerprint=record.fingerprint,
            job_snapshot=job_snapshot,
            score=score,
            priority=priority,
            matched_skills=[],
            missing_skills=[],
            extracted_keywords=[],
            relevant_domains=[],
            rejection_reasons=[],
            score_explanation=score_explanation,
            status=status,
            attempts=attempts,
            last_error_code=last_error_code,
            last_error_message=last_error_message,
            next_retry_at=next_retry_at,
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
            notified_at=record.notified_at,
        )

    def _map_legacy_status(
        self,
        record: LegacyStoredJobRecordV1,
    ) -> tuple[JobStatus, int, str | None, str | None, datetime | None]:
        status = record.status.strip().casefold()
        if status == "rejected":
            return JobStatus.REJECTED, 0, None, None, None
        if status == "eligible":
            return JobStatus.QUEUED, 0, None, None, None
        if status == "resume_generated":
            return JobStatus.QUEUED, 0, None, None, None
        if status == "notified":
            return JobStatus.NOTIFIED, 0, None, None, None
        if status == "resume_failed":
            return (
                JobStatus.RETRY_PENDING,
                1,
                "migrated_resume_failed",
                "Migrated failed resume generation from history version 1",
                record.last_seen_at,
            )
        if status == "notification_failed":
            return (
                JobStatus.RETRY_PENDING,
                1,
                "migrated_notification_failed",
                "Migrated failed notification from history version 1",
                record.last_seen_at,
            )
        return (
            JobStatus.DEAD_LETTER,
            1,
            "migrated_unknown_status",
            "Migrated unknown legacy status",
            None,
        )

    def _build_migrated_job_snapshot(self, record: LegacyStoredJobRecordV1) -> JobPosting:
        return JobPosting.model_validate(
            {
                "provider": record.provider,
                "provider_job_id": record.provider_job_id,
                "title": record.title,
                "company": record.company,
                "location": None,
                "work_mode": None,
                "employment_type": None,
                "description": "",
                "salary": None,
                "published_at": None,
                "updated_at": record.last_seen_at,
                "url": record.url,
                "source_name": record.provider.title(),
                "search_term": None,
                "collected_at": record.last_seen_at,
            }
        )

    def _ensure_migration_backup(self) -> None:
        if self._migration_source_version is None or self._migration_backup_created:
            return
        self._backup_existing_file(suffix=f"v{self._migration_source_version}")
        self._migration_backup_created = True

    def _rebuild_indexes(self) -> None:
        self._provider_index: dict[str, str] = {}
        self._url_index: dict[str, str] = {}

        for fingerprint, record in self.jobs.items():
            if record.provider_job_id:
                provider_key = f"{record.provider.casefold()}::{record.provider_job_id.strip()}"
                self._provider_index[provider_key] = fingerprint
            self._url_index[record.normalized_url] = fingerprint

    def is_final_status(self, status: JobStatus) -> bool:
        return status in FINAL_JOB_STATUSES

    def get_processable_records(
        self,
        *,
        reference_time: datetime | None = None,
    ) -> list[StoredJobRecord]:
        now = (reference_time or utc_now()).astimezone(UTC)
        records: list[StoredJobRecord] = []

        for record in self.jobs.values():
            if record.status not in PROCESSABLE_JOB_STATUSES:
                continue
            if record.status is JobStatus.RETRY_PENDING:
                if record.next_retry_at is None or record.next_retry_at > now:
                    continue
            records.append(record.model_copy(deep=True))

        records.sort(
            key=lambda item: (
                -(item.score or 0),
                -(
                    item.job_snapshot.updated_at
                    or item.job_snapshot.published_at
                    or now
                ).timestamp(),
                item.title,
            )
        )
        return records

    def find_match(
        self,
        job: JobPosting,
        *,
        fingerprint: str | None = None,
    ) -> HistoryLookupResult | None:
        provider_key = make_provider_job_key(job)
        if provider_key and provider_key in self._provider_index:
            matched_fingerprint = self._provider_index[provider_key]
            return HistoryLookupResult(
                record=self.jobs[matched_fingerprint],
                reason=DuplicateReason.PROVIDER_JOB_ID,
                matched_key=provider_key,
            )

        normalized_url = make_normalized_job_url(job)
        if normalized_url in self._url_index:
            matched_fingerprint = self._url_index[normalized_url]
            return HistoryLookupResult(
                record=self.jobs[matched_fingerprint],
                reason=DuplicateReason.NORMALIZED_URL,
                matched_key=normalized_url,
            )

        resolved_fingerprint = fingerprint or make_job_identity_fingerprint(job)
        if resolved_fingerprint in self.jobs:
            return HistoryLookupResult(
                record=self.jobs[resolved_fingerprint],
                reason=DuplicateReason.FINGERPRINT,
                matched_key=resolved_fingerprint,
            )

        return None

    def record_job(
        self,
        job: JobPosting,
        *,
        status: JobStatus,
        score: int | None,
        seen_at: datetime | None = None,
        notified_at: datetime | None = None,
        fingerprint: str | None = None,
        evaluated_job: EvaluatedJob | None = None,
    ) -> StoredJobRecord:
        resolved_seen_at = _normalize_datetime(seen_at) or utc_now()
        resolved_notified_at = _normalize_datetime(notified_at)
        resolved_fingerprint = fingerprint or make_job_identity_fingerprint(job)
        lookup = self.find_match(job, fingerprint=resolved_fingerprint)
        normalized_url = make_normalized_job_url(job)

        if lookup is not None:
            existing = lookup.record.model_copy(deep=True)
            existing.provider = job.provider
            existing.provider_job_id = job.provider_job_id
            existing.title = job.title
            existing.company = job.company
            existing.url = str(job.url)
            existing.normalized_url = normalized_url
            existing.fingerprint = resolved_fingerprint
            existing.job_snapshot = job.model_copy(deep=True)
            existing.score = score
            existing.status = status
            existing.last_seen_at = resolved_seen_at
            if evaluated_job is not None:
                _update_record_from_evaluation(existing, evaluated_job)
            if status in {
                JobStatus.QUEUED,
                JobStatus.RESUME_GENERATED,
                JobStatus.NOTIFIED,
                JobStatus.REJECTED,
            }:
                existing.next_retry_at = None
                existing.last_error_code = None
                existing.last_error_message = None
            if resolved_notified_at is not None:
                existing.notified_at = resolved_notified_at
            elif status is JobStatus.NOTIFIED:
                existing.notified_at = resolved_seen_at

            self.jobs[lookup.record.fingerprint] = existing
            self._rebuild_indexes()
            return existing

        created = StoredJobRecord(
            provider=job.provider,
            provider_job_id=job.provider_job_id,
            title=job.title,
            company=job.company,
            url=str(job.url),
            normalized_url=normalized_url,
            fingerprint=resolved_fingerprint,
            job_snapshot=job.model_copy(deep=True),
            score=score,
            priority=(
                evaluated_job.priority
                if evaluated_job is not None
                else _priority_from_score(score)
            ),
            matched_skills=evaluated_job.matched_skills.copy() if evaluated_job is not None else [],
            missing_skills=evaluated_job.missing_skills.copy() if evaluated_job is not None else [],
            extracted_keywords=(
                evaluated_job.extracted_keywords.copy() if evaluated_job is not None else []
            ),
            relevant_domains=(
                evaluated_job.relevant_domains.copy() if evaluated_job is not None else []
            ),
            rejection_reasons=(
                evaluated_job.rejection_reasons.copy() if evaluated_job is not None else []
            ),
            score_explanation=(
                evaluated_job.score_explanation if evaluated_job is not None else None
            ),
            status=status,
            first_seen_at=resolved_seen_at,
            last_seen_at=resolved_seen_at,
            notified_at=resolved_notified_at if resolved_notified_at is not None else None,
        )
        if status is JobStatus.NOTIFIED and created.notified_at is None:
            created.notified_at = resolved_seen_at

        self.jobs[resolved_fingerprint] = created
        self._rebuild_indexes()
        return created

    def record_failure(
        self,
        job: JobPosting,
        *,
        score: int | None,
        error_code: str,
        error_message: str,
        seen_at: datetime | None = None,
        fingerprint: str | None = None,
        evaluated_job: EvaluatedJob | None = None,
    ) -> StoredJobRecord:
        resolved_seen_at = _normalize_datetime(seen_at) or utc_now()
        resolved_fingerprint = fingerprint or make_job_identity_fingerprint(job)
        lookup = self.find_match(job, fingerprint=resolved_fingerprint)
        existing_attempts = lookup.record.attempts if lookup is not None else 0
        attempts = existing_attempts + 1
        status = JobStatus.RETRY_PENDING
        next_retry_at: datetime | None = resolved_seen_at + _retry_backoff_for_attempt(attempts)
        if attempts >= self.max_retry_attempts:
            status = JobStatus.DEAD_LETTER
            next_retry_at = None

        record = self.record_job(
            job,
            status=status,
            score=score,
            seen_at=resolved_seen_at,
            fingerprint=resolved_fingerprint,
            evaluated_job=evaluated_job,
        )
        record.attempts = attempts
        record.last_error_code = error_code
        record.last_error_message = _normalize_error_message(error_message)
        record.next_retry_at = next_retry_at
        self.jobs[record.fingerprint] = record
        self._rebuild_indexes()
        return record

    def prune(self, *, reference_time: datetime | None = None) -> list[str]:
        cutoff = (reference_time or utc_now()).astimezone(UTC) - timedelta(days=self.retention_days)
        fingerprints_to_remove = [
            fingerprint
            for fingerprint, record in self.jobs.items()
            if record.last_seen_at < cutoff
        ]

        for fingerprint in fingerprints_to_remove:
            self.jobs.pop(fingerprint, None)

        if fingerprints_to_remove:
            self._rebuild_indexes()

        return fingerprints_to_remove

    def save(self) -> None:
        if self.dry_run:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_migration_backup()
        document = HistoryDocument(version=HISTORY_VERSION, jobs=self.jobs)
        payload = json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2)

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=self.path.parent,
                prefix=f"{self.path.stem}.",
                suffix=".tmp",
            ) as temp_file:
                temp_file.write(payload)
                temp_path = Path(temp_file.name)

            os.replace(temp_path, self.path)
        except OSError as exc:
            raise HistoryStorageError(f"Could not persist history file: {self.path}") from exc
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()


def _priority_from_score(score: int | None) -> Priority | None:
    if score is None:
        return None
    if score >= 85:
        return Priority.HIGH
    if score >= 70:
        return Priority.GOOD
    return Priority.BELOW_THRESHOLD


def _retry_backoff_for_attempt(attempt: int) -> timedelta:
    if attempt <= 0:
        return timedelta(0)
    index = min(attempt - 1, len(RETRY_BACKOFF_SCHEDULE) - 1)
    return RETRY_BACKOFF_SCHEDULE[index]


def _update_record_from_evaluation(record: StoredJobRecord, evaluated_job: EvaluatedJob) -> None:
    record.priority = evaluated_job.priority
    record.matched_skills = evaluated_job.matched_skills.copy()
    record.missing_skills = evaluated_job.missing_skills.copy()
    record.extracted_keywords = evaluated_job.extracted_keywords.copy()
    record.relevant_domains = evaluated_job.relevant_domains.copy()
    record.rejection_reasons = evaluated_job.rejection_reasons.copy()
    record.score_explanation = evaluated_job.score_explanation
