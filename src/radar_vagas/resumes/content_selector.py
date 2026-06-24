"""Selecao de conteudo verdadeiro para curriculos otimizados."""

from __future__ import annotations

from dataclasses import dataclass, field

from radar_vagas.config import ProfileConfig
from radar_vagas.models import (
    CandidateAdditionalExperience,
    CandidateEducation,
    CandidateExperience,
    CandidateProject,
    JobPosting,
)
from radar_vagas.resumes.keyword_extractor import KeywordExtraction
from radar_vagas.resumes.profile import ResumeProfile
from radar_vagas.text_utils import normalize_text


@dataclass(slots=True)
class SelectedExperience:
    experience: CandidateExperience
    bullet_ids: list[str]
    bullet_texts: list[str]


@dataclass(slots=True)
class SelectedProject:
    project: CandidateProject
    bullets: list[str]


@dataclass(slots=True)
class SelectedAdditionalExperience:
    experience: CandidateAdditionalExperience


@dataclass(slots=True)
class SelectedResumeContent:
    target_title: str
    summary: str
    skills: list[str]
    selected_skill_ids: list[str]
    experiences: list[SelectedExperience]
    projects: list[SelectedProject]
    education: list[CandidateEducation]
    highlights: list[str]
    additional_experience: list[SelectedAdditionalExperience] = field(default_factory=list)


def select_resume_content(
    *,
    job: JobPosting,
    extraction: KeywordExtraction,
    resume_profile: ResumeProfile,
    config: ProfileConfig,
) -> SelectedResumeContent:
    """Seleciona apenas conteudo aprovado e aderente ao perfil da vaga."""
    profile = resume_profile.candidate_profile
    selected_skills, selected_skill_ids = _select_skills(extraction, resume_profile, config)
    selected_summary = _select_summary(extraction, resume_profile)
    selected_experiences = _select_experiences(extraction, resume_profile)
    selected_projects = _select_projects(extraction, resume_profile, config)
    selected_additional_experience = _select_additional_experience(extraction, resume_profile)

    return SelectedResumeContent(
        target_title=job.title.strip(),
        summary=selected_summary,
        skills=selected_skills,
        selected_skill_ids=selected_skill_ids,
        experiences=selected_experiences,
        projects=selected_projects,
        education=profile.education,
        highlights=profile.highlights,
        additional_experience=selected_additional_experience,
    )


def _select_skills(
    extraction: KeywordExtraction,
    resume_profile: ResumeProfile,
    config: ProfileConfig,
) -> tuple[list[str], list[str]]:
    selected: list[tuple[str, str, int]] = []
    extraction_terms = _build_extraction_terms(
        extraction.matched_skills,
        extraction.ats_keywords,
        extraction.relevant_domains,
        extraction.tools,
    )

    for skill in resume_profile.candidate_profile.skills:
        aliases = {normalize_text(alias) for alias in skill.aliases}
        tags = {normalize_text(tag) for tag in skill.tags}
        label = normalize_text(skill.label)
        score = 0
        if label in extraction_terms:
            score += 6
        if aliases & extraction_terms:
            score += 5
        score += len(tags & extraction_terms)
        if score > 0:
            selected.append((skill.id, skill.label, score))

    ordered = sorted(selected, key=lambda item: (-item[2], item[1]))
    limited = ordered[: config.resume.maximum_skills]
    return (
        [label for _id, label, _score in limited],
        [skill_id for skill_id, _label, _score in limited],
    )


def _select_summary(extraction: KeywordExtraction, resume_profile: ResumeProfile) -> str:
    scored_blocks: list[tuple[int, str]] = []
    extraction_terms = _build_extraction_terms(
        extraction.matched_skills,
        extraction.relevant_domains,
        [extraction.target_title],
    )

    for block in resume_profile.candidate_profile.summary_blocks:
        tags = {normalize_text(tag) for tag in block.tags}
        score = len(tags & extraction_terms)
        scored_blocks.append((score, block.text))

    scored_blocks.sort(key=lambda item: (-item[0], item[1]))
    selected = [text for score, text in scored_blocks[:2] if score > 0]
    if not selected:
        selected = [resume_profile.candidate_profile.summary_blocks[0].text]
    return " ".join(selected)


