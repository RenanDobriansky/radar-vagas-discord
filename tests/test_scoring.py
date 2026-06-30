from __future__ import annotations

from datetime import UTC, datetime

from radar_vagas.config import load_profile_config
from radar_vagas.models import JobPosting, Priority, Seniority, WorkMode
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


def evaluate(job: JobPosting):
    config = load_profile_config()
    return evaluate_job(job, config, reference_time=datetime(2026, 6, 23, 12, 0, tzinfo=UTC))


def test_evaluate_job_accepts_highly_adherent_junior_role() -> None:
    result = evaluate(build_job_posting())

    assert result.is_eligible is True
    assert result.priority is Priority.HIGH
    assert result.score >= 85
    assert result.score <= 100
    assert "cargo=22/25" in result.score_explanation


def test_evaluate_job_can_keep_partially_adherent_midlevel_role_below_threshold() -> None:
    result = evaluate(
        build_job_posting(
            title="Analista de Performance Pleno",
            description="Atendimento comercial, CRM e follow-up de vendas.",
        )
    )

    assert result.is_eligible is False
    assert result.priority is Priority.BELOW_THRESHOLD
    assert result.score < 70
    assert "senioridade incompativel" not in result.rejection_reasons


def test_evaluate_job_rejects_senior_title() -> None:
    result = evaluate(build_job_posting(title="Senior Data Analyst"))

    assert result.is_eligible is False
    assert "senioridade incompativel" in result.rejection_reasons


def test_evaluate_job_rejects_leadership_titles() -> None:
    for title in ["Coordenador de Dados", "Data Lead"]:
        result = evaluate(build_job_posting(title=title))
        assert result.is_eligible is False
        assert "senioridade incompativel" in result.rejection_reasons


def test_evaluate_job_uses_structured_seniority_when_available() -> None:
    result = evaluate(
        build_job_posting(
            title="Analista de Dados",
            seniority=Seniority.MIDLEVEL,
        )
    )

    assert "senioridade=8/15" in result.score_explanation
    assert "senioridade incompativel" not in result.rejection_reasons


def test_evaluate_job_does_not_reject_junior_role_that_reports_to_manager() -> None:
    result = evaluate(
        build_job_posting(
            title="Junior Data Analyst",
            description=(
                "SQL, Power BI e Python. A pessoa reportara ao gerente da area e apoiara "
                "coordenadores na consolidacao de indicadores."
            ),
        )
    )

    assert result.is_eligible is True
    assert "senioridade incompativel" not in result.rejection_reasons


def test_evaluate_job_does_not_reject_role_that_mentions_management_context_only() -> None:
    result = evaluate(
        build_job_posting(
            title="Analista de Dados",
            description=(
                "SQL, Power BI e Python para apoiar a gestao com indicadores e dashboards."
            ),
        )
    )

    assert "senioridade incompativel" not in result.rejection_reasons
    assert result.score <= 100


def test_evaluate_job_rejects_onsite_role_outside_region() -> None:
    result = evaluate(
        build_job_posting(location="Belo Horizonte - MG", work_mode=WorkMode.ONSITE)
    )

    assert result.is_eligible is False
    assert "localizacao fora da regiao aceita" in result.rejection_reasons


def test_evaluate_job_accepts_remote_brazil_with_max_location_score() -> None:
    result = evaluate(
        build_job_posting(
            title="BI Analyst Junior",
            location="Remoto Brasil",
            work_mode=WorkMode.REMOTE,
        )
    )

    assert result.is_eligible is True
    assert "localizacao=15/15" in result.score_explanation


def test_evaluate_job_accepts_remote_worldwide_with_max_location_score() -> None:
    result = evaluate(
        build_job_posting(
            title="BI Analyst Junior",
            location="Worldwide",
            work_mode=WorkMode.REMOTE,
        )
    )

    assert result.is_eligible is True
    assert "localizacao=15/15" in result.score_explanation


def test_evaluate_job_assigns_intermediate_score_to_remote_without_location() -> None:
    result = evaluate(
        build_job_posting(
            title="BI Analyst Junior",
            location=None,
            work_mode=WorkMode.REMOTE,
        )
    )

    assert "localizacao=6/15" in result.score_explanation
    assert "remoto sem disponibilidade para o brasil" not in result.rejection_reasons


def test_evaluate_job_rejects_remote_restricted_to_other_country() -> None:
    result = evaluate(
        build_job_posting(
            title="BI Analyst Junior",
            location="US only",
            work_mode=WorkMode.REMOTE,
        )
    )

    assert result.is_eligible is False
    assert "remoto sem disponibilidade para o brasil" in result.rejection_reasons


def test_evaluate_job_handles_missing_description() -> None:
    result = evaluate(build_job_posting(description=""))

    assert result.is_eligible is False
    assert result.priority is Priority.BELOW_THRESHOLD
    assert result.score < 70


def test_evaluate_job_rejects_old_job() -> None:
    result = evaluate(
        build_job_posting(
            updated_at="2026-06-01T10:00:00Z",
            published_at="2026-06-01T08:00:00Z",
        )
    )

    assert result.is_eligible is False
    assert "vaga antiga acima do limite configurado" in result.rejection_reasons


def test_evaluate_job_extracts_required_skills_real_gaps_and_optional_skills() -> None:
    result = evaluate(
        build_job_posting(
            description="SQL, Power BI, Python e Looker. Diferencial: Tableau.",
        )
    )

    assert result.required_skills[:4] == ["Power BI", "SQL", "Python", "Looker"]
    assert result.matched_candidate_skills == ["Power BI", "SQL", "Python"]
    assert result.candidate_skill_gaps == ["Looker"]
    assert result.optional_job_skills == ["Tableau"]
    assert "requisitos=Power BI, SQL, Python, Looker" in result.score_explanation
    assert "lacunas=Looker" in result.score_explanation


def test_evaluate_job_uses_published_at_when_updated_at_is_missing() -> None:
    result = evaluate(
        build_job_posting(updated_at=None, published_at="2026-06-22T16:00:00Z")
    )

    assert "atualidade=10/10" in result.score_explanation
