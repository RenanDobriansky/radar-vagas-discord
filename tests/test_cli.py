from __future__ import annotations

import logging

from radar_vagas.cli import _configure_logging


def test_verbose_logging_keeps_http_clients_quiet() -> None:
    _configure_logging(verbose=True)

    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("httpx").level == logging.WARNING
