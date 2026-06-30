"""Interfaces e erros base para providers de vagas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from radar_vagas.models import JobPosting


class ProviderError(RuntimeError):
    """Erro-base para falhas em providers."""


class ProviderAuthenticationError(ProviderError):
    """Erro de autenticacao ou autorizacao do provider."""


class ProviderRequestError(ProviderError):
    """Erro de request nao recuperavel do provider."""


class ProviderResponseError(ProviderError):
    """Erro de payload ou resposta inesperada do provider."""


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Capacidades declarativas usadas para montar consultas do provider."""

    supports_location: bool = True
    supports_pagination: bool = True
    supports_category: bool = False


class JobProvider(ABC):
    """Contrato minimo para providers que retornam vagas normalizadas."""

    provider_name: str
    capabilities: ProviderCapabilities = ProviderCapabilities()

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
