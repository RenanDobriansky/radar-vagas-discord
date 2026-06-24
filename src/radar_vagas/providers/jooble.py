"""Provider da Jooble."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from radar_vagas.models import JobPosting
from radar_vagas.providers.base import (
    JobProvider,
    ProviderAuthenticationError,
    ProviderRequestError,
    ProviderResponseError,
)

logger = logging.getLogger(__name__)

JOOBLE_API_BASE_URL = "https://pt.jooble.org/api/"
JOOBLE_SOURCE_NAME = "Jooble"
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _before_sleep_log(retry_state: RetryCallState) -> None:
    outcome = retry_state.outcome
    if outcome is None:
        return

    exception = outcome.exception()
    if exception is None:
        return

    logger.warning(
        "jooble retrying request: attempt=%s error=%s",
        retry_state.attempt_number,
        exception.__class__.__name__,
    )


class JoobleProvider(JobProvider):
    """Client deterministico para a API de busca da Jooble.

    Assumimos o payload JSON com `keywords`, `location`, `page` e `resultOnPage`,
    seguindo o fluxo documentado de POST da pagina oficial de exemplos.
    """

    provider_name = "jooble"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 10.0,
        base_url: str = JOOBLE_API_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        cleaned_api_key = api_key.strip()
        if not cleaned_api_key:
            raise ProviderAuthenticationError("JOOBLE_API_KEY is required to query Jooble")

        self.api_key = cleaned_api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/") + "/"
        self._client = client

    @property
    def endpoint_url(self) -> str:
        return f"{self.base_url}{self.api_key}"

    def fetch_jobs(
        self,
        *,
        term: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
    ) -> list[JobPosting]:
        payload = self._build_payload(
            term=term,
            location=location,
            page=page,
            results_per_page=results_per_page,
        )
        response_payload = self._request(payload)
        jobs = self._parse_jobs(response_payload, search_term=term)
        logger.info("jooble fetched=%s term=%r location=%r", len(jobs), term, location)
        return jobs

    def _build_payload(
        self,
        *,
        term: str,
        location: str,
        page: int,
        results_per_page: int,
    ) -> dict[str, Any]:
        cleaned_term = term.strip()
        cleaned_location = location.strip()

        if not cleaned_term:
            raise ProviderRequestError("Jooble search term cannot be empty")
        if not cleaned_location:
            raise ProviderRequestError("Jooble search location cannot be empty")
        if page < 1:
            raise ProviderRequestError("Jooble page must be greater than or equal to 1")
        if results_per_page < 1:
            raise ProviderRequestError("Jooble results_per_page must be greater than or equal to 1")

        return {
            "keywords": cleaned_term,
            "location": cleaned_location,
            "page": str(page),
            "resultOnPage": str(results_per_page),
        }

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        retryer = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
            before_sleep=_before_sleep_log,
            reraise=True,
        )

        try:
            for attempt in retryer:
                with attempt:
                    return self._perform_request(payload)
        except ProviderAuthenticationError:
            raise
        except ProviderRequestError:
            raise
        except ProviderResponseError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderRequestError("Jooble request timed out") from exc
        except httpx.TransportError as exc:
            raise ProviderRequestError("Jooble request failed") from exc

    def _perform_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._client or httpx.Client(timeout=self.timeout_seconds)
        owns_client = self._client is None

        try:
            response = client.post(
                self.endpoint_url,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "radar-vagas-discord/0.1",
                },
            )
        except httpx.TimeoutException:
            raise
        except httpx.TransportError:
            raise
        finally:
            if owns_client:
                client.close()

        status_code = response.status_code
        if status_code in NON_RETRYABLE_STATUS_CODES:
            if status_code in {401, 403}:
                raise ProviderAuthenticationError(
                    f"Jooble rejected the credentials with status {status_code}"
                )
            raise ProviderRequestError(f"Jooble request failed with status {status_code}")

        if status_code in RETRYABLE_STATUS_CODES:
            if status_code == 429:
                logger.warning("jooble rate limited: status=429")
            raise httpx.TransportError(f"retryable Jooble status code: {status_code}")

        try:
            payload_document = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Jooble returned an invalid JSON payload") from exc

        if not isinstance(payload_document, dict):
            raise ProviderResponseError("Jooble payload must be a JSON object")

        return payload_document

    def _parse_jobs(self, payload: dict[str, Any], *, search_term: str) -> list[JobPosting]:
        raw_jobs = payload.get("jobs", [])
        if raw_jobs is None:
            return []
        if not isinstance(raw_jobs, list):
            raise ProviderResponseError("Jooble payload field 'jobs' must be a list")

        jobs: list[JobPosting] = []
        skipped = 0
        for raw_job in raw_jobs:
            if not isinstance(raw_job, dict):
                skipped += 1
                continue

            normalized = self._normalize_job(raw_job, search_term=search_term)
            if normalized is None:
                skipped += 1
                continue
            jobs.append(normalized)

        if skipped:
            logger.warning("jooble skipped_invalid_jobs=%s", skipped)

        return jobs

    def _normalize_job(
        self,
        raw_job: dict[str, Any],
        *,
        search_term: str,
    ) -> JobPosting | None:
        title = self._optional_string(raw_job.get("title"))
        url = self._optional_string(raw_job.get("link"))
        if not title or not url:
            return None

        provider_job_id = raw_job.get("id")
        if provider_job_id is None:
            provider_job_id = raw_job.get("job_id")

        updated_at = self._parse_optional_datetime(raw_job.get("updated"))
        published_at = self._parse_optional_datetime(raw_job.get("created"))

        return JobPosting(
            provider=self.provider_name,
            provider_job_id=str(provider_job_id).strip() if provider_job_id is not None else None,
            title=title,
            company=self._optional_string(raw_job.get("company")),
            location=self._optional_string(raw_job.get("location")),
            description=self._optional_string(raw_job.get("snippet")) or "",
            salary=self._optional_string(raw_job.get("salary")),
            employment_type=self._optional_string(raw_job.get("type")),
            published_at=published_at,
            updated_at=updated_at,
            url=url,
            source_name=JOOBLE_SOURCE_NAME,
            search_term=search_term,
            collected_at=datetime.now(UTC),
        )

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _parse_optional_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            try:
                return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).astimezone(UTC)
            except ValueError:
                return None
        return None