def _select_experiences(
    extraction: KeywordExtraction,
    resume_profile: ResumeProfile,
) -> list[SelectedExperience]:
    extraction_terms = _build_extraction_terms(
        extraction.matched_skills,
        extraction.relevant_domains,
        extraction.ats_keywords,
        extraction.responsibilities,
        extraction.tools,
    )
    selected_experiences: list[SelectedExperience] = []

    for experience in resume_profile.candidate_profile.experiences:
        scored_bullets: list[tuple[int, str, str]] = []
        for bullet in experience.bullets:
            tags = {normalize_text(tag) for tag in bullet.tags}
            bullet_text = normalize_text(bullet.text)
            score = len(tags & extraction_terms)
            score += sum(1 for term in extraction_terms if term and term in bullet_text)
            if score > 0:
                scored_bullets.append((score, bullet.id, bullet.text))

        if not scored_bullets:
            continue

        scored_bullets.sort(key=lambda item: (-item[0], item[1]))
        chosen = scored_bullets[:3]
        selected_experiences.append(
            SelectedExperience(
                experience=experience,
                bullet_ids=[bullet_id for _score, bullet_id, _text in chosen],
                bullet_texts=[text for _score, _bullet_id, text in chosen],
            )
        )

    if not selected_experiences:
        fallback = resume_profile.candidate_profile.experiences[0]
        selected_experiences.append(
            SelectedExperience(
                experience=fallback,
                bullet_ids=[bullet.id for bullet in fallback.bullets[:3]],
                bullet_texts=[bullet.text for bullet in fallback.bullets[:3]],
            )
        )

    return selected_experiences


def _select_projects(
    extraction: KeywordExtraction,
    resume_profile: ResumeProfile,
    config: ProfileConfig,
) -> list[SelectedProject]:
    extraction_terms = _build_extraction_terms(
        extraction.matched_skills,
        extraction.relevant_domains,
        extraction.ats_keywords,
        extraction.responsibilities,
        extraction.tools,
    )
    scored_projects: list[tuple[int, CandidateProject]] = []
    for project in resume_profile.candidate_profile.projects:
        tags = {normalize_text(tag) for tag in project.tags}
        project_text = normalize_text(" ".join([project.title, *project.bullets]))
        score = len(tags & extraction_terms)
        score += sum(1 for term in extraction_terms if term and term in project_text)
        scored_projects.append((score, project))

    scored_projects.sort(key=lambda item: (-item[0], item[1].title))
    minimum_projects = min(2, len(scored_projects))
    maximum_projects = min(config.resume.maximum_projects, len(scored_projects), 3)

    selected_projects = [project for score, project in scored_projects if score > 0]
    selected_projects = selected_projects[:maximum_projects]
    if len(selected_projects) < minimum_projects:
        selected_ids = {project.id for project in selected_projects}
        for _score, project in scored_projects:
            if project.id in selected_ids:
                continue
            selected_projects.append(project)
            selected_ids.add(project.id)
            if len(selected_projects) >= minimum_projects:
                break

    return [
        SelectedProject(project=project, bullets=project.bullets[:2])
        for project in selected_projects[:maximum_projects]
    ]


def _build_extraction_terms(*groups: list[str]) -> set[str]:
    terms: set[str] = set()
    for group in groups:
        for term in group:
            normalized = normalize_text(term)
            if normalized:
                terms.add(normalized)
    return terms


def _select_additional_experience(
    extraction: KeywordExtraction,
    resume_profile: ResumeProfile,
) -> list[SelectedAdditionalExperience]:
    extraction_terms = _build_extraction_terms(
        extraction.matched_skills,
        extraction.relevant_domains,
        extraction.ats_keywords,
        extraction.responsibilities,
        extraction.tools,
        [extraction.target_title],
    )
    scored_entries: list[tuple[int, CandidateAdditionalExperience]] = []

    for entry in resume_profile.candidate_profile.additional_experiences:
        tags = {normalize_text(tag) for tag in entry.tags}
        entry_text = normalize_text(f"{entry.headline} {entry.details}")
        score = len(tags & extraction_terms)
        score += sum(1 for term in extraction_terms if term and term in entry_text)
        scored_entries.append((score, entry))

    selected_entries = [entry for score, entry in scored_entries if score > 0]
    if not selected_entries and resume_profile.candidate_profile.additional_experiences:
        selected_entries = resume_profile.candidate_profile.additional_experiences[:2]

    return [
        SelectedAdditionalExperience(experience=entry)
        for entry in selected_entries[:2]
    ]
