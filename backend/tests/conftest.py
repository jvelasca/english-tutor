"""Asegura que los imports del backend resuelvan al ejecutar pytest desde cualquier
cwd."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Limpia el estado en memoria del rate limiter entre tests (V1.41)."""
    import security

    security._clients.clear()
    yield
    security._clients.clear()

