from __future__ import annotations

from datetime import UTC, datetime

import pytest

from radar_vagas.config import load_profile_config
from radar_vagas.models import JobPosting, Priority, WorkMode
from radar_vagas.scoring import evaluate_job


def build_job_posting(**overrides: object) -> JobPosting:
    payload = {
        "provider": "jooble",
        "provider_job_id": "123",
        "title": "Analista de Dados Junior",
        "company": "Empresa X",
        "location": "Curitiba - PR",
        "work_mode": WorkMode.HYBRID,
        "employment_type": "CLT",
        "description": "SQL, Power BI, Python, DAX, Power Query, ETL e dashboards.",
        "salary": None,
        "published_at": "2026-06-23T08:00:00Z",
        "updated_at": "2026-06-23T10:00:00Z",
        "url": "https://example.com/jobs/123",
        "source_name": "Jooble",
        "search_term": "Analista de Dados",
        "collected_at": "2026-06-23T11:30:00Z",
    }
    payload.update(overrides)
    return JobPosting.model_validate(payload)


@pytest.mark.parametrize(
    ("scenario", "job", "expected"),
    [
        (
            "vaga junior altamente aderente",
            build_job_posting(),
            {"eligible": True, "priority": Priority.HIGH, "min_score": 85, "reason": None},
        ),
        (
            "vaga pleno parcialmente aderente",
            build_job_posting(
                title="Analista de Performance Pleno",
                description="Excel, SQL e dashboards para area comercial.",
            ),
            {
                "eligible": False,
                "priority": Priority.BELOW_THRESHOLD,
                "max_score": 69,
                "reason": None,
            },
        ),
        (
            "vaga senior",
            build_job_posting(title="Analista de Dados Senior"),
            {
                "eligible": False,
                "priority": Priority.BELOW_THRESHOLD,
                "reason": "senioridade incompativel",
            },
        ),
        (
            "vaga presencial fora da regiao",
            build_job_posting(location="Belo Horizonte - MG", work_mode=WorkMode.ONSITE),
            {
                "eligible": False,
                "priority": Priority.BELOW_THRESHOLD,
                "reason": "localizacao fora da regiao aceita",
            },
        ),
        (
            "vaga remota brasil",
            build_job_posting(
                title="BI Analyst Junior",
                location="Remoto Brasil",
                work_mode=WorkMode.REMOTE,
            ),
            {"eligible": True, "priority": Priority.HIGH, "min_score": 85, "reason": None},
        ),
        (
            "vaga sem descricao",
            build_job_posting(description=""),
            {
                "eligible": False,
                "priority": Priority.BELOW_THRESHOLD,
                "max_score": 69,
                "reason": None,
            },
        ),
        (
            "vaga antiga",
            build_job_posting(
                updated_at="2026-06-01T10:00:00Z",
                published_at="2026-06-01T08:00:00Z",
            ),
            {
                "eligible": False,
                "priority": Priority.BELOW_THRESHOLD,
                "reason": "vaga antiga acima do limite configurado",
            },
        ),
        (
            "vaga com score abaixo de 70",
            build_job_posting(
                title="Analista Comercial",
                description="Excel e reporting operacional.",
            ),
            {
                "eligible": False,
                "priority": Priority.BELOW_THRESHOLD,
                "max_score": 69,
                "reason": None,
            },
        ),
    ],
)
def test_evaluate_job_scenarios(
    scenario: str,
    job: JobPosting,
    expected: dict[str, object],
) -> None:
    config = load_profile_config()
    result = evaluate_job(job, config, reference_time=datetime(2026, 6, 23, 12, 0, tzinfo=UTC))

    assert result.is_eligible is expected["eligible"], scenario
    assert result.priority is expected["priority"], scenario
    assert result.score <= 100, scenario
    assert "cargo=" in result.score_explanation, scenario

    min_score = expected.get("min_score")
    if isinstance(min_score, int):
        assert result.score >= min_score, scenario

    max_score = expected.get("max_score")
    if isinstance(max_score, int):
        assert result.score <= max_score, scenario

    reason = expected.get("reason")
    if isinstance(reason, str):
        assert reason in result.rejection_reasons, scenario


def test_evaluate_job_extracts_matched_and_missing_skills() -> None:
    config = load_profile_config()
    job = build_job_posting(description="SQL, Power BI, Python e Azure.")

    result = evaluate_job(job, config, reference_time=datetime(2026, 6, 23, 12, 0, tzinfo=UTC))

    assert result.matched_skills[:4] == ["Power BI", "SQL", "Python", "Cloud"]
    assert "DAX" in result.missing_skills


def test_evaluate_job_uses_published_at_when_updated_at_is_missing() -> None:
    config = load_profile_config()
    job = build_job_posting(updated_at=None, published_at="2026-06-22T16:00:00Z")

    result = evaluate_job(job, config, reference_time=datetime(2026, 6, 23, 12, 0, tzinfo=UTC))

    assert "atualidade=10/10" in result.score_explanation
