from __future__ import annotations

import json

import httpx
import pytest
import respx

from radar_vagas.cli import main
from radar_vagas.config import RuntimeSettings
from radar_vagas.providers.base import (
    ProviderAuthenticationError,
    ProviderRequestError,
)
from radar_vagas.providers.jooble import JOOBLE_API_BASE_URL, JoobleProvider


def build_provider(**overrides: object) -> JoobleProvider:
    payload = {
        "api_key": "test-api-key",
        "timeout_seconds": 0.1,
        "base_url": JOOBLE_API_BASE_URL,
    }
    payload.update(overrides)
    return JoobleProvider(**payload)


def build_jooble_job(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": 12345,
        "title": "Analista de Dados Junior",
        "company": "Empresa X",
        "location": "Curitiba - PR",
        "snippet": "SQL, Power BI e Python.",
        "salary": "R$ 5.000",
        "type": "CLT",
        "link": "https://example.com/jobs/12345",
        "updated": "2026-06-23T10:00:00Z",
    }
    payload.update(overrides)
    return payload


@respx.mock
def test_jooble_provider_fetches_and_normalizes_jobs() -> None:
    route = respx.post("https://pt.jooble.org/api/test-api-key").mock(
        return_value=httpx.Response(
            200,
            json={"jobs": [build_jooble_job()]},
        )
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(
        term="Analista de Dados",
        location="Curitiba",
        page=2,
        results_per_page=15,
    )

    assert route.called
    request_payload = route.calls[0].request.content.decode("utf-8")
    assert json.loads(request_payload) == {
        "keywords": "Analista de Dados",
        "location": "Curitiba",
        "page": "2",
        "resultOnPage": "15",
    }
    assert len(jobs) == 1
    assert jobs[0].provider == "jooble"
    assert jobs[0].provider_job_id == "12345"
    assert jobs[0].employment_type == "CLT"
    assert jobs[0].source_name == "Jooble"


@respx.mock
def test_jooble_provider_handles_empty_response() -> None:
    respx.post("https://pt.jooble.org/api/test-api-key").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(term="Analista de Dados", location="Curitiba")

    assert jobs == []


@respx.mock
def test_jooble_provider_retries_on_timeout() -> None:
    route = respx.post("https://pt.jooble.org/api/test-api-key").mock(
        side_effect=httpx.TimeoutException("boom")
    )
    provider = build_provider()

    with pytest.raises(ProviderRequestError, match="timed out"):
        provider.fetch_jobs(term="Analista de Dados", location="Curitiba")

    assert route.call_count == 3


@respx.mock
def test_jooble_provider_does_not_retry_on_403() -> None:
    route = respx.post("https://pt.jooble.org/api/test-api-key").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    provider = build_provider()

    with pytest.raises(ProviderAuthenticationError, match="status 403"):
        provider.fetch_jobs(term="Analista de Dados", location="Curitiba")

    assert route.call_count == 1


@respx.mock
def test_jooble_provider_retries_on_429_then_succeeds() -> None:
    route = respx.post("https://pt.jooble.org/api/test-api-key").mock(
        side_effect=[
            httpx.Response(429, json={"error": "too many requests"}),
            httpx.Response(200, json={"jobs": [build_jooble_job(id=999)]}),
        ]
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(term="Analista de Dados", location="Curitiba")

    assert route.call_count == 2
    assert jobs[0].provider_job_id == "999"


@respx.mock
def test_jooble_provider_skips_incomplete_payload_items() -> None:
    respx.post("https://pt.jooble.org/api/test-api-key").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    build_jooble_job(id=1),
                    build_jooble_job(id=2, title=""),
                    build_jooble_job(id=3, link=None),
                ]
            },
        )
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(term="Analista de Dados", location="Curitiba")

    assert len(jobs) == 1
    assert jobs[0].provider_job_id == "1"


def test_jooble_provider_requires_api_key() -> None:
    with pytest.raises(ProviderAuthenticationError, match="JOOBLE_API_KEY"):
        build_provider(api_key="  ")


def test_cli_jooble_dry_run_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "radar_vagas.cli.load_runtime_settings",
        lambda: RuntimeSettings.model_validate(
            {"jooble_api_key": "test-api-key", "_env_file": None}
        ),
    )

    class StubProvider:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key

        def fetch_jobs(
            self,
            *,
            term: str,
            location: str,
            page: int = 1,
            results_per_page: int = 20,
        ) -> list[object]:
            return []

    monkeypatch.setattr("radar_vagas.cli.JoobleProvider", StubProvider)

    exit_code = main(
        [
            "--provider",
            "jooble",
            "--dry-run",
            "--term",
            "Analista de Dados",
            "--location",
            "Curitiba",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["provider"] == "jooble"
    assert payload["fetched"] == 0


def test_cli_jooble_dry_run_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "radar_vagas.cli.load_runtime_settings",
        lambda: RuntimeSettings.model_validate({"_env_file": None}),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--provider",
                "jooble",
                "--dry-run",
                "--term",
                "Analista de Dados",
                "--location",
                "Curitiba",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "JOOBLE_API_KEY is required" in captured.err
