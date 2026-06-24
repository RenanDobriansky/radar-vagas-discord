"""Carregamento do perfil-base aprovado para geracao de curriculos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from radar_vagas.config import FileConfigurationError, RuntimeSettings, load_candidate_profile
from radar_vagas.models import CandidateProfile


@dataclass(slots=True)
class ResumeProfile:
    """Perfil-base carregado com dados de contato vindos do ambiente."""

    candidate_profile: CandidateProfile
    email: str
    phone: str
    source_path: Path


def load_resume_profile(settings: RuntimeSettings) -> ResumeProfile:
    """Carrega o perfil-base e valida dados de contato obrigatorios."""
    if not settings.candidate_email:
        raise FileConfigurationError("CANDIDATE_EMAIL is required to generate resumes")
    if not settings.candidate_phone:
        raise FileConfigurationError("CANDIDATE_PHONE is required to generate resumes")

    source_path = settings.candidate_profile_path
    candidate_profile = load_candidate_profile(source_path)

    return ResumeProfile(
        candidate_profile=candidate_profile,
        email=settings.candidate_email,
        phone=settings.candidate_phone,
        source_path=Path(source_path),
    )
