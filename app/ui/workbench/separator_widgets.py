"""Widgets del separador de documento en el Workbench (paridad FlexibarNET10).

- ``SeparatorValueDialog``: pide el valor al marcar una página como
  separador o al editarlo, y lo valida en vivo contra
  ``separator_manual_regex``.
- ``SeparatorZone``: tarjeta con borde naranja en el panel derecho, visible
  solo si la página del visor es separador, con el valor y «Editar valor».

La lógica (sugerencia y validación) vive en ``app.pipeline.separator``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.pipeline import separator


class SeparatorValueDialog(QDialog):
    """Diálogo del valor del separador, con validación en vivo.

    Un valor vacío se admite (separador sin valor), como en Flexibar.
    """

    def __init__(
        self,
        value: str,
        step: Any | None,
        *,
        editing: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step
        self.setWindowTitle(
            self.tr("Editar separador")
            if editing
            else self.tr("Marcar separador de documento")
        )
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(self.tr("Valor del separador (puede quedar en blanco):"))
        )
        self._edit = QLineEdit(value)
        self._edit.setObjectName("separatorValueEdit")
        self._edit.selectAll()
        layout.addWidget(self._edit)

        self._lbl_error = QLabel()
        self._lbl_error.setObjectName("separatorValueError")
        self._lbl_error.setWordWrap(True)
        layout.addWidget(self._lbl_error)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._edit.textChanged.connect(self._validate)
        self._validate(self._edit.text())

    def _validate(self, text: str) -> None:
        error = separator.manual_value_error(self._step, text.strip())
        self._lbl_error.setText(error or "")
        self._lbl_error.setVisible(bool(error))
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            error is None
        )

    def value(self) -> str:
        """Valor introducido, sin espacios en los extremos."""
        return self._edit.text().strip()


class SeparatorZone(QFrame):
    """Zona «Separador de documento» del panel derecho.

    Signals:
        edit_requested: El operador quiere cambiar el valor.
    """

    edit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("separatorZone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._lbl_title = QLabel()
        self._lbl_title.setObjectName("sectionTitle")
        layout.addWidget(self._lbl_title)

        row = QHBoxLayout()
        self._lbl_value = QLabel()
        self._lbl_value.setObjectName("separatorValue")
        row.addWidget(self._lbl_value, stretch=1)
        self._btn_edit = QPushButton(self.tr("Editar valor"))
        self._btn_edit.clicked.connect(self.edit_requested)
        row.addWidget(self._btn_edit)
        layout.addLayout(row)

        self.setVisible(False)

    def show_separator(self, value: str, document_index: int, pages: int) -> None:
        """Muestra la zona para una página separadora."""
        self._lbl_title.setText(
            self.tr("SEPARADOR DE DOCUMENTO · DOC {0} · {1} PÁG.").format(
                document_index, pages
            )
        )
        self._lbl_value.setText(value or self.tr("(sin valor)"))
        self.setVisible(True)
