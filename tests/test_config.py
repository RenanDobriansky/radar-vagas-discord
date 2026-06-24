from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from radar_vagas.config import (
    FileConfigurationError,
    LogLevel,
    ProfileConfig,
    RuntimeSettings,
    load_candidate_profile,
    load_profile_config,
    load_runtime_settings,
)
from radar_vagas.models import CandidateProfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_load_profile_config_from_repository_file() -> None:
    config = load_profile_config(PROJECT_ROOT / "config" / "profile.yaml")

    assert isinstance(config, ProfileConfig)
    assert config.search.minimum_score == 70
    assert "Analista de Dados" in config.search.terms


def test_load_candidate_profile_example_from_repository_file() -> None:
    profile = load_candidate_profile(PROJECT_ROOT / "config" / "candidate_profile.example.yaml")

    assert isinstance(profile, CandidateProfile)
    assert profile.candidate.name == "Rafael Exemplo da Silva"
    assert profile.education[1].status == "Curso interrompido"


def test_load_runtime_settings_with_explicit_overrides() -> None:
    settings = load_runtime_settings(
        _env_file=None,
        candidate_profile_path="config/custom_profile.yaml",
        log_level=LogLevel.DEBUG,
        environment="test",
        candidate_email="renan@example.com",
    )

    assert isinstance(settings, RuntimeSettings)
    assert settings.log_level is LogLevel.DEBUG
    assert settings.environment == "test"
    assert settings.candidate_email == "renan@example.com"
    assert settings.candidate_profile_path == Path("config/custom_profile.yaml")


def test_load_profile_config_rejects_minimum_score_out_of_range(tmp_path: Path) -> None:
    document = yaml.safe_load(
        (PROJECT_ROOT / "config" / "profile.yaml").read_text(encoding="utf-8")
    )
    document["search"]["minimum_score"] = 101
    config_path = tmp_path / "profile.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    with pytest.raises(FileConfigurationError, match="minimum_score"):
        load_profile_config(config_path)


def test_load_profile_config_requires_at_least_one_location(tmp_path: Path) -> None:
    document = yaml.safe_load(
        (PROJECT_ROOT / "config" / "profile.yaml").read_text(encoding="utf-8")
    )
    document["search"]["locations"] = ["", "   "]
    config_path = tmp_path / "profile.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    with pytest.raises(FileConfigurationError, match="locations"):
        load_profile_config(config_path)


def test_load_candidate_profile_rejects_duplicate_ids(tmp_path: Path) -> None:
    document = yaml.safe_load(
        (PROJECT_ROOT / "config" / "candidate_profile.example.yaml").read_text(encoding="utf-8")
    )
    document["skills"][1]["id"] = document["skills"][0]["id"]
    profile_path = tmp_path / "candidate_profile.yaml"
    profile_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    with pytest.raises(FileConfigurationError, match="duplicate ids"):
        load_candidate_profile(profile_path)


def test_load_candidate_profile_requires_esic_administration_as_interrupted(tmp_path: Path) -> None:
    document = yaml.safe_load(
        (PROJECT_ROOT / "config" / "candidate_profile.example.yaml").read_text(encoding="utf-8")
    )
    document["education"][1]["status"] = "Concluido"
    profile_path = tmp_path / "candidate_profile.yaml"
    profile_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    with pytest.raises(FileConfigurationError, match="Curso interrompido"):
        load_candidate_profile(profile_path)


def test_settings_keep_default_log_level_when_env_file_is_disabled() -> None:
    settings = load_runtime_settings(_env_file=None)

    assert settings.log_level is LogLevel.INFO
    assert settings.candidate_profile_path == Path("config/candidate_profile.local.yaml")
