"""Asegura que los imports del backend resuelvan al ejecutar pytest desde cualquier
cwd."""
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
# Permite `from golden import loader` en los tests de golden datasets.
sys.path.insert(0, str(_TESTS))


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Limpia el estado en memoria del rate limiter entre tests (V1.41)."""
    import security

    security._clients.clear()
    security._rejections.clear()
    yield
    security._clients.clear()
    security._rejections.clear()

