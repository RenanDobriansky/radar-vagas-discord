from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from radar_vagas.deduplication import DuplicateReason
from radar_vagas.models import JobPosting, JobStatus, WorkMode
from radar_vagas.storage import JobHistoryStore


def build_job_posting(**overrides: object) -> JobPosting:
    payload = {
        "provider": "jooble",
        "provider_job_id": "123",
        "title": "Analista de Dados Junior",
        "company": "Empresa X",
        "location": "Curitiba - PR",
        "work_mode": WorkMode.HYBRID,
        "employment_type": "CLT",
        "description": "SQL e Power BI.",
        "salary": None,
        "published_at": "2026-06-23T08:00:00Z",
        "updated_at": "2026-06-23T10:00:00Z",
        "url": "https://example.com/jobs/123?utm_source=linkedin&id=55",
        "source_name": "Jooble",
        "search_term": "Analista de Dados",
        "collected_at": "2026-06-23T11:30:00Z",
    }
    payload.update(overrides)
    return JobPosting.model_validate(payload)


def test_storage_initializes_empty_structure_when_file_does_not_exist(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"

    store = JobHistoryStore(history_path)

    assert store.version == 1
    assert store.jobs == {}
    store.save()
    saved = json.loads(history_path.read_text(encoding="utf-8"))
    assert saved == {"version": 1, "jobs": {}}


def test_storage_persists_and_reloads_history(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    store = JobHistoryStore(history_path)
    job = build_job_posting()

    store.record_job(
        job,
        status=JobStatus.ELIGIBLE,
        score=82,
        seen_at=datetime(2026, 6, 23, 12, 0, tzinfo=UTC),
    )
    store.save()

    reloaded = JobHistoryStore(history_path)
    stored_record = next(iter(reloaded.jobs.values()))
    assert stored_record.status is JobStatus.ELIGIBLE
    assert stored_record.score == 82
    assert stored_record.first_seen_at == datetime(2026, 6, 23, 12, 0, tzinfo=UTC)
    assert stored_record.last_seen_at == datetime(2026, 6, 23, 12, 0, tzinfo=UTC)


def test_storage_finds_duplicates_by_provider_url_and_fingerprint(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    store = JobHistoryStore(history_path)
    base_job = build_job_posting()
    store.record_job(base_job, status=JobStatus.ELIGIBLE, score=80)

    same_provider_id = build_job_posting(
        provider_job_id="123",
        url="https://example.com/other?id=999",
        title="Outro titulo",
        company="Outra empresa",
    )
    same_url = build_job_posting(provider_job_id=None, url="https://example.com/jobs/123?id=55&utm_medium=email")
    same_fingerprint = build_job_posting(
        provider_job_id=None,
        url="https://another.example/jobs/abc",
        title="ANALISTA DE DADOS JUNIOR",
        company="empresa x",
        location="CURITIBA - PR",
    )

    assert store.find_match(same_provider_id).reason is DuplicateReason.PROVIDER_JOB_ID
    assert store.find_match(same_url).reason is DuplicateReason.NORMALIZED_URL
    assert store.find_match(same_fingerprint).reason is DuplicateReason.FINGERPRINT


def test_storage_creates_backup_when_json_is_invalid(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    history_path.write_text("{invalid json", encoding="utf-8")

    store = JobHistoryStore(history_path)

    assert store.jobs == {}
    backups = list(tmp_path.glob("seen_jobs.*.invalid.json.bak"))
    assert backups, "expected a backup file to be created"


def test_storage_uses_atomic_replace_on_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_path = tmp_path / "seen_jobs.json"
    store = JobHistoryStore(history_path)
    store.record_job(build_job_posting(), status=JobStatus.REJECTED, score=40)

    calls: list[tuple[str, str]] = []
    original_replace = os.replace

    def tracking_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        calls.append((str(src), str(dst)))
        original_replace(src, dst)

    monkeypatch.setattr("radar_vagas.storage.os.replace", tracking_replace)

    store.save()

    assert calls
    assert calls[0][1] == str(history_path)


def test_storage_does_not_persist_in_dry_run_mode(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    store = JobHistoryStore(history_path, dry_run=True)

    store.record_job(build_job_posting(), status=JobStatus.NOTIFIED, score=88)
    store.save()

    assert not history_path.exists()


def test_storage_prunes_records_older_than_retention_window(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    store = JobHistoryStore(history_path, retention_days=180)

    old_seen_at = datetime(2025, 12, 1, 12, 0, tzinfo=UTC)
    fresh_seen_at = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)

    store.record_job(
        build_job_posting(provider_job_id="old-1", url="https://example.com/jobs/old"),
        status=JobStatus.REJECTED,
        score=10,
        seen_at=old_seen_at,
    )
    store.record_job(
        build_job_posting(
            provider_job_id="new-1",
            url="https://example.com/jobs/new",
            company="Empresa Y",
        ),
        status=JobStatus.ELIGIBLE,
        score=90,
        seen_at=fresh_seen_at,
    )

    removed = store.prune(reference_time=datetime(2026, 6, 23, 12, 0, tzinfo=UTC))

    assert len(removed) == 1
    assert len(store.jobs) == 1


def test_storage_updates_last_seen_and_notified_at_on_rewrite(tmp_path: Path) -> None:
    history_path = tmp_path / "seen_jobs.json"
    store = JobHistoryStore(history_path)
    job = build_job_posting()

    store.record_job(
        job,
        status=JobStatus.ELIGIBLE,
        score=75,
        seen_at=datetime(2026, 6, 23, 10, 0, tzinfo=UTC),
    )
    store.record_job(
        job,
        status=JobStatus.NOTIFIED,
        score=88,
        seen_at=datetime(2026, 6, 23, 12, 0, tzinfo=UTC),
    )

    stored = next(iter(store.jobs.values()))
    assert stored.first_seen_at == datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    assert stored.last_seen_at == datetime(2026, 6, 23, 12, 0, tzinfo=UTC)
    assert stored.notified_at == datetime(2026, 6, 23, 12, 0, tzinfo=UTC)
