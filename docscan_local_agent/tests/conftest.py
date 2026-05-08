"""Fixtures comunes para tests del agente local."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docscan_local_agent.deps import get_settings
from docscan_local_agent.main import create_app
from docscan_local_agent.settings import AgentSettings


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Cliente de pruebas FastAPI con config_dir aislado en tmp_path.

    Sin este aislamiento la fixture leía ``~/.docscan/`` real y los
    tests cambiaban de comportamiento si la máquina tenía un agente
    pareado (caso típico tras smoke local). Cada test arranca sin
    credenciales salvo que las cree explícitamente con
    ``save_credentials(creds, tmp_path)``.
    """
    app = create_app()
    settings = AgentSettings(config_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)
