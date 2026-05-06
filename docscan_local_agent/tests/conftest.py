"""Fixtures comunes para tests del agente local."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from docscan_local_agent.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Cliente de pruebas FastAPI con la app del agente."""
    app = create_app()
    return TestClient(app)
