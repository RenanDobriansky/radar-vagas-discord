"""Regras de deduplicacao de vagas.

Ordem aplicada, conforme a especificacao:
1. provider + provider_job_id;
2. URL normalizada;
3. fingerprint de titulo + empresa + localizacao.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from radar_vagas.models import JobPosting
from radar_vagas.text_utils import make_job_fingerprint, normalize_text, normalize_url


class DuplicateReason(StrEnum):
    """Motivo pelo qual uma vaga foi considerada duplicada."""

    PROVIDER_JOB_ID = "provider_job_id"
    NORMALIZED_URL = "normalized_url"
    FINGERPRINT = "fingerprint"


@dataclass(slots=True)
class DuplicateRecord:
    """Representa uma vaga descartada por deduplicacao."""

    job: JobPosting
    duplicate_of: JobPosting
    reason: DuplicateReason
    matched_key: str


@dataclass(slots=True)
class DeduplicationResult:
    """Resultado da deduplicacao de uma lista de vagas."""

    unique_jobs: list[JobPosting] = field(default_factory=list)
    duplicates: list[DuplicateRecord] = field(default_factory=list)


def make_provider_job_key(job: JobPosting) -> str | None:
    """Gera a chave forte provider+id quando o provider_job_id existe."""
    if not job.provider_job_id:
        return None

    provider = normalize_text(job.provider)
    provider_job_id = job.provider_job_id.strip()
    if not provider_job_id:
        return None

    return f"{provider}::{provider_job_id}"


def make_normalized_job_url(job: JobPosting) -> str:
    """Retorna a URL normalizada da vaga."""
    return normalize_url(str(job.url))


def make_job_identity_fingerprint(job: JobPosting) -> str:
    """Retorna o fingerprint de identidade textual da vaga."""
    return make_job_fingerprint(job.title, job.company, job.location)


def deduplicate_jobs(jobs: list[JobPosting]) -> DeduplicationResult:
    """Remove duplicatas seguindo a ordem de prioridade definida no contexto."""
    provider_index: dict[str, JobPosting] = {}
    url_index: dict[str, JobPosting] = {}
    fingerprint_index: dict[str, JobPosting] = {}
    result = DeduplicationResult()

    for job in jobs:
        provider_key = make_provider_job_key(job)
        if provider_key and provider_key in provider_index:
            result.duplicates.append(
                DuplicateRecord(
                    job=job,
                    duplicate_of=provider_index[provider_key],
                    reason=DuplicateReason.PROVIDER_JOB_ID,
                    matched_key=provider_key,
                )
            )
            continue

        normalized_job_url = make_normalized_job_url(job)
        if normalized_job_url in url_index:
            result.duplicates.append(
                DuplicateRecord(
                    job=job,
                    duplicate_of=url_index[normalized_job_url],
                    reason=DuplicateReason.NORMALIZED_URL,
                    matched_key=normalized_job_url,
                )
            )
            continue

        fingerprint = make_job_identity_fingerprint(job)
        if fingerprint in fingerprint_index:
            result.duplicates.append(
                DuplicateRecord(
                    job=job,
                    duplicate_of=fingerprint_index[fingerprint],
                    reason=DuplicateReason.FINGERPRINT,
                    matched_key=fingerprint,
                )
            )
            continue

        result.unique_jobs.append(job)

        if provider_key:
            provider_index[provider_key] = job
        url_index[normalized_job_url] = job
        fingerprint_index[fingerprint] = job

    return result
