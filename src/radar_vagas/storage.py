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
from radar_vagas.models import JobPosting, JobStatus, utc_now

HISTORY_VERSION = 1
DEFAULT_HISTORY_PATH = Path("data/seen_jobs.json")


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


class StoredJobRecord(BaseModel):
    """Registro persistido para uma vaga ja processada."""

    provider: str
    provider_job_id: str | None = None
    title: str
    company: str | None = None
    url: str
    normalized_url: str
    fingerprint: str
    score: int | None = Field(default=None, ge=0, le=100)
    status: JobStatus
    first_seen_at: datetime
    last_seen_at: datetime
    notified_at: datetime | None = None

    @field_validator("first_seen_at", "last_seen_at", "notified_at", mode="before")
    @classmethod
    def normalize_timestamps(cls, value: datetime | str | None) -> datetime | None:
        return _normalize_datetime(value)


class HistoryDocument(BaseModel):
    """Documento JSON persistido em `data/seen_jobs.json`."""

    version: int = HISTORY_VERSION
    jobs: dict[str, StoredJobRecord] = Field(default_factory=dict)


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
    ) -> None:
        self.path = Path(path)
        self.dry_run = dry_run
        self.retention_days = retention_days
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

    def _backup_invalid_file(self) -> Path | None:
        if not self.path.exists():
            return None

        timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"{self.path.stem}.{timestamp}.invalid{self.path.suffix}.bak"
        backup_path = self.path.with_name(backup_name)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.path, backup_path)
        return backup_path

    def _load_document(self) -> HistoryDocument:
        if not self.path.exists():
            return self._empty_document()

        try:
            raw_document = json.loads(self.path.read_text(encoding="utf-8"))
        except (JSONDecodeError, OSError) as exc:
            self._backup_invalid_file()
            if isinstance(exc, OSError):
                raise HistoryStorageError(
                    f"Could not read history file: {self.path}"
                ) from exc
            return self._empty_document()

        try:
            return HistoryDocument.model_validate(raw_document)
        except ValidationError as exc:
            self._backup_invalid_file()
            raise HistoryStorageError(f"Invalid history document in {self.path}") from exc

    def _rebuild_indexes(self) -> None:
        self._provider_index: dict[str, str] = {}
        self._url_index: dict[str, str] = {}

        for fingerprint, record in self.jobs.items():
            if record.provider_job_id:
                provider_key = f"{record.provider.casefold()}::{record.provider_job_id.strip()}"
                self._provider_index[provider_key] = fingerprint
            self._url_index[record.normalized_url] = fingerprint

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
            existing.score = score
            existing.status = status
            existing.last_seen_at = resolved_seen_at
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
            score=score,
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
