"""Provider da Remotive."""

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

from radar_vagas.models import JobPosting, WorkMode
from radar_vagas.providers.base import JobProvider, ProviderRequestError, ProviderResponseError

logger = logging.getLogger(__name__)

REMOTIVE_API_BASE_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_SOURCE_NAME = "Remotive"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}


def _before_sleep_log(retry_state: RetryCallState) -> None:
    outcome = retry_state.outcome
    if outcome is None:
        return

    exception = outcome.exception()
    if exception is None:
        return

    logger.warning(
        "remotive retrying request: attempt=%s error=%s",
        retry_state.attempt_number,
        exception.__class__.__name__,
    )


class RemotiveProvider(JobProvider):
    """Client para a API publica de vagas remotas da Remotive.

    A Remotive documenta `search`, `category` e `limit` como filtros opcionais.
    Como a API publica nao oferece paginacao por offset/pagina, usamos `limit`
    para buscar `page * results_per_page` e fatiar localmente.
    """

    provider_name = "remotive"

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        base_url: str = REMOTIVE_API_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url
        self._client = client

    def fetch_jobs(
        self,
        *,
        term: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
        category: str | None = None,
    ) -> list[JobPosting]:
        del location  # A API publica da Remotive nao filtra por localizacao geografica.

        if page < 1:
            raise ProviderRequestError("Remotive page must be greater than or equal to 1")
        if results_per_page < 1:
            raise ProviderRequestError(
                "Remotive results_per_page must be greater than or equal to 1"
            )

        params = self._build_params(
            term=term,
            category=category,
            limit=page * results_per_page,
        )
        response_payload = self._request(params)
        jobs = self._parse_jobs(response_payload, search_term=term)

        start = (page - 1) * results_per_page
        end = start + results_per_page
        paged_jobs = jobs[start:end]
        logger.info(
            "remotive fetched=%s page=%s results_per_page=%s term=%r category=%r",
            len(paged_jobs),
            page,
            results_per_page,
            term,
            category,
        )
        return paged_jobs

    def _build_params(
        self,
        *,
        term: str,
        category: str | None,
        limit: int,
    ) -> dict[str, str]:
        cleaned_term = term.strip()
        cleaned_category = category.strip() if category else ""

        params: dict[str, str] = {"limit": str(limit)}
        if cleaned_term:
            params["search"] = cleaned_term
        if cleaned_category:
            params["category"] = cleaned_category
        return params

    def _request(self, params: dict[str, str]) -> dict[str, Any]:
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
                    return self._perform_request(params)
        except ProviderRequestError:
            raise
        except ProviderResponseError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderRequestError("Remotive request timed out") from exc
        except httpx.TransportError as exc:
            raise ProviderRequestError("Remotive request failed") from exc

    def _perform_request(self, params: dict[str, str]) -> dict[str, Any]:
        client = self._client or httpx.Client(timeout=self.timeout_seconds)
        owns_client = self._client is None

        try:
            response = client.get(
                self.base_url,
                params=params,
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
            raise ProviderRequestError(f"Remotive request failed with status {status_code}")

        if status_code in RETRYABLE_STATUS_CODES:
            raise httpx.TransportError(f"retryable Remotive status code: {status_code}")

        try:
            payload_document = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Remotive returned an invalid JSON payload") from exc

        if not isinstance(payload_document, dict):
            raise ProviderResponseError("Remotive payload must be a JSON object")

        return payload_document

    def _parse_jobs(self, payload: dict[str, Any], *, search_term: str) -> list[JobPosting]:
        raw_jobs = payload.get("jobs", [])
        if raw_jobs is None:
            return []
        if not isinstance(raw_jobs, list):
            raise ProviderResponseError("Remotive payload field 'jobs' must be a list")

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
            logger.warning("remotive skipped_invalid_jobs=%s", skipped)

        return jobs

    def _normalize_job(
        self,
        raw_job: dict[str, Any],
        *,
        search_term: str,
    ) -> JobPosting | None:
        title = self._optional_string(raw_job.get("title"))
        url = self._optional_string(raw_job.get("url"))
        if not title or not url:
            return None

        company_name = self._optional_string(raw_job.get("company_name"))
        candidate_location = self._optional_string(raw_job.get("candidate_required_location"))
        description = self._optional_string(raw_job.get("description")) or ""
        publication_date = self._parse_optional_datetime(raw_job.get("publication_date"))

        return JobPosting(
            provider=self.provider_name,
            provider_job_id=self._stringify_id(raw_job.get("id")),
            title=title,
            company=company_name,
            location=candidate_location,
            work_mode=WorkMode.REMOTE,
            employment_type=self._optional_string(raw_job.get("job_type")),
            description=description,
            salary=self._optional_string(raw_job.get("salary")),
            published_at=publication_date,
            updated_at=publication_date,
            url=url,
            source_name=REMOTIVE_SOURCE_NAME,
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
    def _stringify_id(value: Any) -> str | None:
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
