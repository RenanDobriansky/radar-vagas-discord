"""Persistencia local do historico de vagas em JSON."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from json import JSONDecodeError
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from radar_vagas.deduplication import (
    DuplicateReason,
    make_job_identity_fingerprint,
    make_normalized_job_url,
    make_provider_job_key,
)
from radar_vagas.models import (
    EvaluatedJob,
    JobPosting,
    JobStatus,
    Priority,
    Seniority,
    WorkMode,
    utc_now,
)

HISTORY_VERSION = 3
DEFAULT_HISTORY_PATH = Path("data/seen_jobs.json")
DEFAULT_STATE_BRANCH = "radar-state"
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
STATUS_MERGE_PRIORITY = {
    JobStatus.NOTIFIED: 6,
    JobStatus.REJECTED: 5,
    JobStatus.DEAD_LETTER: 4,
    JobStatus.RESUME_GENERATED: 3,
    JobStatus.RETRY_PENDING: 2,
    JobStatus.QUEUED: 1,
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


def _build_url_hash(normalized_url: str) -> str:
    return sha256(normalized_url.encode("utf-8")).hexdigest()


def _make_normalized_url_hash(job: JobPosting) -> str:
    return _build_url_hash(make_normalized_job_url(job))


class StoredJobSnapshot(BaseModel):
    """Snapshot minimo da vaga necessario para retries e auditoria."""

    title: str
    company: str | None = None
    location: str | None = None
    seniority: Seniority | None = None
    work_mode: WorkMode | None = None
    employment_type: str | None = None
    url: str
    source_name: str
    search_term: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    collected_at: datetime

    @field_validator(
        "published_at",
        "updated_at",
        "collected_at",
        mode="before",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | str | None) -> datetime | None:
        return _normalize_datetime(value)

    @classmethod
    def from_job_posting(cls, job: JobPosting) -> StoredJobSnapshot:
        return cls.model_validate(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "seniority": job.seniority,
                "work_mode": job.work_mode,
                "employment_type": job.employment_type,
                "url": str(job.url),
                "source_name": job.source_name,
                "search_term": job.search_term,
                "published_at": job.published_at,
                "updated_at": job.updated_at,
                "collected_at": job.collected_at,
            }
        )

    def to_job_posting(
        self,
        *,
        provider: str,
        provider_job_id: str | None,
    ) -> JobPosting:
        return JobPosting.model_validate(
            {
                "provider": provider,
                "provider_job_id": provider_job_id,
                "title": self.title,
                "company": self.company,
                "location": self.location,
                "seniority": self.seniority,
                "work_mode": self.work_mode,
                "employment_type": self.employment_type,
                "description": "",
                "salary": None,
                "published_at": self.published_at,
                "updated_at": self.updated_at,
                "url": self.url,
                "source_name": self.source_name,
                "search_term": self.search_term,
                "collected_at": self.collected_at,
            }
        )


class StoredJobRecord(BaseModel):
    """Registro persistido para uma vaga ja processada ou enfileirada."""

    provider: str
    provider_job_id: str | None = None
    normalized_url_hash: str
    fingerprint: str
    job_snapshot: StoredJobSnapshot
    score: int | None = Field(default=None, ge=0, le=100)
    priority: Priority | None = None
    required_skills: list[str] = Field(default_factory=list)
    matched_candidate_skills: list[str] = Field(default_factory=list)
    candidate_skill_gaps: list[str] = Field(default_factory=list)
    optional_job_skills: list[str] = Field(default_factory=list)
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

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_skill_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        if "matched_candidate_skills" not in payload and "matched_skills" in payload:
            payload["matched_candidate_skills"] = payload["matched_skills"]
        if "candidate_skill_gaps" not in payload and "missing_skills" in payload:
            payload["candidate_skill_gaps"] = payload["missing_skills"]
        if "required_skills" not in payload:
            payload["required_skills"] = payload.get("matched_candidate_skills") or payload.get(
                "matched_skills",
                [],
            )
        if "optional_job_skills" not in payload:
            payload["optional_job_skills"] = []
        return payload

    @property
    def matched_skills(self) -> list[str]:
        return self.matched_candidate_skills

    @property
    def missing_skills(self) -> list[str]:
        return self.candidate_skill_gaps

    @property
    def title(self) -> str:
        return self.job_snapshot.title

    @property
    def company(self) -> str | None:
        return self.job_snapshot.company


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


class LegacyStoredJobRecordV2(BaseModel):
    """Schema legado da versao 2 do historico."""

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
    required_skills: list[str] = Field(default_factory=list)
    matched_candidate_skills: list[str] = Field(default_factory=list)
    candidate_skill_gaps: list[str] = Field(default_factory=list)
    optional_job_skills: list[str] = Field(default_factory=list)
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


class LegacyHistoryDocumentV2(BaseModel):
    """Documento JSON persistido no formato legado v2."""

    version: int = 2
    jobs: dict[str, LegacyStoredJobRecordV2] = Field(default_factory=dict)


@dataclass(slots=True)
class HistoryLookupResult:
    """Representa um match encontrado no historico."""

    record: StoredJobRecord
    reason: DuplicateReason
    matched_key: str


def load_history_document(path: Path | str) -> HistoryDocument:
    """Carrega um documento de historico, aplicando migracao quando necessario."""
    return JobHistoryStore(path, dry_run=True).to_document()


def write_history_document(path: Path | str, document: HistoryDocument) -> None:
    """Persiste um documento de historico com escrita atomica."""
    _persist_history_document(Path(path), document)


def merge_history_documents(
    primary: HistoryDocument,
    secondary: HistoryDocument,
) -> HistoryDocument:
    """Combina dois documentos de historico preservando o estado mais forte e mais recente."""
    merged_jobs: dict[str, StoredJobRecord] = {}
    fingerprints = set(primary.jobs) | set(secondary.jobs)

    for fingerprint in fingerprints:
        left = primary.jobs.get(fingerprint)
        right = secondary.jobs.get(fingerprint)
        if left is None and right is not None:
            merged_jobs[fingerprint] = right.model_copy(deep=True)
            continue
        if right is None and left is not None:
            merged_jobs[fingerprint] = left.model_copy(deep=True)
            continue
        if left is None or right is None:
            continue
        merged_jobs[fingerprint] = _merge_record_pair(left, right)

    return HistoryDocument(version=HISTORY_VERSION, jobs=merged_jobs)


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

    def to_document(self) -> HistoryDocument:
        return self._document.model_copy(deep=True)

    def replace_document(self, document: HistoryDocument) -> None:
        self._document = document.model_copy(deep=True)
        self._rebuild_indexes()

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

        if raw_version == 2:
            try:
                legacy_document = LegacyHistoryDocumentV2.model_validate(raw_document)
            except ValidationError as exc:
                self._backup_existing_file(suffix="invalid")
                raise HistoryStorageError(f"Invalid history document in {self.path}") from exc

            self._migration_source_version = 2
            migrated_jobs = {
                fingerprint: self._migrate_record_v2(record)
                for fingerprint, record in legacy_document.jobs.items()
            }
            return HistoryDocument(version=HISTORY_VERSION, jobs=migrated_jobs)

        if raw_version == 1:
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

        self._backup_existing_file(suffix="unsupported")
        raise HistoryStorageError(
            f"Unsupported history version {raw_version} in {self.path}"
        )

    def _migrate_record_v1(self, record: LegacyStoredJobRecordV1) -> StoredJobRecord:
        status, attempts, last_error_code, last_error_message, next_retry_at = (
            self._map_legacy_status(record)
        )
        score = record.score
        priority = _priority_from_score(score)
        score_explanation = (
            "Migrated from history version 1"
            if score is not None
            else "Migrated from history version 1 without stored score"
        )
        snapshot = StoredJobSnapshot.model_validate(
            {
                "title": record.title,
                "company": record.company,
                "location": None,
                "seniority": None,
                "work_mode": None,
                "employment_type": None,
                "url": record.url,
                "source_name": record.provider.title(),
                "search_term": None,
                "published_at": None,
                "updated_at": record.last_seen_at,
                "collected_at": record.last_seen_at,
            }
        )

        return StoredJobRecord(
            provider=record.provider,
            provider_job_id=record.provider_job_id,
            normalized_url_hash=_build_url_hash(record.normalized_url),
            fingerprint=record.fingerprint,
            job_snapshot=snapshot,
            score=score,
            priority=priority,
            required_skills=[],
            matched_candidate_skills=[],
            candidate_skill_gaps=[],
            optional_job_skills=[],
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

    def _migrate_record_v2(self, record: LegacyStoredJobRecordV2) -> StoredJobRecord:
        return StoredJobRecord(
            provider=record.provider,
            provider_job_id=record.provider_job_id,
            normalized_url_hash=_build_url_hash(record.normalized_url),
            fingerprint=record.fingerprint,
            job_snapshot=StoredJobSnapshot.from_job_posting(record.job_snapshot),
            score=record.score,
            priority=record.priority,
            required_skills=record.required_skills.copy(),
            matched_candidate_skills=record.matched_candidate_skills.copy(),
            candidate_skill_gaps=record.candidate_skill_gaps.copy(),
            optional_job_skills=record.optional_job_skills.copy(),
            extracted_keywords=record.extracted_keywords.copy(),
            relevant_domains=record.relevant_domains.copy(),
            rejection_reasons=record.rejection_reasons.copy(),
            score_explanation=record.score_explanation,
            status=record.status,
            attempts=record.attempts,
            last_error_code=record.last_error_code,
            last_error_message=record.last_error_message,
            next_retry_at=record.next_retry_at,
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

    def _ensure_migration_backup(self) -> None:
        if self._migration_source_version is None or self._migration_backup_created:
            return
        self._backup_existing_file(suffix=f"v{self._migration_source_version}")
        self._migration_backup_created = True

    def _rebuild_indexes(self) -> None:
        self._provider_index: dict[str, str] = {}
        self._url_hash_index: dict[str, str] = {}

        for fingerprint, record in self.jobs.items():
            if record.provider_job_id:
                provider_key = f"{record.provider.casefold()}::{record.provider_job_id.strip()}"
                self._provider_index[provider_key] = fingerprint
            self._url_hash_index[record.normalized_url_hash] = fingerprint

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

        normalized_url_hash = _make_normalized_url_hash(job)
        if normalized_url_hash in self._url_hash_index:
            matched_fingerprint = self._url_hash_index[normalized_url_hash]
            return HistoryLookupResult(
                record=self.jobs[matched_fingerprint],
                reason=DuplicateReason.NORMALIZED_URL,
                matched_key=normalized_url_hash,
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
        normalized_url_hash = _make_normalized_url_hash(job)
        snapshot = StoredJobSnapshot.from_job_posting(job)

        if lookup is not None:
            existing = lookup.record.model_copy(deep=True)
            previous_fingerprint = lookup.record.fingerprint
            existing.provider = job.provider
            existing.provider_job_id = job.provider_job_id
            existing.normalized_url_hash = normalized_url_hash
            existing.fingerprint = resolved_fingerprint
            existing.job_snapshot = snapshot
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

            if previous_fingerprint != resolved_fingerprint:
                self.jobs.pop(previous_fingerprint, None)
            self.jobs[resolved_fingerprint] = existing
            self._rebuild_indexes()
            return existing

        created = StoredJobRecord(
            provider=job.provider,
            provider_job_id=job.provider_job_id,
            normalized_url_hash=normalized_url_hash,
            fingerprint=resolved_fingerprint,
            job_snapshot=snapshot,
            score=score,
            priority=(
                evaluated_job.priority
                if evaluated_job is not None
                else _priority_from_score(score)
            ),
            required_skills=(
                evaluated_job.required_skills.copy() if evaluated_job is not None else []
            ),
            matched_candidate_skills=(
                evaluated_job.matched_candidate_skills.copy()
                if evaluated_job is not None
                else []
            ),
            candidate_skill_gaps=(
                evaluated_job.candidate_skill_gaps.copy()
                if evaluated_job is not None
                else []
            ),
            optional_job_skills=(
                evaluated_job.optional_job_skills.copy()
                if evaluated_job is not None
                else []
            ),
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

        self._ensure_migration_backup()
        _persist_history_document(
            self.path,
            HistoryDocument(version=HISTORY_VERSION, jobs=self.jobs),
        )


def _persist_history_document(path: Path, document: HistoryDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f"{path.stem}.",
            suffix=".tmp",
        ) as temp_file:
            temp_file.write(payload)
            temp_path = Path(temp_file.name)

        os.replace(temp_path, path)
    except OSError as exc:
        raise HistoryStorageError(f"Could not persist history file: {path}") from exc
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
    record.required_skills = evaluated_job.required_skills.copy()
    record.matched_candidate_skills = evaluated_job.matched_candidate_skills.copy()
    record.candidate_skill_gaps = evaluated_job.candidate_skill_gaps.copy()
    record.optional_job_skills = evaluated_job.optional_job_skills.copy()
    record.extracted_keywords = evaluated_job.extracted_keywords.copy()
    record.relevant_domains = evaluated_job.relevant_domains.copy()
    record.rejection_reasons = evaluated_job.rejection_reasons.copy()
    record.score_explanation = evaluated_job.score_explanation


def _merge_record_pair(left: StoredJobRecord, right: StoredJobRecord) -> StoredJobRecord:
    preferred = _preferred_record(left, right)
    alternate = right if preferred is left else left
    merged = preferred.model_copy(deep=True)

    merged.provider = preferred.provider or alternate.provider
    merged.provider_job_id = preferred.provider_job_id or alternate.provider_job_id
    merged.normalized_url_hash = preferred.normalized_url_hash or alternate.normalized_url_hash
    merged.fingerprint = preferred.fingerprint or alternate.fingerprint
    merged.job_snapshot = preferred.job_snapshot.model_copy(deep=True)
    merged.score = preferred.score if preferred.score is not None else alternate.score
    merged.priority = preferred.priority or alternate.priority or _priority_from_score(merged.score)
    merged.required_skills = _merge_ordered_values(
        preferred.required_skills,
        alternate.required_skills,
    )
    merged.matched_candidate_skills = _merge_ordered_values(
        preferred.matched_candidate_skills,
        alternate.matched_candidate_skills,
    )
    merged.candidate_skill_gaps = _merge_ordered_values(
        preferred.candidate_skill_gaps,
        alternate.candidate_skill_gaps,
    )
    merged.optional_job_skills = _merge_ordered_values(
        preferred.optional_job_skills,
        alternate.optional_job_skills,
    )
    merged.extracted_keywords = _merge_ordered_values(
        preferred.extracted_keywords,
        alternate.extracted_keywords,
    )
    merged.relevant_domains = _merge_ordered_values(
        preferred.relevant_domains,
        alternate.relevant_domains,
    )
    merged.rejection_reasons = _merge_ordered_values(
        preferred.rejection_reasons,
        alternate.rejection_reasons,
    )
    merged.score_explanation = preferred.score_explanation or alternate.score_explanation
    merged.attempts = max(left.attempts, right.attempts)
    merged.first_seen_at = min(left.first_seen_at, right.first_seen_at)
    merged.last_seen_at = max(left.last_seen_at, right.last_seen_at)
    merged.notified_at = _max_datetime(left.notified_at, right.notified_at)

    error_source = left if left.attempts >= right.attempts else right
    merged.last_error_code = error_source.last_error_code
    merged.last_error_message = error_source.last_error_message
    merged.next_retry_at = _max_datetime(left.next_retry_at, right.next_retry_at)

    if merged.status not in {JobStatus.RETRY_PENDING, JobStatus.DEAD_LETTER}:
        merged.last_error_code = None
        merged.last_error_message = None
        merged.next_retry_at = None

    return merged


def _preferred_record(left: StoredJobRecord, right: StoredJobRecord) -> StoredJobRecord:
    left_tuple = _record_preference_tuple(left)
    right_tuple = _record_preference_tuple(right)
    return left if left_tuple >= right_tuple else right


def _record_preference_tuple(record: StoredJobRecord) -> tuple[int, float, float, int, int]:
    return (
        STATUS_MERGE_PRIORITY[record.status],
        record.last_seen_at.timestamp(),
        record.notified_at.timestamp() if record.notified_at is not None else -1.0,
        record.attempts,
        record.score or -1,
    )


def _merge_ordered_values(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []

    for value in [*primary, *secondary]:
        if value in seen:
            continue
        seen.add(value)
        merged.append(value)

    return merged


def _max_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
