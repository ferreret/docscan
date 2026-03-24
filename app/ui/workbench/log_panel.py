"""Panel de logs en tiempo real para el Workbench.

Muestra mensajes de logging de la aplicación (pipeline, scripts, eventos)
en un QPlainTextEdit de solo lectura. Usa un logging.Handler personalizado
que emite señales Qt para thread-safety.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QLabel,
)

log = logging.getLogger(__name__)

# Colores por nivel de log (texto)
_LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: "#888888",
    logging.INFO: "#d4d4d4",
    logging.WARNING: "#e5c07b",
    logging.ERROR: "#e06c75",
    logging.CRITICAL: "#ff4444",
}

_MAX_LOG_LINES = 5000


class _LogSignalBridge(QObject):
    """Bridge thread-safe: el Handler emite esta señal desde cualquier hilo."""

    log_record = Signal(str, int)  # (mensaje formateado, nivel)


class QtLogHandler(logging.Handler):
    """Handler de logging que emite señales Qt por cada registro.

    Thread-safe: puede recibir logs desde QThreads del pipeline.
    """

    def __init__(self, bridge: _LogSignalBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._bridge.log_record.emit(msg, record.levelno)
        except Exception:
            self.handleError(record)


class LogPanel(QWidget):
    """Panel de logs con filtrado por nivel y auto-scroll."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._min_level = logging.DEBUG
        self._build_ui()
        self._setup_handler()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Barra de herramientas
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)

        title = QLabel(self.tr("Log"))
        title.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(title)

        toolbar.addStretch()

        # Filtro de nivel
        toolbar.addWidget(QLabel(self.tr("Nivel:")))
        self._level_combo = QComboBox()
        self._level_combo.addItem("DEBUG", logging.DEBUG)
        self._level_combo.addItem("INFO", logging.INFO)
        self._level_combo.addItem("WARNING", logging.WARNING)
        self._level_combo.addItem("ERROR", logging.ERROR)
        self._level_combo.setCurrentIndex(1)  # INFO por defecto
        self._min_level = logging.INFO
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        toolbar.addWidget(self._level_combo)

        # Botón limpiar
        btn_clear = QPushButton(self.tr("Limpiar"))
        btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self._on_clear)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        # Área de texto
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(_MAX_LOG_LINES)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self._text.setFont(font)
        self._text.setObjectName("logTextArea")
        layout.addWidget(self._text)

    # ------------------------------------------------------------------
    # Logging handler
    # ------------------------------------------------------------------

    def _setup_handler(self) -> None:
        """Instala el handler en el logger raíz para capturar todo."""
        self._bridge = _LogSignalBridge(self)
        self._bridge.log_record.connect(
            self._append_log, Qt.ConnectionType.QueuedConnection
        )

        self._handler = QtLogHandler(self._bridge)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
                              datefmt="%H:%M:%S")
        )
        logging.getLogger().addHandler(self._handler)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _append_log(self, message: str, level: int) -> None:
        """Añade un mensaje al panel si supera el nivel mínimo."""
        if level < self._min_level:
            return

        color = _LEVEL_COLORS.get(level, "#d4d4d4")

        # Insertar con color
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(message + "\n", fmt)

        # Auto-scroll al final
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def _on_level_changed(self, index: int) -> None:
        self._min_level = self._level_combo.currentData()

    def _on_clear(self) -> None:
        self._text.clear()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Desinstala el handler de logging."""
        logging.getLogger().removeHandler(self._handler)
