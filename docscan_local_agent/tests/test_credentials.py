"""Tests del storage de credenciales del agente.

El agente persiste sus credenciales de pairing (agent_token + metadatos
del SaaS) en ``~/.docscan/agent.json``. Estas pruebas cubren load/save/
clear con un ``config_dir`` apuntando a un tmp_path para no tocar el HOME
real durante los tests.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from docscan_local_agent.credentials import (
    AgentCredentials,
    clear_credentials,
    load_credentials,
    save_credentials,
)


def _sample_creds() -> AgentCredentials:
    return AgentCredentials(
        saas_url="https://docscan.example.com",
        agent_token="42.deadbeefcafebabe",
        device_id=42,
        device_name="Portátil Ana",
        user_email="ana@example.com",
        tenant_name="TecnoMedia",
        paired_at=datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    """Sin agent.json, load_credentials devuelve None (estado pre-pairing)."""
    assert load_credentials(tmp_path) is None


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    """save + load reconstruye exactamente las credenciales."""
    creds = _sample_creds()
    save_credentials(creds, tmp_path)

    loaded = load_credentials(tmp_path)
    assert loaded is not None
    assert loaded == creds


def test_save_creates_config_dir_if_missing(tmp_path: Path) -> None:
    """Si el directorio de config no existe, save lo crea."""
    nested = tmp_path / "does" / "not" / "exist"
    creds = _sample_creds()
    save_credentials(creds, nested)
    assert (nested / "agent.json").is_file()


def test_save_overwrites_existing_file(tmp_path: Path) -> None:
    """Re-pairing: el segundo save reemplaza la versión previa."""
    save_credentials(_sample_creds(), tmp_path)

    new_creds = _sample_creds().model_copy(
        update={"device_id": 99, "agent_token": "99.newsecret"}
    )
    save_credentials(new_creds, tmp_path)

    loaded = load_credentials(tmp_path)
    assert loaded is not None
    assert loaded.device_id == 99
    assert loaded.agent_token == "99.newsecret"


def test_load_returns_none_when_file_corrupt(tmp_path: Path) -> None:
    """JSON corrupto se trata como pre-pairing (no crashea el agente)."""
    (tmp_path / "agent.json").write_text("{this is not json}")
    assert load_credentials(tmp_path) is None


def test_load_returns_none_when_schema_invalid(tmp_path: Path) -> None:
    """JSON sintácticamente válido pero sin los campos esperados → None."""
    (tmp_path / "agent.json").write_text(json.dumps({"foo": "bar"}))
    assert load_credentials(tmp_path) is None


@pytest.mark.skipif(sys.platform == "win32", reason="permisos POSIX")
def test_save_writes_with_owner_only_permissions(tmp_path: Path) -> None:
    """En POSIX agent.json se escribe con 0600 (sólo el dueño)."""
    save_credentials(_sample_creds(), tmp_path)
    mode = (tmp_path / "agent.json").stat().st_mode & 0o777
    assert mode == 0o600


def test_clear_removes_file(tmp_path: Path) -> None:
    """clear borra agent.json. load tras clear devuelve None."""
    save_credentials(_sample_creds(), tmp_path)
    assert (tmp_path / "agent.json").exists()

    clear_credentials(tmp_path)
    assert not (tmp_path / "agent.json").exists()
    assert load_credentials(tmp_path) is None


def test_clear_is_idempotent(tmp_path: Path) -> None:
    """clear sin fichero previo no lanza excepción."""
    clear_credentials(tmp_path)  # no debe crashear


def test_save_is_atomic_under_concurrent_failure(tmp_path: Path, monkeypatch) -> None:
    """Si la escritura del tmp falla, el agent.json previo no queda corrupto.

    Estrategia: guardamos unas credenciales válidas. Luego forzamos que
    ``os.replace`` lance OSError. El agent.json previo debe seguir
    siendo legible y coincidir con la primera versión.
    """
    save_credentials(_sample_creds(), tmp_path)

    real_replace = os.replace

    def _boom(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr("docscan_local_agent.credentials.os.replace", _boom)

    new_creds = _sample_creds().model_copy(update={"device_id": 99})
    with pytest.raises(OSError):
        save_credentials(new_creds, tmp_path)

    # El fichero original debe permanecer intacto.
    loaded = load_credentials(tmp_path)
    assert loaded is not None
    assert loaded.device_id == 42
