from __future__ import annotations

import httpx
import pytest
import respx

from radar_vagas.providers.base import ProviderRequestError, ProviderResponseError
from radar_vagas.providers.remotive import REMOTIVE_API_BASE_URL, RemotiveProvider


def build_provider(**overrides: object) -> RemotiveProvider:
    payload = {
        "timeout_seconds": 0.1,
        "base_url": REMOTIVE_API_BASE_URL,
    }
    payload.update(overrides)
    return RemotiveProvider(**payload)


def build_remotive_job(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": 12345,
        "url": "https://remotive.com/remote-jobs/data/analista-de-dados-12345",
        "title": "Analista de Dados",
        "company_name": "Empresa X",
        "category": "Data",
        "job_type": "full_time",
        "publication_date": "2026-06-23T10:00:00",
        "candidate_required_location": "Worldwide",
        "salary": "$40,000 - $50,000",
        "description": "<p>Remote data job</p>",
    }
    payload.update(overrides)
    return payload


@respx.mock
def test_remotive_provider_fetches_and_normalizes_jobs() -> None:
    route = respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [build_remotive_job()]})
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(
        term="data",
        location="Curitiba",
        page=1,
        results_per_page=10,
        category="software-dev",
    )

    assert route.called
    assert route.calls[0].request.url.params["search"] == "data"
    assert route.calls[0].request.url.params["category"] == "software-dev"
    assert route.calls[0].request.url.params["limit"] == "10"
    assert len(jobs) == 1
    assert jobs[0].provider == "remotive"
    assert jobs[0].provider_job_id == "12345"
    assert jobs[0].source_name == "Remotive"
    assert str(jobs[0].url) == "https://remotive.com/remote-jobs/data/analista-de-dados-12345"


@respx.mock
def test_remotive_provider_handles_empty_response() -> None:
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(term="data", location="Curitiba")

    assert jobs == []


@respx.mock
def test_remotive_provider_retries_on_timeout() -> None:
    route = respx.get("https://remotive.com/api/remote-jobs").mock(
        side_effect=httpx.TimeoutException("boom")
    )
    provider = build_provider()

    with pytest.raises(ProviderRequestError, match="timed out"):
        provider.fetch_jobs(term="data", location="Curitiba")

    assert route.call_count == 3


@respx.mock
def test_remotive_provider_retries_on_503_then_succeeds() -> None:
    route = respx.get("https://remotive.com/api/remote-jobs").mock(
        side_effect=[
            httpx.Response(503, json={"error": "temporarily unavailable"}),
            httpx.Response(200, json={"jobs": [build_remotive_job(id=999)]}),
        ]
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(term="data", location="Curitiba")

    assert route.call_count == 2
    assert jobs[0].provider_job_id == "999"


@respx.mock
def test_remotive_provider_rejects_invalid_payload_shape() -> None:
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"jobs": "invalid"})
    )
    provider = build_provider()

    with pytest.raises(ProviderResponseError, match="must be a list"):
        provider.fetch_jobs(term="data", location="Curitiba")


@respx.mock
def test_remotive_provider_skips_incomplete_jobs() -> None:
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    build_remotive_job(id=1),
                    build_remotive_job(id=2, title=""),
                    build_remotive_job(id=3, url=None),
                ]
            },
        )
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(term="data", location="Curitiba")

    assert len(jobs) == 1
    assert jobs[0].provider_job_id == "1"


@respx.mock
def test_remotive_provider_supports_local_pagination_slice() -> None:
    jobs_payload = [build_remotive_job(id=index, title=f"Job {index}") for index in range(1, 7)]
    route = respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json={"jobs": jobs_payload})
    )
    provider = build_provider()

    jobs = provider.fetch_jobs(term="data", location="Curitiba", page=2, results_per_page=2)

    assert route.calls[0].request.url.params["limit"] == "4"
    assert [job.provider_job_id for job in jobs] == ["3", "4"]


def test_remotive_provider_declares_capabilities() -> None:
    provider = build_provider()

    assert provider.capabilities.supports_location is False
    assert provider.capabilities.supports_pagination is False
    assert provider.capabilities.supports_category is True
