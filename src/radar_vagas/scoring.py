"""Regras de scoring deterministico para vagas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil

from radar_vagas.config import ProfileConfig
from radar_vagas.models import EvaluatedJob, JobPosting, Priority, Seniority, WorkMode
from radar_vagas.text_utils import make_job_fingerprint, normalize_text

LEADERSHIP_KEYWORDS = {
    "coordenador",
    "diretor",
    "gerente",
    "gestao",
    "gestor",
    "head",
    "lead",
    "lider",
    "lideranca",
    "principal",
    "staff",
    "tech lead",
}
REMOTE_BRAZIL_MARKERS = {"brasil", "brazil", "remoto brasil", "remote brazil"}
REMOTE_FOREIGN_MARKERS = {
    "eua",
    "europe",
    "european union",
    "portugal",
    "usa",
    "united states",
    "united kingdom",
}


@dataclass(slots=True)
class ScoreBreakdown:
    """Pontuacao detalhada e auditavel da vaga."""

    title: int
    technical: int
    seniority: int
    location: int
    freshness: int

    @property
    def total(self) -> int:
        return max(
            0,
            min(100, self.title + self.technical + self.seniority + self.location + self.freshness),
        )


def _combined_job_text(job: JobPosting) -> str:
    location = job.location or ""
    return normalize_text(f"{job.title} {job.description} {location}")


def _infer_work_mode(job: JobPosting) -> WorkMode | None:
    if job.work_mode is not None:
        return job.work_mode

    text = _combined_job_text(job)
    if "remoto" in text or "remote" in text:
        return WorkMode.REMOTE
    if "hibrido" in text or "hybrid" in text:
        return WorkMode.HYBRID
    if "presencial" in text or "onsite" in text:
        return WorkMode.ONSITE
    return None


def _detect_seniority(job: JobPosting, config: ProfileConfig) -> Seniority:
    text = _combined_job_text(job)

    normalized_excluded_seniority = (
        normalize_text(item) for item in config.filters.excluded_seniority
    )
    if any(term in text for term in normalized_excluded_seniority):
        return Seniority.SENIOR
    if any(keyword in text for keyword in LEADERSHIP_KEYWORDS):
        return Seniority.LEADERSHIP
    if "junior" in text or "jr" in text:
        return Seniority.JUNIOR
    if "assistente" in text:
        return Seniority.ASSISTANT
    if "pleno" in text:
        return Seniority.MIDLEVEL
    return Seniority.UNSPECIFIED


def _score_title(job: JobPosting, config: ProfileConfig) -> tuple[int, list[str]]:
    normalized_title = normalize_text(job.title)
    normalized_terms = [normalize_text(term) for term in config.search.terms]

    if normalized_title in normalized_terms:
        return config.scoring.weights.title, []

    title_tokens = set(normalized_title.split())
    for term in normalized_terms:
        term_tokens = set(term.split())
        overlap = len(title_tokens & term_tokens)
        if overlap >= 2 or term in normalized_title or normalized_title in term:
            return 22, []

    if any(
        keyword in normalized_title
        for keyword in map(normalize_text, config.scoring.related_title_keywords)
    ):
        return 15, []

    combined_text = _combined_job_text(job)
    normalized_partial_keywords = map(normalize_text, config.scoring.partial_title_keywords)
    if any(keyword in combined_text for keyword in normalized_partial_keywords):
        return 8, []

    return 0, ["titulo fora da area-alvo"]


def _detect_skills(job: JobPosting, config: ProfileConfig) -> tuple[list[str], list[str], int]:
    text = _combined_job_text(job)
    matched: list[str] = []
    missing: list[str] = []
    matched_weight = 0
    total_weight = sum(config.scoring.skill_weights.values())

    sorted_skills = sorted(
        config.scoring.skill_weights.items(),
        key=lambda item: (-item[1], item[0]),
    )
    for skill_name, weight in sorted_skills:
        aliases = [normalize_text(alias) for alias in config.scoring.skill_aliases[skill_name]]
        if any(alias and alias in text for alias in aliases):
            matched.append(skill_name)
            matched_weight += weight
        else:
            missing.append(skill_name)

    if total_weight == 0:
        return matched, missing, 0

    normalized_score = matched_weight / total_weight
    score = normalized_score * config.scoring.weights.technical

    if not job.description.strip():
        score *= 0.6

    return matched, missing, min(config.scoring.weights.technical, ceil(score))


def _score_seniority(job: JobPosting, config: ProfileConfig) -> tuple[int, Seniority, list[str]]:
    detected = _detect_seniority(job, config)

    if detected in {Seniority.SENIOR, Seniority.LEADERSHIP}:
        return 0, detected, ["senioridade incompativel"]
    if detected is Seniority.JUNIOR:
        return config.scoring.weights.seniority, detected, []
    if detected is Seniority.MIDLEVEL:
        return 8, detected, []
    if detected is Seniority.ASSISTANT:
        return 7, detected, []

    return 12, detected, []


def _score_location(job: JobPosting, config: ProfileConfig) -> tuple[int, list[str]]:
    work_mode = _infer_work_mode(job)
    normalized_location = normalize_text(job.location)
    accepted_locations = {
        normalize_text(location)
        for location in config.search.locations
        if normalize_text(location) != "remoto brasil"
    }
    candidate_city = normalize_text(config.candidate.city)

    if work_mode is WorkMode.REMOTE:
        if not normalized_location:
            return config.scoring.weights.location, []
        if any(marker in normalized_location for marker in REMOTE_BRAZIL_MARKERS):
            return config.scoring.weights.location, []
        if any(marker in normalized_location for marker in REMOTE_FOREIGN_MARKERS):
            return 0, ["remoto sem disponibilidade para o brasil"]
        return 6, []

    if candidate_city and candidate_city in normalized_location:
        return config.scoring.weights.location, []

    if any(location in normalized_location for location in accepted_locations):
        return 13, []

    if work_mode is WorkMode.HYBRID and not normalized_location:
        return 6, []

    if work_mode in {WorkMode.HYBRID, WorkMode.ONSITE}:
        return 0, ["localizacao fora da regiao aceita"]

    if not normalized_location:
        return 6, []

    return 0, ["localizacao fora da regiao aceita"]


def _score_freshness(
    job: JobPosting,
    config: ProfileConfig,
    reference_time: datetime,
) -> tuple[int, list[str]]:
    job_timestamp = job.updated_at or job.published_at
    if job_timestamp is None:
        return 0, []

    age = reference_time - job_timestamp
    age_days = age.total_seconds() / 86400

    if age_days > config.search.maximum_age_days:
        return 0, ["vaga antiga acima do limite configurado"]
    if age_days <= 1:
        return config.scoring.weights.freshness, []
    if age_days <= 3:
        return 8, []
    if age_days <= 7:
        return 5, []
    return 2, []


def _determine_priority(score: int, minimum_score: int) -> Priority:
    if score >= 85:
        return Priority.HIGH
    if score >= minimum_score:
        return Priority.GOOD
    return Priority.BELOW_THRESHOLD


def _build_explanation(
    breakdown: ScoreBreakdown,
    config: ProfileConfig,
    matched_skills: list[str],
    rejection_reasons: list[str],
) -> str:
    explanation = (
        f"cargo={breakdown.title}/{config.scoring.weights.title}; "
        f"competencias={breakdown.technical}/{config.scoring.weights.technical}; "
        f"senioridade={breakdown.seniority}/{config.scoring.weights.seniority}; "
        f"localizacao={breakdown.location}/{config.scoring.weights.location}; "
        f"atualidade={breakdown.freshness}/{config.scoring.weights.freshness}"
    )
    if matched_skills:
        explanation += f"; aderentes={', '.join(matched_skills[:4])}"
    if rejection_reasons:
        explanation += f"; rejeicoes={', '.join(rejection_reasons)}"
    return explanation


def evaluate_job(
    job: JobPosting,
    config: ProfileConfig,
    *,
    reference_time: datetime | None = None,
) -> EvaluatedJob:
    """Avalia uma vaga com score deterministico, filtros e explicacao auditavel."""
    now = reference_time.astimezone(UTC) if reference_time else datetime.now(UTC)
    rejection_reasons: list[str] = []

    combined_text = _combined_job_text(job)
    excluded_terms = [normalize_text(term) for term in config.filters.excluded_terms]
    if any(term in combined_text for term in excluded_terms):
        rejection_reasons.append("termo excluido encontrado")

    title_score, title_rejections = _score_title(job, config)
    rejection_reasons.extend(title_rejections)

    matched_skills, missing_skills, technical_score = _detect_skills(job, config)
    seniority_score, _detected_seniority, seniority_rejections = _score_seniority(job, config)
    rejection_reasons.extend(seniority_rejections)

    location_score, location_rejections = _score_location(job, config)
    rejection_reasons.extend(location_rejections)

    freshness_score, freshness_rejections = _score_freshness(job, config, now)
    rejection_reasons.extend(freshness_rejections)

    # Repeticoes geradas por regras convergentes nao agregam valor para auditoria.
    rejection_reasons = list(dict.fromkeys(rejection_reasons))

    breakdown = ScoreBreakdown(
        title=title_score,
        technical=technical_score,
        seniority=seniority_score,
        location=location_score,
        freshness=freshness_score,
    )
    score = breakdown.total
    is_eligible = not rejection_reasons and score >= config.search.minimum_score
    priority = (
        _determine_priority(score, config.search.minimum_score)
        if is_eligible
        else Priority.BELOW_THRESHOLD
    )
    fingerprint = make_job_fingerprint(job.title, job.company, job.location)
    explanation = _build_explanation(breakdown, config, matched_skills, rejection_reasons)

    return EvaluatedJob(
        job=job,
        score=score,
        priority=priority,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        extracted_keywords=matched_skills.copy(),
        relevant_domains=[],
        rejection_reasons=rejection_reasons,
        is_eligible=is_eligible,
        fingerprint=fingerprint,
        score_explanation=explanation,
    )
