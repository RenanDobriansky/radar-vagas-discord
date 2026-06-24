"""Modelos de dominio do projeto Radar de Vagas."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any
from unicodedata import normalize

from dateutil.parser import isoparse
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

NonEmptyStr = Annotated[str, Field(min_length=1)]


def utc_now() -> datetime:
    """Retorna o instante atual com timezone UTC."""
    return datetime.now(UTC)


def _normalize_lookup_text(value: str) -> str:
    normalized = normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().split())


def _normalize_datetime_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        parsed = isoparse(value)
    else:
        return value

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


class Priority(StrEnum):
    """Faixas de prioridade usadas no pipeline."""

    HIGH = "alta"
    GOOD = "boa_oportunidade"
    BELOW_THRESHOLD = "abaixo_do_minimo"


class JobStatus(StrEnum):
    """Status persistidos para o historico das vagas."""

    REJECTED = "rejected"
    ELIGIBLE = "eligible"
    RESUME_GENERATED = "resume_generated"
    RESUME_FAILED = "resume_failed"
    NOTIFIED = "notified"
    NOTIFICATION_FAILED = "notification_failed"


class WorkMode(StrEnum):
    """Modalidade de trabalho da vaga."""

    REMOTE = "remoto"
    HYBRID = "hibrido"
    ONSITE = "presencial"


class Seniority(StrEnum):
    """Senioridade inferida ou declarada para a vaga."""

    JUNIOR = "junior"
    ASSISTANT = "assistente"
    MIDLEVEL = "pleno"
    SENIOR = "senior"
    LEADERSHIP = "lideranca"
    UNSPECIFIED = "nao_informada"


class JobPosting(BaseModel):
    """Vaga normalizada independentemente da fonte."""

    provider: NonEmptyStr
    provider_job_id: str | None = None
    title: NonEmptyStr
    company: str | None = None
    location: str | None = None
    work_mode: WorkMode | None = None
    employment_type: str | None = None
    description: NonEmptyStr
    salary: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    url: AnyHttpUrl
    source_name: NonEmptyStr
    search_term: str | None = None
    collected_at: datetime = Field(default_factory=utc_now)

    @field_validator("published_at", "updated_at", "collected_at", mode="before")
    @classmethod
    def normalize_datetimes(cls, value: Any) -> Any:
        return _normalize_datetime_value(value)


class EvaluatedJob(BaseModel):
    """Resultado da analise deterministica aplicada a uma vaga."""

    job: JobPosting
    score: int = Field(ge=0, le=100)
    priority: Priority
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    extracted_keywords: list[str] = Field(default_factory=list)
    relevant_domains: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    is_eligible: bool
    fingerprint: NonEmptyStr


class ResumeArtifact(BaseModel):
    """Metadados do curriculo gerado para uma vaga elegivel."""

    job_fingerprint: NonEmptyStr
    target_title: NonEmptyStr
    company: NonEmptyStr
    file_path: Path
    file_name: NonEmptyStr
    file_sha256: NonEmptyStr
    selected_skill_ids: list[str] = Field(default_factory=list)
    selected_experience_bullet_ids: list[str] = Field(default_factory=list)
    selected_project_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
    validation_errors: list[str] = Field(default_factory=list)
    is_valid: bool

    @field_validator("generated_at", mode="before")
    @classmethod
    def normalize_generated_at(cls, value: Any) -> Any:
        return _normalize_datetime_value(value)


class CandidateHeader(BaseModel):
    """Dados de cabecalho do perfil-base aprovado."""

    name: NonEmptyStr
    city: NonEmptyStr
    state: NonEmptyStr
    linkedin_url: AnyHttpUrl
    github_url: AnyHttpUrl


class SummaryBlock(BaseModel):
    """Bloco aprovado para compor resumos profissionais."""

    id: NonEmptyStr
    text: NonEmptyStr
    tags: list[NonEmptyStr] = Field(default_factory=list)


class CandidateSkill(BaseModel):
    """Competencia aprovada com aliases e tags."""

    id: NonEmptyStr
    label: NonEmptyStr
    aliases: list[NonEmptyStr] = Field(default_factory=list)
    tags: list[NonEmptyStr] = Field(default_factory=list)


class ExperienceBullet(BaseModel):
    """Bullet verdadeiro vinculado a uma experiencia profissional."""

    id: NonEmptyStr
    text: NonEmptyStr
    tags: list[NonEmptyStr] = Field(default_factory=list)


class CandidateExperience(BaseModel):
    """Experiencia profissional aprovada do perfil-base."""

    id: NonEmptyStr
    company: NonEmptyStr
    role: NonEmptyStr
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[ExperienceBullet] = Field(default_factory=list)
    tags: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bullets(self) -> CandidateExperience:
        if not self.bullets:
            raise ValueError("experiences must include at least one bullet")
        return self


class CandidateProject(BaseModel):
    """Projeto aprovado para selecao em curriculos."""

    id: NonEmptyStr
    title: NonEmptyStr
    bullets: list[NonEmptyStr] = Field(default_factory=list)
    tags: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bullets(self) -> CandidateProject:
        if not self.bullets:
            raise ValueError("projects must include at least one bullet")
        return self


class CandidateEducation(BaseModel):
    """Formacao ou curso relevante do candidato."""

    id: NonEmptyStr
    institution: NonEmptyStr
    course: NonEmptyStr
    status: NonEmptyStr
    expected_completion: str | None = None


class CandidateProfile(BaseModel):
    """Perfil-base aprovado para geracao deterministica de curriculos."""

    candidate: CandidateHeader
    summary_blocks: list[SummaryBlock] = Field(default_factory=list)
    skills: list[CandidateSkill] = Field(default_factory=list)
    experiences: list[CandidateExperience] = Field(default_factory=list)
    projects: list[CandidateProject] = Field(default_factory=list)
    education: list[CandidateEducation] = Field(default_factory=list)
    highlights: list[NonEmptyStr] = Field(default_factory=list)
    forbidden_claims: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> CandidateProfile:
        duplicate_ids: set[str] = set()
        seen_ids: set[str] = set()

        def collect(identifier: str) -> None:
            if identifier in seen_ids:
                duplicate_ids.add(identifier)
            seen_ids.add(identifier)

        for block in self.summary_blocks:
            collect(block.id)
        for skill in self.skills:
            collect(skill.id)
        for experience in self.experiences:
            collect(experience.id)
            for bullet in experience.bullets:
                collect(bullet.id)
        for project in self.projects:
            collect(project.id)
        for education_item in self.education:
            collect(education_item.id)

        if duplicate_ids:
            duplicates = ", ".join(sorted(duplicate_ids))
            raise ValueError(f"candidate profile contains duplicate ids: {duplicates}")

        return self

    @model_validator(mode="after")
    def validate_esic_administration_status(self) -> CandidateProfile:
        for education_item in self.education:
            institution = _normalize_lookup_text(education_item.institution)
            course = _normalize_lookup_text(education_item.course)
            status = _normalize_lookup_text(education_item.status)

            if (
                "esic" in institution
                and "administracao" in course
                and status != "curso interrompido"
            ):
                raise ValueError(
                    "Administracao na ESIC deve estar marcada como 'Curso interrompido'"
                )

        return self
