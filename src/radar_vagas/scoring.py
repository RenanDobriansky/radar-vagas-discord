"""Regras de scoring deterministico para vagas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil

from radar_vagas.config import ProfileConfig
from radar_vagas.models import EvaluatedJob, JobPosting, Priority, Seniority, WorkMode
from radar_vagas.text_utils import make_job_fingerprint, normalize_text

SENIORITY_JUNIOR_TERMS = {"junior", "jr", "jun", "trainee"}
SENIORITY_ASSISTANT_TERMS = {"assistente", "assistant"}
SENIORITY_MIDLEVEL_TERMS = {"pleno", "mid level", "mid-level"}
SENIORITY_SENIOR_TERMS = {"senior", "sr", "especialista", "specialist"}
LEADERSHIP_TERMS = {
    "coordenador",
    "coordinator",
    "diretor",
    "director",
    "gerente",
    "manager",
    "gestor",
    "head",
    "lead",
    "lider",
    "lideranca",
    "principal",
    "staff",
    "tech lead",
}
SENIORITY_CONTEXT_TERMS = {
    "cargo",
    "nivel",
    "perfil",
    "posicao",
    "position",
    "role",
    "senioridade",
    "vaga",
}
REMOTE_COMPATIBLE_MARKERS = {
    "americas",
    "anywhere",
    "brazil",
    "brasil",
    "global",
    "latam",
    "latin america",
    "remote brazil",
    "remoto brasil",
    "worldwide",
}
REMOTE_RESTRICTED_MARKERS = {
    "australia only",
    "canada only",
    "eu only",
    "european union only",
    "europe only",
    "portugal only",
    "uk only",
    "united kingdom only",
    "united states only",
    "us only",
    "usa only",
}
OPTIONAL_SKILL_MARKERS = {
    "bonus",
    "desejavel",
    "diferencial",
    "nice to have",
    "plus",
    "preferencial",
    "seria um diferencial",
}
DESCRIPTION_SPLIT_PATTERN = re.compile(r"[.\n;\u2022]+")
EXTERNAL_SKILL_ALIASES = {
    "Airflow": ("airflow",),
    "BigQuery": ("bigquery", "big query"),
    "Databricks": ("databricks",),
    "dbt": ("dbt",),
    "Kafka": ("kafka",),
    "Looker": ("looker",),
    "Snowflake": ("snowflake",),
    "Tableau": ("tableau",),
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


@dataclass(slots=True)
class SkillAssessment:
    required_skills: list[str]
    matched_candidate_skills: list[str]
    candidate_skill_gaps: list[str]
    optional_job_skills: list[str]
    technical_score: int


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
    title = normalize_text(job.title)
    title_detection = _detect_seniority_from_title(title, config)
    if title_detection is not None:
        return title_detection

    if job.seniority is not None:
        return job.seniority

    description = normalize_text(job.description)
    description_detection = _detect_seniority_from_explicit_description(description)
    if description_detection is not None:
        return description_detection

    return Seniority.UNSPECIFIED


def _score_title(job: JobPosting, config: ProfileConfig) -> tuple[int, list[str]]:
    normalized_title = normalize_text(job.title)
    normalized_terms = [normalize_text(term) for term in config.search.terms]
    title_weight = config.scoring.weights.title
    title_ratios = config.scoring.ratios.title

    if normalized_title in normalized_terms:
        return title_weight, []

    title_tokens = set(normalized_title.split())
    for term in normalized_terms:
        term_tokens = set(term.split())
        overlap = len(title_tokens & term_tokens)
        if overlap >= 2 or term in normalized_title or normalized_title in term:
            return _scaled_weight(title_weight, title_ratios.close), []

    if any(
        keyword in normalized_title
        for keyword in map(normalize_text, config.scoring.related_title_keywords)
    ):
        return _scaled_weight(title_weight, title_ratios.related), []

    normalized_partial_keywords = map(normalize_text, config.scoring.partial_title_keywords)
    if any(keyword in normalized_title for keyword in normalized_partial_keywords):
        return _scaled_weight(title_weight, title_ratios.partial), []

    return 0, ["titulo fora da area-alvo"]


def _analyze_skills(job: JobPosting, config: ProfileConfig) -> SkillAssessment:
    candidate_catalog = {
        skill_name: {
            "weight": weight,
            "aliases": [
                normalize_text(alias)
                for alias in config.scoring.skill_aliases[skill_name]
            ],
        }
        for skill_name, weight in config.scoring.skill_weights.items()
    }
    required_candidate: set[str] = set()
    optional_candidate: set[str] = set()
    required_external: set[str] = set()
    optional_external: set[str] = set()

    for segment, is_optional in _iter_skill_segments(job):
        for skill_name, metadata in candidate_catalog.items():
            if _segment_contains_alias(segment, metadata["aliases"]):
                if is_optional and skill_name not in required_candidate:
                    optional_candidate.add(skill_name)
                else:
                    required_candidate.add(skill_name)
                    optional_candidate.discard(skill_name)

        for skill_name, aliases in EXTERNAL_SKILL_ALIASES.items():
            normalized_aliases = [normalize_text(alias) for alias in aliases]
            if _segment_contains_alias(segment, normalized_aliases):
                if is_optional and skill_name not in required_external:
                    optional_external.add(skill_name)
                else:
                    required_external.add(skill_name)
                    optional_external.discard(skill_name)

    candidate_skill_order = {
        skill_name: weight for skill_name, weight in config.scoring.skill_weights.items()
    }
    external_gap_weight = _estimate_external_gap_weight(config)
    required_skills = _sort_skill_labels(
        [*required_candidate, *required_external],
        candidate_skill_order,
        external_gap_weight,
    )
    matched_candidate_skills = _sort_skill_labels(
        list(required_candidate),
        candidate_skill_order,
        external_gap_weight,
    )
    candidate_skill_gaps = sorted(required_external)
    optional_job_skills = _sort_skill_labels(
        [*optional_candidate, *optional_external],
        candidate_skill_order,
        external_gap_weight,
    )

    required_candidate_weight = sum(candidate_skill_order[skill] for skill in required_candidate)
    optional_candidate_full_weight = sum(
        candidate_skill_order[skill] for skill in optional_candidate
    )
    optional_candidate_credit = (
        optional_candidate_full_weight * config.scoring.ratios.skills.optional_detected
    )
    required_gap_weight = external_gap_weight * len(required_external)
    technical_total_weight = (
        required_candidate_weight + optional_candidate_full_weight + required_gap_weight
    )
    technical_matched_weight = required_candidate_weight + optional_candidate_credit

    if technical_total_weight == 0:
        technical_score = 0
    else:
        normalized_score = technical_matched_weight / technical_total_weight
        technical_score = min(
            config.scoring.weights.technical,
            ceil(normalized_score * config.scoring.weights.technical),
        )

    if not job.description.strip():
        technical_score = ceil(technical_score * 0.6)

    return SkillAssessment(
        required_skills=required_skills,
        matched_candidate_skills=matched_candidate_skills,
        candidate_skill_gaps=candidate_skill_gaps,
        optional_job_skills=optional_job_skills,
        technical_score=min(config.scoring.weights.technical, technical_score),
    )


def _score_seniority(job: JobPosting, config: ProfileConfig) -> tuple[int, Seniority, list[str]]:
    detected = _detect_seniority(job, config)
    seniority_weight = config.scoring.weights.seniority
    ratios = config.scoring.ratios.seniority

    if detected in {Seniority.SENIOR, Seniority.LEADERSHIP}:
        return 0, detected, ["senioridade incompativel"]
    if detected is Seniority.JUNIOR:
        return seniority_weight, detected, []
    if detected is Seniority.MIDLEVEL:
        return _scaled_weight(seniority_weight, ratios.midlevel), detected, []
    if detected is Seniority.ASSISTANT:
        return _scaled_weight(seniority_weight, ratios.assistant), detected, []

    return _scaled_weight(seniority_weight, ratios.unspecified), detected, []


def _score_location(job: JobPosting, config: ProfileConfig) -> tuple[int, list[str]]:
    work_mode = _infer_work_mode(job)
    normalized_location = normalize_text(job.location)
    remote_scope_text = normalize_text(f"{job.location or ''} {job.description}")
    accepted_locations = {
        normalize_text(location)
        for location in config.search.locations
        if normalize_text(location) != "remoto brasil"
    }
    candidate_city = normalize_text(config.candidate.city)
    location_weight = config.scoring.weights.location
    location_ratios = config.scoring.ratios.location

    if work_mode is WorkMode.REMOTE:
        if not normalized_location:
            return _scaled_weight(location_weight, location_ratios.remote_unspecified), []
        if any(marker in remote_scope_text for marker in REMOTE_RESTRICTED_MARKERS):
            return 0, ["remoto sem disponibilidade para o brasil"]
        if any(marker in remote_scope_text for marker in REMOTE_COMPATIBLE_MARKERS):
            return _scaled_weight(location_weight, location_ratios.remote_compatible), []
        return _scaled_weight(location_weight, location_ratios.remote_unspecified), []

    if candidate_city and candidate_city in normalized_location:
        return _scaled_weight(location_weight, location_ratios.exact), []

    if any(location in normalized_location for location in accepted_locations):
        return _scaled_weight(location_weight, location_ratios.metro), []

    if work_mode is WorkMode.HYBRID and not normalized_location:
        return _scaled_weight(location_weight, location_ratios.hybrid_unspecified), []

    if work_mode in {WorkMode.HYBRID, WorkMode.ONSITE}:
        return 0, ["localizacao fora da regiao aceita"]

    if not normalized_location:
        return _scaled_weight(location_weight, location_ratios.hybrid_unspecified), []

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
    freshness_weight = config.scoring.weights.freshness
    freshness_ratios = config.scoring.ratios.freshness

    if age_days > config.search.maximum_age_days:
        return 0, ["vaga antiga acima do limite configurado"]
    if age_days <= 1:
        return freshness_weight, []
    if age_days <= 3:
        return _scaled_weight(freshness_weight, freshness_ratios.recent), []
    if age_days <= 7:
        return _scaled_weight(freshness_weight, freshness_ratios.week), []
    return _scaled_weight(freshness_weight, freshness_ratios.stale), []


def _determine_priority(score: int, minimum_score: int) -> Priority:
    if score >= 85:
        return Priority.HIGH
    if score >= minimum_score:
        return Priority.GOOD
    return Priority.BELOW_THRESHOLD


def _build_explanation(
    breakdown: ScoreBreakdown,
    config: ProfileConfig,
    required_skills: list[str],
    matched_candidate_skills: list[str],
    candidate_skill_gaps: list[str],
    rejection_reasons: list[str],
) -> str:
    explanation = (
        f"cargo={breakdown.title}/{config.scoring.weights.title}; "
        f"competencias={breakdown.technical}/{config.scoring.weights.technical}; "
        f"senioridade={breakdown.seniority}/{config.scoring.weights.seniority}; "
        f"localizacao={breakdown.location}/{config.scoring.weights.location}; "
        f"atualidade={breakdown.freshness}/{config.scoring.weights.freshness}"
    )
    if required_skills:
        explanation += f"; requisitos={', '.join(required_skills[:4])}"
    if matched_candidate_skills:
        explanation += f"; aderentes={', '.join(matched_candidate_skills[:4])}"
    if candidate_skill_gaps:
        explanation += f"; lacunas={', '.join(candidate_skill_gaps[:4])}"
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

    skill_assessment = _analyze_skills(job, config)
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
        technical=skill_assessment.technical_score,
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
    explanation = _build_explanation(
        breakdown,
        config,
        skill_assessment.required_skills,
        skill_assessment.matched_candidate_skills,
        skill_assessment.candidate_skill_gaps,
        rejection_reasons,
    )

    return EvaluatedJob(
        job=job,
        score=score,
        priority=priority,
        required_skills=skill_assessment.required_skills,
        matched_candidate_skills=skill_assessment.matched_candidate_skills,
        candidate_skill_gaps=skill_assessment.candidate_skill_gaps,
        optional_job_skills=skill_assessment.optional_job_skills,
        extracted_keywords=(
            skill_assessment.required_skills + skill_assessment.optional_job_skills
        ),
        relevant_domains=[],
        rejection_reasons=rejection_reasons,
        is_eligible=is_eligible,
        fingerprint=fingerprint,
        score_explanation=explanation,
    )


def _detect_seniority_from_title(title: str, config: ProfileConfig) -> Seniority | None:
    normalized_excluded = [normalize_text(item) for item in config.filters.excluded_seniority]
    if any(term and term in title for term in normalized_excluded):
        if any(term in title for term in LEADERSHIP_TERMS):
            return Seniority.LEADERSHIP
        return Seniority.SENIOR
    if any(term in title for term in LEADERSHIP_TERMS):
        return Seniority.LEADERSHIP
    if any(term in title for term in SENIORITY_SENIOR_TERMS):
        return Seniority.SENIOR
    if any(term in title for term in SENIORITY_JUNIOR_TERMS):
        return Seniority.JUNIOR
    if any(term in title for term in SENIORITY_ASSISTANT_TERMS):
        return Seniority.ASSISTANT
    if any(term in title for term in SENIORITY_MIDLEVEL_TERMS):
        return Seniority.MIDLEVEL
    return None


def _detect_seniority_from_explicit_description(description: str) -> Seniority | None:
    if not description:
        return None
    if _has_contextual_seniority(description, LEADERSHIP_TERMS):
        return Seniority.LEADERSHIP
    if _has_contextual_seniority(description, SENIORITY_SENIOR_TERMS):
        return Seniority.SENIOR
    if _has_contextual_seniority(description, SENIORITY_JUNIOR_TERMS):
        return Seniority.JUNIOR
    if _has_contextual_seniority(description, SENIORITY_ASSISTANT_TERMS):
        return Seniority.ASSISTANT
    if _has_contextual_seniority(description, SENIORITY_MIDLEVEL_TERMS):
        return Seniority.MIDLEVEL
    return None


def _has_contextual_seniority(text: str, terms: set[str]) -> bool:
    for context in SENIORITY_CONTEXT_TERMS:
        for term in terms:
            if context in text and term in text:
                context_index = text.index(context)
                term_index = text.index(term)
                if abs(context_index - term_index) <= 40:
                    return True
    return False


def _iter_skill_segments(job: JobPosting) -> list[tuple[str, bool]]:
    segments: list[tuple[str, bool]] = [(normalize_text(job.title), False)]
    for chunk in DESCRIPTION_SPLIT_PATTERN.split(job.description.replace("\r", "\n")):
        normalized_chunk = normalize_text(chunk)
        if not normalized_chunk:
            continue
        is_optional = any(marker in normalized_chunk for marker in OPTIONAL_SKILL_MARKERS)
        segments.append((normalized_chunk, is_optional))
    return segments


def _segment_contains_alias(segment: str, aliases: list[str]) -> bool:
    return any(alias and alias in segment for alias in aliases)


def _sort_skill_labels(
    skills: list[str],
    candidate_skill_order: dict[str, int],
    external_gap_weight: int,
) -> list[str]:
    unique_skills = list(dict.fromkeys(skills))
    return sorted(
        unique_skills,
        key=lambda skill: (
            -(candidate_skill_order.get(skill, external_gap_weight)),
            skill,
        ),
    )


def _estimate_external_gap_weight(config: ProfileConfig) -> int:
    weights = list(config.scoring.skill_weights.values())
    if not weights:
        return 3
    return max(3, round(sum(weights) / len(weights)))


def _scaled_weight(weight: int, ratio: float) -> int:
    return max(0, min(weight, round(weight * ratio)))
