from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from radar_vagas.models import (
    CandidateProfile,
    EvaluatedJob,
    JobPosting,
    Priority,
    ResumeArtifact,
    WorkMode,
)


def build_job_posting(**overrides: object) -> JobPosting:
    payload = {
        "provider": "jooble",
        "provider_job_id": "123",
        "title": "Analista de Dados",
        "company": "Empresa X",
        "location": "Curitiba",
        "work_mode": WorkMode.HYBRID,
        "employment_type": "CLT",
        "description": "Atuacao com SQL, Power BI e Python.",
        "salary": None,
        "published_at": "2026-06-23T08:00:00-03:00",
        "updated_at": "2026-06-23T12:00:00",
        "url": "https://example.com/jobs/123",
        "source_name": "Jooble",
        "search_term": "Analista de Dados",
        "collected_at": "2026-06-23T11:30:00-03:00",
    }
    payload.update(overrides)
    return JobPosting.model_validate(payload)


def test_job_posting_normalizes_datetime_fields_to_utc() -> None:
    job = build_job_posting()

    assert job.published_at == datetime(2026, 6, 23, 11, 0, tzinfo=UTC)
    assert job.updated_at == datetime(2026, 6, 23, 12, 0, tzinfo=UTC)
    assert job.collected_at == datetime(2026, 6, 23, 14, 30, tzinfo=UTC)


def test_evaluated_job_enforces_score_range() -> None:
    job = build_job_posting()

    evaluated = EvaluatedJob.model_validate(
        {
            "job": job,
            "score": 85,
            "priority": Priority.HIGH,
            "matched_skills": ["SQL", "Power BI"],
            "missing_skills": ["Azure"],
            "extracted_keywords": ["sql", "power bi"],
            "relevant_domains": ["bi"],
            "rejection_reasons": [],
            "is_eligible": True,
            "fingerprint": "abc123",
        }
    )

    assert evaluated.score == 85
    assert evaluated.priority is Priority.HIGH


def test_resume_artifact_normalizes_generated_at_to_utc() -> None:
    artifact = ResumeArtifact.model_validate(
        {
            "job_fingerprint": "abc123",
            "target_title": "Analista de Dados Junior",
            "company": "Empresa X",
            "file_path": str(Path("output/resumes/curriculo.docx")),
            "file_name": "curriculo.docx",
            "file_sha256": "hash",
            "selected_skill_ids": ["sql"],
            "selected_experience_bullet_ids": ["smart_sql"],
            "selected_project_ids": ["cvm_pipeline"],
            "generated_at": "2026-06-23T15:00:00-03:00",
            "validation_errors": [],
            "is_valid": True,
        }
    )

    assert artifact.generated_at == datetime(2026, 6, 23, 18, 0, tzinfo=UTC)


def test_candidate_profile_accepts_valid_structure() -> None:
    profile = CandidateProfile.model_validate(
        {
            "candidate": {
                "name": "Rafael Exemplo da Silva",
                "city": "Curitiba",
                "state": "PR",
                "linkedin_url": "https://www.linkedin.com/in/rafael-exemplo/",
                "github_url": "https://github.com/rafael-exemplo",
            },
            "summary_blocks": [
                {
                    "id": "summary_data_bi",
                    "text": "Analista de dados com foco em BI.",
                    "tags": ["bi", "sql"],
                }
            ],
            "skills": [
                {"id": "python", "label": "Python", "aliases": ["python"], "tags": ["etl"]}
            ],
            "experiences": [
                {
                    "id": "smart_data_bi",
                    "company": "Smart Data BI",
                    "role": "Analista de Dados",
                    "bullets": [
                        {"id": "smart_dashboard", "text": "Criacao de dashboards.", "tags": ["bi"]}
                    ],
                }
            ],
            "projects": [
                {
                    "id": "cvm_pipeline",
                    "title": "Pipeline Financeiro",
                    "bullets": ["Pipeline em Python."],
                    "tags": ["python"],
                }
            ],
            "education": [
                {
                    "id": "fae_data_science",
                    "institution": "FAE Business School",
                    "course": "Ciencia de Dados para Negocios",
                    "status": "Em andamento",
                    "expected_completion": "2027",
                },
                {
                    "id": "esic_business",
                    "institution": "ESIC",
                    "course": "Administracao",
                    "status": "Curso interrompido",
                },
            ],
            "highlights": ["1o lugar no Data Science Day 2024"],
            "forbidden_claims": ["formado em Administracao"],
        }
    )

    assert profile.education[1].status == "Curso interrompido"
