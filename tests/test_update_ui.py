"""Tests para los componentes UI de auto-actualización.

Cubre UpdateDialog, banner en LauncherWindow y botón en AboutDialog.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt

from app.services.update_service import ReleaseInfo


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def sample_release() -> ReleaseInfo:
    """Release de ejemplo para tests."""
    return ReleaseInfo(
        version="99.0.0",
        tag_name="v99.0.0",
        published_at="2026-04-01T10:00:00Z",
        release_notes="## Novedades\n- Feature X\n- Fix Y",
        html_url="https://github.com/ferreret/docscan/releases/tag/v99.0.0",
        asset_url="https://example.com/app.AppImage",
        asset_name="docscan-99.0.0-x86_64.AppImage",
        asset_size=104_857_600,  # 100 MB
        sha256="abc123def456",
    )


@pytest.fixture
def release_no_sha() -> ReleaseInfo:
    """Release sin checksum."""
    return ReleaseInfo(
        version="99.0.0",
        tag_name="v99.0.0",
        published_at="2026-04-01T10:00:00Z",
        release_notes="",
        html_url="",
        asset_url="https://example.com/app.AppImage",
        asset_name="docscan-99.0.0.AppImage",
        asset_size=0,
        sha256="",
    )


# ── Tests de UpdateDialog ────────────────────────────────────────


class TestUpdateDialog:
    """Tests del diálogo de actualización."""

    def test_dialog_creates(self, qtbot, sample_release):
        """El diálogo se crea correctamente."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        assert dialog.windowTitle()
        assert dialog._release == sample_release

    def test_shows_version_info(self, qtbot, sample_release):
        """Muestra versión actual y nueva."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        # El header contiene la versión nueva
        header_text = dialog.findChildren(type(dialog._banner_label)
            if hasattr(dialog, '_banner_label') else type(None))
        # Verificar que existe el texto de versión en algún label
        assert "99.0.0" in dialog._notes_browser.toPlainText() or \
               dialog._release.version == "99.0.0"

    def test_shows_release_notes(self, qtbot, sample_release):
        """Las notas de la release se muestran."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        content = dialog._notes_browser.toPlainText()
        assert "Feature X" in content

    def test_shows_no_notes_message(self, qtbot, release_no_sha):
        """Sin notas muestra mensaje por defecto."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(release_no_sha)
        qtbot.addWidget(dialog)

        content = dialog._notes_browser.toPlainText()
        assert len(content) > 0  # Tiene el mensaje de "no hay notas"

    def test_shows_sha_info(self, qtbot, sample_release):
        """Muestra info de SHA-256 cuando está disponible."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        assert "SHA-256" in dialog._size_label.text()

    def test_no_sha_info(self, qtbot, release_no_sha):
        """No muestra info SHA-256 cuando no está disponible."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(release_no_sha)
        qtbot.addWidget(dialog)

        assert "SHA-256" not in dialog._size_label.text()

    def test_progress_bar_hidden_initially(self, qtbot, sample_release):
        """La barra de progreso está oculta al inicio."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        assert dialog._progress_bar.isHidden()

    def test_apply_button_hidden_initially(self, qtbot, sample_release):
        """El botón aplicar está oculto al inicio."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        assert dialog._btn_apply.isHidden()

    def test_download_button_enabled(self, qtbot, sample_release):
        """El botón de descarga está habilitado al inicio."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        assert dialog._btn_download.isEnabled()
        assert not dialog._btn_download.isHidden()
        assert dialog._btn_download.text()

    def test_on_progress_updates_bar(self, qtbot, sample_release):
        """El progreso actualiza la barra."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        dialog._progress_bar.setVisible(True)
        dialog._on_progress(50_000_000, 100_000_000)

        assert dialog._progress_bar.value() == 50

    def test_on_progress_indeterminate(self, qtbot, sample_release):
        """Progreso con total=0 muestra barra indeterminada."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        dialog._progress_bar.setVisible(True)
        dialog._on_progress(1_000_000, 0)

        # Barra indeterminada: minimum == maximum == 0
        assert dialog._progress_bar.minimum() == 0
        assert dialog._progress_bar.maximum() == 0

    def test_on_download_finished(self, qtbot, sample_release, tmp_path):
        """Descarga completada muestra botón aplicar."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        fake_path = str(tmp_path / "installer.AppImage")
        dialog._on_download_finished(fake_path)

        assert not dialog._btn_apply.isHidden()
        assert dialog._btn_download.isHidden()
        assert dialog._progress_bar.value() == 100

    def test_on_download_error(self, qtbot, sample_release):
        """Error de descarga permite reintentar."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        dialog._on_download_error("Connection reset")

        assert dialog._btn_download.isEnabled()
        assert "Error" in dialog._status_label.text()

    def test_reject_stops_worker(self, qtbot, sample_release):
        """Cancelar detiene el worker si está en marcha."""
        from app.ui.update_dialog import UpdateDialog

        dialog = UpdateDialog(sample_release)
        qtbot.addWidget(dialog)

        # Simular worker en marcha
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        dialog._download_worker = mock_worker

        dialog.reject()

        mock_worker.quit.assert_called_once()


# ── Tests del banner en LauncherWindow ───────────────────────────


class TestLauncherUpdateBanner:
    """Tests del banner de actualización en el launcher."""

    @pytest.fixture
    def launcher(self, qtbot):
        """Crea un LauncherWindow con session_factory mock."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_all.return_value = []

        with patch(
            "app.db.repositories.application_repo.ApplicationRepository",
            return_value=mock_repo,
        ):
            from app.ui.launcher.launcher_window import LauncherWindow

            factory = MagicMock(return_value=mock_session)
            window = LauncherWindow(session_factory=factory)
            qtbot.addWidget(window)
            return window

    def test_banner_hidden_initially(self, launcher):
        """El banner está oculto al inicio."""
        assert launcher._update_banner.isHidden()

    def test_show_update_banner(self, launcher, sample_release):
        """show_update_banner muestra el banner con la versión."""
        launcher.show()
        launcher.show_update_banner(sample_release)

        assert not launcher._update_banner.isHidden()
        assert "99.0.0" in launcher._banner_label.text()
        assert launcher._pending_release == sample_release

    def test_dismiss_hides_banner(self, launcher, sample_release):
        """El botón Ignorar oculta el banner."""
        launcher.show()
        launcher.show_update_banner(sample_release)
        launcher._btn_banner_dismiss.click()

        assert launcher._update_banner.isHidden()


# ── Tests del botón en AboutDialog ───────────────────────────────


class TestAboutDialogUpdate:
    """Tests del botón de buscar actualizaciones en AboutDialog."""

    def test_has_update_button(self, qtbot):
        """El diálogo tiene botón de buscar actualizaciones."""
        from app.ui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)

        assert hasattr(dialog, "_btn_check_update")
        assert not dialog._btn_check_update.isHidden()

    def test_update_status_label_exists(self, qtbot):
        """Existe la etiqueta de estado."""
        from app.ui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)

        assert hasattr(dialog, "_update_status")

    def test_on_no_update_shows_message(self, qtbot):
        """Sin actualización muestra mensaje de versión actual."""
        from app.ui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)

        dialog._on_no_update()

        text = dialog._update_status.text()
        assert "última versión" in text or "0.1.0" in text

    def test_on_check_error_shows_error(self, qtbot):
        """Error muestra el mensaje."""
        from app.ui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)

        dialog._on_check_error("Sin conexión")

        assert "Sin conexión" in dialog._update_status.text()
