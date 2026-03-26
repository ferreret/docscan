"""Diálogo de actualización de DocScan Studio.

Muestra las notas de la release, barra de progreso de descarga
y botones para verificar/aplicar o cancelar.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app._version import __version__ as _CURRENT_VERSION
from app.services.update_service import ReleaseInfo, UpdateService
from app.workers.update_worker import UpdateDownloadWorker

log = logging.getLogger(__name__)


class UpdateDialog(QDialog):
    """Diálogo modal para descargar y aplicar una actualización.

    Muestra la información de la nueva versión, permite descargar
    con barra de progreso y aplicar la actualización.
    """

    def __init__(
        self,
        release: ReleaseInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._release = release
        self._download_worker: UpdateDownloadWorker | None = None
        self._downloaded_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(self.tr("Actualización disponible"))
        self.setMinimumSize(520, 420)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Cabecera: versión actual → nueva
        header = QLabel(
            self.tr("Nueva versión: <b>{0}</b>  (actual: {1})").format(
                self._release.version, _CURRENT_VERSION,
            )
        )
        header.setProperty("cssClass", "update-header")
        layout.addWidget(header)

        # Notas de la release
        notes_label = QLabel(self.tr("Novedades:"))
        notes_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(notes_label)

        self._notes_browser = QTextBrowser()
        self._notes_browser.setOpenExternalLinks(True)
        if self._release.release_notes:
            self._notes_browser.setMarkdown(self._release.release_notes)
        else:
            self._notes_browser.setPlainText(
                self.tr("No hay notas de la versión disponibles.")
            )
        layout.addWidget(self._notes_browser, stretch=1)

        # Tamaño del fichero
        size_mb = self._release.asset_size / (1024 * 1024)
        size_text = self.tr("Tamaño: {0:.1f} MB").format(size_mb)
        if self._release.sha256:
            size_text += self.tr("  •  Verificación SHA-256 incluida")
        self._size_label = QLabel(size_text)
        self._size_label.setStyleSheet("color: #888; font-size: 10pt;")
        layout.addWidget(self._size_label)

        # Barra de progreso (oculta inicialmente)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat(self.tr("Descargando... %p%"))
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # Etiqueta de estado
        self._status_label = QLabel("")
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_download = QPushButton(self.tr("Descargar y actualizar"))
        self._btn_download.setDefault(True)
        self._btn_download.clicked.connect(self._on_download)
        btn_layout.addWidget(self._btn_download)

        self._btn_apply = QPushButton(self.tr("Aplicar actualización"))
        self._btn_apply.setVisible(False)
        self._btn_apply.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._btn_apply)

        self._btn_cancel = QPushButton(self.tr("Cancelar"))
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Descarga
    # ------------------------------------------------------------------

    @Slot()
    def _on_download(self) -> None:
        """Inicia la descarga del instalador."""
        self._btn_download.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setVisible(True)
        self._status_label.setText(self.tr("Iniciando descarga..."))

        dest_dir = Path(tempfile.gettempdir()) / "docscan_updates"
        self._download_worker = UpdateDownloadWorker(
            self._release, dest_dir, parent=self,
        )
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.download_finished.connect(self._on_download_finished)
        self._download_worker.download_error.connect(self._on_download_error)
        self._download_worker.start()

    @Slot(int, int)
    def _on_progress(self, downloaded: int, total: int) -> None:
        """Actualiza la barra de progreso."""
        if total > 0:
            pct = int(downloaded * 100 / total)
            self._progress_bar.setValue(pct)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self._status_label.setText(
                self.tr("{0:.1f} / {1:.1f} MB").format(mb_done, mb_total)
            )
        else:
            self._progress_bar.setRange(0, 0)  # Indeterminado
            mb_done = downloaded / (1024 * 1024)
            self._status_label.setText(
                self.tr("{0:.1f} MB descargados").format(mb_done)
            )

    @Slot(str)
    def _on_download_finished(self, path_str: str) -> None:
        """Descarga completada y verificada."""
        self._downloaded_path = Path(path_str)
        self._progress_bar.setValue(100)
        self._progress_bar.setFormat(self.tr("Descarga completada"))

        checksum_msg = ""
        if self._release.sha256:
            checksum_msg = self.tr("  •  Checksum SHA-256 verificado")

        self._status_label.setText(
            self.tr("Descarga completada correctamente.{0}").format(checksum_msg)
        )
        self._status_label.setStyleSheet("color: green; font-weight: bold;")

        self._btn_download.setVisible(False)
        self._btn_apply.setVisible(True)
        self._btn_cancel.setText(self.tr("Cerrar"))

    @Slot(str)
    def _on_download_error(self, error: str) -> None:
        """Error en la descarga."""
        self._progress_bar.setVisible(False)
        self._status_label.setText(self.tr("Error: {0}").format(error))
        self._status_label.setStyleSheet("color: red;")
        self._btn_download.setEnabled(True)
        self._btn_download.setText(self.tr("Reintentar"))

    # ------------------------------------------------------------------
    # Aplicar
    # ------------------------------------------------------------------

    @Slot()
    def _on_apply(self) -> None:
        """Aplica la actualización descargada."""
        if self._downloaded_path is None:
            return

        self._status_label.setText(self.tr("Aplicando actualización..."))
        self._btn_apply.setEnabled(False)

        try:
            UpdateService.apply_update(self._downloaded_path)
            self._status_label.setText(
                self.tr("Actualización aplicada. Reinicie la aplicación.")
            )
            self._btn_cancel.setText(self.tr("Cerrar"))
        except Exception as e:
            log.error("Error aplicando actualización: %s", e)
            self._status_label.setText(
                self.tr("Error al aplicar: {0}").format(e)
            )
            self._status_label.setStyleSheet("color: red;")
            self._btn_apply.setEnabled(True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def reject(self) -> None:
        """Cancela la descarga si está en curso."""
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.quit()
            self._download_worker.wait(3000)
        super().reject()
