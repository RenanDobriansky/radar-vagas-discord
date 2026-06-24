from __future__ import annotations

from radar_vagas.deduplication import (
    DuplicateReason,
    deduplicate_jobs,
    make_job_identity_fingerprint,
    make_normalized_job_url,
)
from radar_vagas.models import JobPosting, WorkMode
from radar_vagas.text_utils import make_job_fingerprint, normalize_text, normalize_url


def build_job_posting(**overrides: object) -> JobPosting:
    payload = {
        "provider": "jooble",
        "provider_job_id": "123",
        "title": "Análise de Dados Júnior",
        "company": "Empresa São José",
        "location": "Curitiba",
        "work_mode": WorkMode.HYBRID,
        "employment_type": "CLT",
        "description": "Atuacao com SQL e Power BI.",
        "salary": None,
        "published_at": "2026-06-23T08:00:00-03:00",
        "updated_at": "2026-06-23T12:00:00-03:00",
        "url": "https://example.com/vagas/123?utm_source=linkedin&id=55",
        "source_name": "Jooble",
        "search_term": "Analista de Dados",
        "collected_at": "2026-06-23T11:30:00-03:00",
    }
    payload.update(overrides)
    return JobPosting.model_validate(payload)


def test_normalize_text_removes_accents_case_and_extra_spaces() -> None:
    assert normalize_text("  Análise   de DÁDOS  Júnior ") == "analise de dados junior"


def test_normalize_url_removes_tracking_params_but_preserves_functional_ones() -> None:
    normalized = normalize_url(
        "HTTPS://Example.com/vagas/123/?utm_source=linkedin&id=55&gclid=abc&vaga=bi"
    )

    assert normalized == "https://example.com/vagas/123?id=55&vaga=bi"


def test_make_job_fingerprint_ignores_case_and_accents() -> None:
    left = make_job_fingerprint("Análise de Dados Júnior", "Empresa São José", "Curitiba")
    right = make_job_fingerprint("analise de dados junior", "empresa sao jose", " CURITIBA ")

    assert left == right


def test_make_job_fingerprint_keeps_companies_separate() -> None:
    left = make_job_fingerprint("Analista de Dados", "Empresa A", "Curitiba")
    right = make_job_fingerprint("Analista de Dados", "Empresa B", "Curitiba")

    assert left != right


def test_deduplicate_jobs_prefers_provider_job_id_before_url_and_fingerprint() -> None:
    original = build_job_posting()
    duplicate = build_job_posting(
        provider_job_id="123",
        url="https://example.com/outra-url?id=999",
        title="Outro titulo",
        company="Outra empresa",
    )

    result = deduplicate_jobs([original, duplicate])

    assert len(result.unique_jobs) == 1
    assert len(result.duplicates) == 1
    assert result.duplicates[0].reason is DuplicateReason.PROVIDER_JOB_ID
    assert result.duplicates[0].duplicate_of == original


def test_deduplicate_jobs_uses_normalized_url_when_provider_id_is_missing() -> None:
    original = build_job_posting(
        provider_job_id=None,
        url="https://example.com/vagas/123?utm_source=linkedin&id=55&vaga=bi",
    )
    duplicate = build_job_posting(
        provider_job_id=None,
        url="https://example.com/vagas/123?vaga=bi&id=55&utm_medium=email",
        title="Analise de dados junior",
        company="Empresa Sao Jose",
    )

    result = deduplicate_jobs([original, duplicate])

    assert len(result.unique_jobs) == 1
    assert result.duplicates[0].reason is DuplicateReason.NORMALIZED_URL
    assert make_normalized_job_url(original) == make_normalized_job_url(duplicate)


def test_deduplicate_jobs_uses_fingerprint_for_textually_equivalent_jobs() -> None:
    original = build_job_posting(
        provider_job_id=None,
        url="https://example.com/vagas/123?id=55",
    )
    duplicate = build_job_posting(
        provider_job_id=None,
        url="https://jobs.example.org/oportunidades/dados?ref=portal",
        title="Analise de Dados Junior",
        company="Empresa Sao Jose",
        location="Curitiba ",
    )

    result = deduplicate_jobs([original, duplicate])

    assert len(result.unique_jobs) == 1
    assert result.duplicates[0].reason is DuplicateReason.FINGERPRINT
    assert make_job_identity_fingerprint(original) == make_job_identity_fingerprint(duplicate)


def test_deduplicate_jobs_does_not_merge_different_companies() -> None:
    left = build_job_posting(
        provider_job_id=None,
        url="https://example.com/vagas/123?id=55",
        company="Empresa A",
    )
    right = build_job_posting(
        provider_job_id=None,
        url="https://example.com/vagas/456?id=99",
        company="Empresa B",
    )

    result = deduplicate_jobs([left, right])

    assert len(result.unique_jobs) == 2
    assert result.duplicates == []
