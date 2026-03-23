"""Tests de configuración y secrets."""

import os
import tempfile
from pathlib import Path

import pytest

from config.secrets import SecretsManager, SecretsError


@pytest.fixture
def tmp_secrets(tmp_path):
    """Crea un SecretsManager con ficheros temporales."""
    return SecretsManager(
        secrets_file=tmp_path / "secrets.enc",
        key_file=tmp_path / ".secrets.key",
    )


class TestSettings:
    def test_defaults(self):
        from config.settings import Settings

        s = Settings()
        assert s.app_name == "DocScan Studio"
        assert s.pipeline.max_step_repeats == 3
        assert s.database.echo is False

    def test_env_override(self, monkeypatch):
        from config.settings import Settings

        monkeypatch.setenv("DOCSCAN_DEBUG", "true")
        monkeypatch.setenv("DOCSCAN_LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.debug is True
        assert s.log_level == "DEBUG"


class TestSecrets:
    def test_set_and_get(self, tmp_secrets):
        tmp_secrets.set("api_key", "sk-test-123")
        assert tmp_secrets.get("api_key") == "sk-test-123"

    def test_get_missing_returns_none(self, tmp_secrets):
        assert tmp_secrets.get("nonexistent") is None

    def test_has(self, tmp_secrets):
        assert not tmp_secrets.has("key")
        tmp_secrets.set("key", "value")
        assert tmp_secrets.has("key")

    def test_delete(self, tmp_secrets):
        tmp_secrets.set("key", "value")
        tmp_secrets.delete("key")
        assert not tmp_secrets.has("key")

    def test_delete_missing_no_error(self, tmp_secrets):
        tmp_secrets.delete("nonexistent")  # No debe fallar

    def test_list_names(self, tmp_secrets):
        tmp_secrets.set("a", "1")
        tmp_secrets.set("b", "2")
        assert sorted(tmp_secrets.list_names()) == ["a", "b"]

    def test_encrypted_on_disk(self, tmp_secrets, tmp_path):
        tmp_secrets.set("api_key", "sk-super-secret-value")
        raw = (tmp_path / "secrets.enc").read_bytes()
        assert b"sk-super-secret" not in raw

    def test_key_file_permissions(self, tmp_secrets, tmp_path):
        tmp_secrets.set("x", "y")
        key_file = tmp_path / ".secrets.key"
        import sys
        if sys.platform != "win32":
            mode = oct(key_file.stat().st_mode & 0o777)
            assert mode == "0o600"
        else:
            assert key_file.exists()

    def test_wrong_key_raises(self, tmp_path):
        sm1 = SecretsManager(
            secrets_file=tmp_path / "s.enc",
            key_file=tmp_path / "k1.key",
        )
        sm1.set("data", "secret")

        sm2 = SecretsManager(
            secrets_file=tmp_path / "s.enc",
            key_file=tmp_path / "k2.key",
        )
        with pytest.raises(SecretsError, match="descifrar"):
            sm2.get("data")

    def test_persistence_across_instances(self, tmp_path):
        kw = dict(
            secrets_file=tmp_path / "s.enc",
            key_file=tmp_path / "k.key",
        )
        SecretsManager(**kw).set("key", "value")
        assert SecretsManager(**kw).get("key") == "value"
