"""Utilitarios de texto para normalizacao e comparacao.

Decisoes importantes desta etapa:
- a comparacao textual ignora acentos, caixa e espacos duplicados;
- a URL normalizada remove apenas parametros de rastreamento conhecidos,
  preservando parametros funcionais da vaga;
- o fingerprint usa titulo, empresa e localizacao normalizados para impedir
  que empresas diferentes sejam mescladas.
"""

from __future__ import annotations

from hashlib import sha256
from unicodedata import normalize
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PARAM_NAMES = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref_src",
    "s_cid",
}

TRACKING_QUERY_PARAM_PREFIXES = ("utm_",)


def strip_accents(value: str) -> str:
    """Remove acentos de forma segura para comparacao."""
    normalized = normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def normalize_whitespace(value: str) -> str:
    """Reduz espacos consecutivos para um unico espaco."""
    return " ".join(value.split())


def normalize_text(value: str | None) -> str:
    """Normaliza texto para comparacao estavel.

    O retorno sempre usa lower case, remove acentos e normaliza espacos.
    Valores ausentes sao convertidos para string vazia para facilitar
    composicoes de chaves e fingerprints.
    """
    if value is None:
        return ""

    return normalize_whitespace(strip_accents(value)).casefold()


def is_tracking_query_param(name: str) -> bool:
    """Indica se um parametro de query e apenas rastreamento."""
    lowered_name = name.casefold()
    return lowered_name in TRACKING_QUERY_PARAM_NAMES or lowered_name.startswith(
        TRACKING_QUERY_PARAM_PREFIXES
    )


def normalize_url(url: str) -> str:
    """Remove ruido de rastreamento e estabiliza a URL para comparacao.

    Preserva query params funcionais e ordena a query final para que a mesma
    vaga nao pareca diferente apenas pela ordem dos parametros.
    """
    parts = urlsplit(url.strip())

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    filtered_query_pairs = [
        (name, value) for name, value in query_pairs if not is_tracking_query_param(name)
    ]
    normalized_query = urlencode(sorted(filtered_query_pairs))

    normalized_path = parts.path.rstrip("/") or "/"

    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            normalized_path,
            normalized_query,
            "",
        )
    )


def make_job_fingerprint(title: str, company: str | None, location: str | None) -> str:
    """Cria um fingerprint SHA-256 com titulo, empresa e localizacao."""
    normalized_title = normalize_text(title)
    normalized_company = normalize_text(company)
    normalized_location = normalize_text(location)
    raw_identity = "||".join((normalized_title, normalized_company, normalized_location))
    return sha256(raw_identity.encode("utf-8")).hexdigest()
