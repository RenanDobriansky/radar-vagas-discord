"""Validacoes de configuracao para GitHub Actions e Dependabot."""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(relative_path: str) -> tuple[dict[str, object], str]:
    path = PROJECT_ROOT / relative_path
    raw_text = path.read_text(encoding="utf-8")
    return yaml.safe_load(raw_text), raw_text


def test_ci_workflow_is_read_only_and_secret_free() -> None:
    workflow, raw_text = _load_yaml(".github/workflows/ci.yml")

    assert workflow["name"] == "CI"
    assert workflow["on"] == {
        "push": None,
        "pull_request": None,
        "workflow_dispatch": None,
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert "${{ secrets." not in raw_text

    job = workflow["jobs"]["validate"]
    assert job["permissions"] == {"contents": "read"}

    run_commands = [
        step["run"]
        for step in job["steps"]
        if isinstance(step, dict) and "run" in step
    ]
    assert any("ruff check ." in command for command in run_commands)
    assert any("pytest" in command for command in run_commands)


def test_radar_workflow_scopes_secrets_to_steps_and_uploads_only_sanitized_artifacts() -> None:
    workflow, raw_text = _load_yaml(".github/workflows/radar.yml")

    assert workflow["permissions"] == {"contents": "read"}
    assert len(workflow["on"]["schedule"]) == 2
    assert workflow["on"]["schedule"][0]["timezone"] == "America/Sao_Paulo"
    assert workflow["on"]["schedule"][1]["timezone"] == "America/Sao_Paulo"
    assert "upload_resume_artifact" not in raw_text
    assert "*.docx" not in raw_text

    validate_job = workflow["jobs"]["validate"]
    radar_job = workflow["jobs"]["radar"]
    assert validate_job["permissions"] == {"contents": "read"}
    assert radar_job["permissions"] == {"contents": "write"}

    radar_job_env = radar_job["env"]
    assert all("${{ secrets." not in str(value) for value in radar_job_env.values())

    step_by_name = {
        step["name"]: step
        for step in radar_job["steps"]
        if isinstance(step, dict) and "name" in step
    }
    assert step_by_name["Validate required secrets"]["env"] == {
        "DISCORD_WEBHOOK_URL": "${{ secrets.DISCORD_WEBHOOK_URL }}",
        "JOOBLE_API_KEY": "${{ secrets.JOOBLE_API_KEY }}",
        "CANDIDATE_EMAIL": "${{ secrets.CANDIDATE_EMAIL }}",
        "CANDIDATE_PHONE": "${{ secrets.CANDIDATE_PHONE }}",
        "CANDIDATE_PROFILE_YAML": "${{ secrets.CANDIDATE_PROFILE_YAML }}",
    }
    assert step_by_name["Materialize candidate profile"]["env"] == {
        "CANDIDATE_PROFILE_YAML": "${{ secrets.CANDIDATE_PROFILE_YAML }}",
    }
    assert step_by_name["Run radar"]["env"] == {
        "DISCORD_WEBHOOK_URL": "${{ secrets.DISCORD_WEBHOOK_URL }}",
        "JOOBLE_API_KEY": "${{ secrets.JOOBLE_API_KEY }}",
        "CANDIDATE_EMAIL": "${{ secrets.CANDIDATE_EMAIL }}",
        "CANDIDATE_PHONE": "${{ secrets.CANDIDATE_PHONE }}",
    }
    assert (
        step_by_name["Upload sanitized execution report"]["with"]["path"]
        == "${{ env.SANITIZED_REPORT_PATH }}"
    )


def test_dependabot_covers_python_and_github_actions() -> None:
    config, _raw_text = _load_yaml(".github/dependabot.yml")

    assert config["version"] == 2
    ecosystems = {
        update["package-ecosystem"]: update
        for update in config["updates"]
    }

    assert set(ecosystems) == {"pip", "github-actions"}
    assert ecosystems["pip"]["directory"] == "/"
    assert ecosystems["github-actions"]["directory"] == "/"
