"""Carregamento e validacao de configuracoes do projeto."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from radar_vagas.models import CandidateProfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_CONFIG_PATH = PROJECT_ROOT / "config" / "profile.yaml"


class ConfigurationError(RuntimeError):
    """Erro-base para falhas seguras de configuracao."""


class EnvironmentConfigurationError(ConfigurationError):
    """Falha ao carregar variaveis de ambiente."""


class FileConfigurationError(ConfigurationError):
    """Falha ao carregar ou validar um arquivo de configuracao."""


class LogLevel(StrEnum):
    """Niveis de log aceitos pela aplicacao."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EnvironmentName(StrEnum):
    """Ambientes aceitos pela aplicacao."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class CandidateConfig(BaseModel):
    """Dados fixos do candidato para a configuracao principal."""

    name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    linkedin_url: str = Field(min_length=1)
    github_url: str = Field(min_length=1)
    email_env: str = Field(min_length=1)
    phone_env: str = Field(min_length=1)


class ResumeConfig(BaseModel):
    """Configuracoes de geracao de curriculo."""

    enabled: bool = True
    output_directory: Path
    language: str = Field(min_length=1)
    preferred_max_pages: int = Field(ge=1)
    hard_max_pages: int = Field(ge=1)
    maximum_projects: int = Field(ge=1)
    maximum_skills: int = Field(ge=1)
    attach_to_discord: bool = True
    keep_generated_files: bool = False
    file_name_pattern: str = Field(min_length=1)

    @field_validator("hard_max_pages")
    @classmethod
    def validate_page_limit(cls, value: int, info: Any) -> int:
        preferred = info.data.get("preferred_max_pages")
        if isinstance(preferred, int) and value < preferred:
            raise ValueError("hard_max_pages must be greater than or equal to preferred_max_pages")
        return value


class SearchConfig(BaseModel):
    """Configuracoes de busca e corte minimo."""

    minimum_score: int = Field(ge=0, le=100)
    maximum_jobs_per_run: int = Field(ge=1)
    maximum_age_days: int = Field(ge=1)
    include_internships: bool = False
    terms: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)

    @field_validator("terms", "locations")
    @classmethod
    def validate_non_empty_string_list(cls, value: list[str], info: Any) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError(f"{info.field_name} must contain at least one non-empty entry")
        return cleaned


class SkillProfileConfig(BaseModel):
    """Competencias declaradas no perfil de busca."""

    primary_skills: list[str] = Field(default_factory=list)
    secondary_skills: list[str] = Field(default_factory=list)

    @field_validator("primary_skills")
    @classmethod
    def validate_primary_skills(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("primary_skills must contain at least one non-empty entry")
        return cleaned

    @field_validator("secondary_skills")
    @classmethod
    def validate_secondary_skills(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class FilterConfig(BaseModel):
    """Termos excludentes usados pelo pipeline."""

    excluded_seniority: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)


class ProfileConfig(BaseModel):
    """Representa o arquivo `config/profile.yaml`."""

    candidate: CandidateConfig
    resume: ResumeConfig
    search: SearchConfig
    profile: SkillProfileConfig
    filters: FilterConfig


class RuntimeSettings(BaseSettings):
    """Variaveis de ambiente usadas pela aplicacao."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_webhook_url: str | None = None
    jooble_api_key: str | None = None
    candidate_email: str | None = None
    candidate_phone: str | None = None
    candidate_profile_path: Path = Path("config/candidate_profile.local.yaml")
    log_level: LogLevel = LogLevel.INFO
    environment: EnvironmentName = EnvironmentName.DEVELOPMENT

    @field_validator(
        "discord_webhook_url",
        "jooble_api_key",
        "candidate_email",
        "candidate_phone",
        mode="before",
    )
    @classmethod
    def strip_optional_secrets(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("candidate_profile_path", mode="before")
    @classmethod
    def normalize_profile_path(cls, value: Any) -> Path:
        if isinstance(value, Path):
            return value
        return Path(str(value).strip())


class AppConfig(BaseModel):
    """Agrega runtime, configuracao principal e perfil-base."""

    runtime: RuntimeSettings
    profile: ProfileConfig
    candidate_profile: CandidateProfile


def _resolve_path(path: Path | str) -> Path:
    candidate = path if isinstance(path, Path) else Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def _format_validation_error(error: ValidationError) -> str:
    details = []
    for issue in error.errors():
        location = ".".join(str(part) for part in issue["loc"])
        details.append(f"{location}: {issue['msg']}")
    return "; ".join(details)


def _read_yaml_file(path: Path | str) -> dict[str, Any]:
    resolved_path = _resolve_path(path)

    if not resolved_path.exists():
        raise FileConfigurationError(f"Configuration file not found: {resolved_path}")

    try:
        raw_text = resolved_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileConfigurationError(f"Could not read configuration file: {resolved_path}") from exc

    try:
        loaded = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise FileConfigurationError(
            f"Invalid YAML in configuration file: {resolved_path}"
        ) from exc

    if not isinstance(loaded, dict):
        raise FileConfigurationError(f"Configuration file must contain a mapping: {resolved_path}")

    return loaded


def load_runtime_settings(**overrides: Any) -> RuntimeSettings:
    """Carrega as variaveis de ambiente com validacao segura."""
    try:
        return RuntimeSettings(**overrides)
    except ValidationError as exc:
        message = _format_validation_error(exc)
        raise EnvironmentConfigurationError(
            f"Invalid environment configuration: {message}"
        ) from exc


def load_profile_config(path: Path | str = DEFAULT_PROFILE_CONFIG_PATH) -> ProfileConfig:
    """Carrega e valida o arquivo principal `config/profile.yaml`."""
    document = _read_yaml_file(path)

    try:
        return ProfileConfig.model_validate(document)
    except ValidationError as exc:
        message = _format_validation_error(exc)
        resolved_path = _resolve_path(path)
        raise FileConfigurationError(
            f"Invalid profile configuration in {resolved_path}: {message}"
        ) from exc


def load_candidate_profile(path: Path | str) -> CandidateProfile:
    """Carrega e valida o perfil-base do candidato."""
    document = _read_yaml_file(path)

    try:
        return CandidateProfile.model_validate(document)
    except ValidationError as exc:
        message = _format_validation_error(exc)
        resolved_path = _resolve_path(path)
        raise FileConfigurationError(
            f"Invalid candidate profile in {resolved_path}: {message}"
        ) from exc


def load_app_config(
    *,
    profile_path: Path | str = DEFAULT_PROFILE_CONFIG_PATH,
    candidate_profile_path: Path | str | None = None,
    **settings_overrides: Any,
) -> AppConfig:
    """Carrega toda a configuracao necessaria para a aplicacao."""
    runtime = load_runtime_settings(**settings_overrides)
    profile = load_profile_config(profile_path)

    selected_profile_path = candidate_profile_path or runtime.candidate_profile_path
    candidate_profile = load_candidate_profile(selected_profile_path)

    return AppConfig(
        runtime=runtime,
        profile=profile,
        candidate_profile=candidate_profile,
    )
