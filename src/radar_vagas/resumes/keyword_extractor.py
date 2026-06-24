"""Extracao deterministica de palavras-chave e requisitos da vaga."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from radar_vagas.config import ProfileConfig
from radar_vagas.models import JobPosting, Seniority
from radar_vagas.scoring import _detect_seniority
from radar_vagas.text_utils import normalize_text

DOMAIN_KEYWORDS = {
    "bi": ["bi", "business intelligence", "power bi", "dashboard", "indicadores"],
    "financeiro": ["financeiro", "financas", "cvm", "contabil", "orcamento"],
    "engenharia_de_dados": [
        "engenharia de dados",
        "engenheiro de dados",
        "pipeline",
        "etl",
        "pyspark",
    ],
    "analytics": ["analytics", "analise", "performance", "insights"],
    "erp": ["erp", "firebird"],
}
RESPONSIBILITY_HINTS = [
    "analisar",
    "construir",
    "criar",
    "desenvolver",
    "estruturar",
    "implementar",
    "manter",
]
RESPONSIBILITY_SPLIT_PATTERN = re.compile(r"[.\n;\u2022]+")


@dataclass(slots=True)
class KeywordExtraction:
    """Representa os elementos extraidos de forma deterministica."""

    target_title: str
    seniority: Seniority
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    relevant_domains: list[str] = field(default_factory=list)
    ats_keywords: list[str] = field(default_factory=list)


def extract_job_keywords(job: JobPosting, config: ProfileConfig) -> KeywordExtraction:
    """Extrai keywords, ferramentas e sinais de aderencia sem usar IA."""
    combined_text = normalize_text(f"{job.title} {job.description}")
    matched_skills: list[str] = []
    missing_skills: list[str] = []

    sorted_skills = sorted(
        config.scoring.skill_weights.items(),
        key=lambda item: (-item[1], item[0]),
    )
    for skill_name, _weight in sorted_skills:
        aliases = [normalize_text(alias) for alias in config.scoring.skill_aliases[skill_name]]
        if any(alias and alias in combined_text for alias in aliases):
            matched_skills.append(skill_name)
        else:
            missing_skills.append(skill_name)

    relevant_domains = [
        domain
        for domain, aliases in DOMAIN_KEYWORDS.items()
        if any(normalize_text(alias) in combined_text for alias in aliases)
    ]

    responsibilities = _extract_responsibilities(job.description)
    ats_keywords = _build_ats_keywords(
        title=job.title,
        matched_skills=matched_skills,
        domains=relevant_domains,
        responsibilities=responsibilities,
    )

    return KeywordExtraction(
        target_title=job.title.strip(),
        seniority=_detect_seniority(job, config),
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        tools=matched_skills.copy(),
        responsibilities=responsibilities,
        relevant_domains=relevant_domains,
        ats_keywords=ats_keywords,
    )


def _extract_responsibilities(description: str) -> list[str]:
    chunks = [
        chunk.strip(" -")
        for chunk in RESPONSIBILITY_SPLIT_PATTERN.split(description.replace("\r", "\n"))
    ]
    responsibilities = [
        chunk
        for chunk in chunks
        if chunk and any(hint in normalize_text(chunk) for hint in RESPONSIBILITY_HINTS)
    ]
    return responsibilities[:5]


def _build_ats_keywords(
    *,
    title: str,
    matched_skills: list[str],
    domains: list[str],
    responsibilities: list[str],
) -> list[str]:
    ordered_keywords: list[str] = []
    seen_keywords: set[str] = set()
    candidates = [title, *matched_skills, *domains, *responsibilities]

    for candidate in candidates:
        normalized = normalize_text(candidate)
        if normalized and normalized not in seen_keywords:
            ordered_keywords.append(candidate)
            seen_keywords.add(normalized)

    return ordered_keywords
