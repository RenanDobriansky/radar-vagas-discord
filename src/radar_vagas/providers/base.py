"""Interfaces e erros base para providers de vagas."""

from __future__ import annotations

from abc import ABC, abstractmethod

from radar_vagas.models import JobPosting


class ProviderError(RuntimeError):
    """Erro-base para falhas em providers."""


class ProviderAuthenticationError(ProviderError):
    """Erro de autenticacao ou autorizacao do provider."""


class ProviderRequestError(ProviderError):
    """Erro de request nao recuperavel do provider."""


class ProviderResponseError(ProviderError):
    """Erro de payload ou resposta inesperada do provider."""


class JobProvider(ABC):
    """Contrato minimo para providers que retornam vagas normalizadas."""

    provider_name: str

    @abstractmethod
    def fetch_jobs(
        self,
        *,
        term: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
    ) -> list[JobPosting]:
        """Busca vagas e retorna itens normalizados."""
