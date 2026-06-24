"""Utilitarios para nomes seguros de arquivos de curriculo."""

from __future__ import annotations

import re

from radar_vagas.text_utils import strip_accents

INVALID_FILENAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
WHITESPACE_PATTERN = re.compile(r"\s+")


def sanitize_file_name_segment(value: str, *, fallback: str = "Sem_Valor") -> str:
    """Gera um segmento seguro para Windows e Linux."""
    cleaned = strip_accents(value).strip()
    cleaned = INVALID_FILENAME_PATTERN.sub(" ", cleaned)
    cleaned = WHITESPACE_PATTERN.sub("_", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def build_resume_file_name(*, company: str, title: str, pattern: str) -> str:
    """Aplica o padrao de nomenclatura do curriculo com segmentos sanitizados."""
    safe_company = sanitize_file_name_segment(company, fallback="Empresa")
    safe_title = sanitize_file_name_segment(title, fallback="Cargo")
    return pattern.format(company=safe_company, title=safe_title)
