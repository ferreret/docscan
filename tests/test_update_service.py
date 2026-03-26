"""Tests para el servicio de auto-actualización."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.update_service import (
    ReleaseInfo,
    UpdateCheckResult,
    UpdateService,
)


# ── Fixtures ──────────────────────────────────────────────────────


def _make_release_json(
    tag: str = "v0.2.0",
    prerelease: bool = False,
    draft: bool = False,
    assets: list | None = None,
) -> dict:
    """Genera un JSON simulado de GitHub Release."""
    if assets is None:
        assets = [
            {
                "name": "DocScanStudio-0.2.0-linux-x86_64.AppImage",
                "browser_download_url": "https://example.com/app.AppImage",
                "size": 100_000_000,
            },
            {
                "name": "DocScanStudio-0.2.0-win64-setup.exe",
                "browser_download_url": "https://example.com/setup.exe",
                "size": 120_000_000,
            },
            {
                "name": "SHA256SUMS.TXT",
                "browser_download_url": "https://example.com/SHA256SUMS.TXT",
                "size": 256,
            },
        ]
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "draft": draft,
        "published_at": "2026-04-01T10:00:00Z",
        "body": "## Novedades\n- Feature X\n- Fix Y",
        "html_url": f"https://github.com/ferreret/docscan/releases/tag/{tag}",
        "assets": assets,
    }


def _sha256_sums_text(filename: str, sha: str) -> str:
    return f"{sha}  {filename}\n"


# ── Tests de check_for_update ─────────────────────────────────────


class TestCheckForUpdate:
    """Tests de comprobación de actualizaciones."""

    @patch("app.services.update_service.httpx.Client")
    def test_update_available(self, mock_client_cls):
        """Detecta una versión más nueva."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_release_json("v99.0.0")
        mock_resp.raise_for_status = MagicMock()

        # SHA256SUMS response
        mock_sha_resp = MagicMock()
        mock_sha_resp.status_code = 200
        mock_sha_resp.text = _sha256_sums_text(
            "DocScanStudio-99.0.0-linux-x86_64.AppImage", "abc123"
        )
        mock_sha_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.side_effect = [mock_resp, mock_sha_resp]
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is True
        assert result.latest is not None
        assert result.latest.version == "99.0.0"
        assert result.error is None

    @patch("app.services.update_service.httpx.Client")
    def test_no_update_same_version(self, mock_client_cls):
        """No detecta actualización si la versión es la misma."""
        from app._version import __version__

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_release_json(f"v{__version__}")
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is False
        assert result.latest is None

    @patch("app.services.update_service.httpx.Client")
    def test_no_releases(self, mock_client_cls):
        """No hay releases publicadas (404)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is False

    @patch("app.services.update_service.httpx.Client")
    def test_prerelease_ignored(self, mock_client_cls):
        """Las pre-releases se ignoran."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_release_json(
            "v99.0.0", prerelease=True
        )
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is False

    @patch("app.services.update_service.httpx.Client")
    def test_draft_ignored(self, mock_client_cls):
        """Los drafts se ignoran."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_release_json(
            "v99.0.0", draft=True
        )
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is False

    @patch("app.services.update_service.httpx.Client")
    def test_invalid_version_tag(self, mock_client_cls):
        """Tag con versión inválida devuelve error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_release_json("not-a-version")
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is False
        assert result.error is not None

    @patch("app.services.update_service.httpx.Client")
    def test_timeout_handled(self, mock_client_cls):
        """El timeout no lanza excepción."""
        import httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is False
        assert "Timeout" in result.error

    @patch("app.services.update_service.httpx.Client")
    def test_no_platform_asset(self, mock_client_cls):
        """Update disponible pero sin asset para la plataforma."""
        release = _make_release_json("v99.0.0", assets=[
            {
                "name": "DocScanStudio-99.0.0-macos-arm64.dmg",
                "browser_download_url": "https://example.com/app.dmg",
                "size": 100_000_000,
            },
        ])

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = release
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        svc = UpdateService()
        result = svc.check_for_update()

        assert result.available is True
        assert result.error is not None
        assert "plataforma" in result.error


# ── Tests de verify_checksum ──────────────────────────────────────


class TestVerifyChecksum:
    """Tests de verificación de integridad."""

    def test_valid_checksum(self, tmp_path):
        """Checksum correcto pasa la verificación."""
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()

        file_path = tmp_path / "test.bin"
        file_path.write_bytes(content)

        assert UpdateService.verify_checksum(file_path, expected) is True

    def test_invalid_checksum(self, tmp_path):
        """Checksum incorrecto falla la verificación."""
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(b"hello world")

        assert UpdateService.verify_checksum(file_path, "bad_hash") is False

    def test_empty_checksum_skips(self, tmp_path):
        """Sin checksum se omite la verificación."""
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(b"data")

        assert UpdateService.verify_checksum(file_path, "") is True


# ── Tests de _find_platform_asset ─────────────────────────────────


class TestFindPlatformAsset:
    """Tests de selección de asset por plataforma."""

    def test_linux_appimage(self):
        """Selecciona AppImage en Linux."""
        assets = [
            {"name": "DocScanStudio-0.2.0-linux-x86_64.AppImage", "browser_download_url": "u1"},
            {"name": "DocScanStudio-0.2.0-win64-setup.exe", "browser_download_url": "u2"},
        ]
        with patch("app.services.update_service.platform") as mock_plat:
            mock_plat.system.return_value = "Linux"
            mock_plat.machine.return_value = "x86_64"
            result = UpdateService._find_platform_asset(assets)
            assert result is not None
            assert "AppImage" in result["name"]

    def test_windows_exe(self):
        """Selecciona .exe en Windows."""
        assets = [
            {"name": "DocScanStudio-0.2.0-linux-x86_64.AppImage", "browser_download_url": "u1"},
            {"name": "DocScanStudio-0.2.0-win64-setup.exe", "browser_download_url": "u2"},
        ]
        with patch("app.services.update_service.platform") as mock_plat:
            mock_plat.system.return_value = "Windows"
            mock_plat.machine.return_value = "AMD64"
            result = UpdateService._find_platform_asset(assets)
            assert result is not None
            assert "setup.exe" in result["name"]

    def test_unsupported_platform(self):
        """Devuelve None en plataforma no soportada."""
        assets = [
            {"name": "DocScanStudio-0.2.0-linux-x86_64.AppImage", "browser_download_url": "u1"},
        ]
        with patch("app.services.update_service.platform") as mock_plat:
            mock_plat.system.return_value = "Darwin"
            mock_plat.machine.return_value = "arm64"
            result = UpdateService._find_platform_asset(assets)
            assert result is None


# ── Tests de current_version ──────────────────────────────────────


class TestCurrentVersion:
    """Tests de la propiedad de versión."""

    def test_returns_version_string(self):
        svc = UpdateService()
        assert isinstance(svc.current_version, str)
        assert len(svc.current_version) > 0
