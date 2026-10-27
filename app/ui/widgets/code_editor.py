"""Editor de scripts Python: monoespaciada, colores, números de línea y sangría.

Sustituye al ``QPlainTextEdit`` plano en todos los sitios donde se ve o se
edita un script (eventos, pasos Script, script de nombre de fichero y las
vistas previas de los asistentes). Paridad con el editor de FlexibarNET10:
resaltado de sintaxis, números de línea y fuente monoespaciada.

- La fuente la pone el QSS (``#codeEditor``): ``setFont()`` lo pisaría el tema.
- Los colores salen de la paleta del tema y se recalculan al cambiarlo.
- Tab inserta 4 espacios, Mayús+Tab quita sangría e Intro conserva la de la
  línea (y añade un nivel tras ``:``).
"""

from __future__ import annotations

import keyword
import re

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

INDENT = "    "

_BUILTINS = (
    "print len range str int float bool dict list tuple set any all sorted "
    "enumerate zip min max sum abs round isinstance getattr setattr hasattr "
    "open repr type super Exception ValueError TypeError KeyError RuntimeError"
).split()
# Variables que el motor de scripts inyecta (CLAUDE.md, «Script context»)
_CONTEXT_NAMES = "app batch page pipeline pages documents document result log http re json datetime Path".split()


def _color(key: str) -> QColor:
    from app.ui.palette import color

    return QColor(color(key))


def _fmt(key: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(_color(key))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class PythonHighlighter(QSyntaxHighlighter):
    """Resaltado de Python con los colores del tema activo."""

    # Estados de bloque para las cadenas triples que ocupan varias líneas
    _IN_TRIPLE_SINGLE = 1
    _IN_TRIPLE_DOUBLE = 2

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._build_rules()

    def _build_rules(self) -> None:
        self._keyword = _fmt("mauve", bold=True)
        self._constant = _fmt("peach")
        self._builtin = _fmt("blue")
        self._context = _fmt("orange")
        self._definition = _fmt("blue", bold=True)
        self._decorator = _fmt("yellow")
        self._number = _fmt("peach")
        self._string = _fmt("green")
        self._comment = _fmt("overlay0", italic=True)

        words = [w for w in keyword.kwlist if w not in ("True", "False", "None")]
        self._rules: list[tuple[re.Pattern[str], QTextCharFormat, int]] = [
            (re.compile(r"\b(?:" + "|".join(words) + r")\b"), self._keyword, 0),
            (re.compile(r"\b(?:True|False|None)\b"), self._constant, 0),
            (re.compile(r"\b(?:" + "|".join(_BUILTINS) + r")\b"), self._builtin, 0),
            (
                re.compile(r"\b(?:" + "|".join(_CONTEXT_NAMES) + r")\b"),
                self._context,
                0,
            ),
            (re.compile(r"\b(?:def|class)\s+(\w+)"), self._definition, 1),
            (re.compile(r"^\s*@[\w.]+"), self._decorator, 0),
            (
                re.compile(r"\b0[xX][0-9a-fA-F_]+\b|\b\d[\d_]*(?:\.\d+)?\b"),
                self._number,
                0,
            ),
        ]
        # Cadenas de una línea (con prefijo f/r/b) y comentarios: se tratan
        # aparte para que lo que hay dentro no se coloree como código.
        self._strings_and_comments = re.compile(
            r"""(?P<string>[rRbBfFuU]{0,2}(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'))"""
            r"|(?P<comment>\#.*$)"
        )

    def refresh_theme(self) -> None:
        """Recalcula los colores tras un cambio de tema y repinta."""
        self._build_rules()
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 — API de Qt
        for pattern, fmt, group in self._rules:
            for match in pattern.finditer(text):
                start, end = match.span(group)
                self.setFormat(start, end - start, fmt)

        # Cadenas de una línea y comentarios pisan lo anterior
        protected: list[tuple[int, int]] = []
        for match in self._strings_and_comments.finditer(text):
            start, end = match.span()
            fmt = self._string if match.group("string") else self._comment
            self.setFormat(start, end - start, fmt)
            protected.append((start, end))

        self._highlight_triple_quotes(text, protected)

    def _highlight_triple_quotes(
        self, text: str, protected: list[tuple[int, int]]
    ) -> None:
        """Cadenas triples, incluidas las que siguen en la línea siguiente."""
        self.setCurrentBlockState(0)
        start = 0
        state = self.previousBlockState()
        if state in (self._IN_TRIPLE_SINGLE, self._IN_TRIPLE_DOUBLE):
            delimiter = "'''" if state == self._IN_TRIPLE_SINGLE else '"""'
        else:
            delimiter = None
            found = self._next_triple(text, 0, protected)
            if found is None:
                return
            start, delimiter = found

        while delimiter is not None:
            search_from = start + (0 if state > 0 and start == 0 else 3)
            end = text.find(delimiter, search_from)
            if end == -1:
                self.setFormat(start, len(text) - start, self._string)
                self.setCurrentBlockState(
                    self._IN_TRIPLE_SINGLE
                    if delimiter == "'''"
                    else self._IN_TRIPLE_DOUBLE
                )
                return
            end += 3
            self.setFormat(start, end - start, self._string)
            state = 0
            found = self._next_triple(text, end, protected)
            if found is None:
                return
            start, delimiter = found

    @staticmethod
    def _next_triple(
        text: str, offset: int, protected: list[tuple[int, int]]
    ) -> tuple[int, str] | None:
        """Siguiente apertura de cadena triple fuera de comentarios."""
        candidates = [
            (pos, delim)
            for delim in ('"""', "'''")
            if (pos := text.find(delim, offset)) != -1
        ]
        for pos, delim in sorted(candidates):
            in_comment = any(s <= pos < e and text[s] == "#" for s, e in protected)
            if not in_comment:
                return pos, delim
        return None


class _LineNumberArea(QWidget):
    def __init__(self, editor: CodeEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 — API de Qt
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 — API de Qt
        self._editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """Editor de código Python con resaltado y números de línea."""

    def __init__(
        self, parent: QWidget | None = None, *, read_only: bool = False
    ) -> None:
        super().__init__(parent)
        self.setObjectName("codeEditor")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(read_only)
        self._highlighter = PythonHighlighter(self.document())
        self._numbers = _LineNumberArea(self)

        self.blockCountChanged.connect(self._update_margins)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.textChanged.connect(self._highlight_current_line)
        self._update_margins()
        self._highlight_current_line()

        try:
            from app.ui.theme_manager import ThemeManager

            ThemeManager().theme_changed.connect(self._on_theme_changed)
        except Exception:  # pragma: no cover - sin tema (tests aislados)
            pass

    # ------------------------------------------------------------------
    # Tema y fuente
    # ------------------------------------------------------------------

    def _on_theme_changed(self, _theme: str) -> None:
        self._highlighter.refresh_theme()
        self._highlight_current_line()
        self._numbers.update()

    def changeEvent(self, event) -> None:  # noqa: N802 — API de Qt
        # El QSS fija la fuente después de construir el widget: la tabulación
        # y el margen se recalculan con la fuente real.
        super().changeEvent(event)
        if event.type() == event.Type.FontChange:
            self.setTabStopDistance(
                self.fontMetrics().horizontalAdvance(" ") * len(INDENT)
            )
            self._update_margins()

    # ------------------------------------------------------------------
    # Números de línea
    # ------------------------------------------------------------------

    def line_number_width(self) -> int:
        digits = max(2, len(str(self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margins(self, _count: int = 0) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._numbers.scroll(0, dy)
        else:
            self._numbers.update(0, rect.y(), self._numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margins()

    def resizeEvent(self, event) -> None:  # noqa: N802 — API de Qt
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._numbers.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_width(), cr.height())
        )

    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self._numbers)
        painter.fillRect(event.rect(), _color("bg_alt"))
        painter.setPen(_color("overlay0"))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        width = self._numbers.width() - 6
        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(_color("text" if number == current else "overlay0"))
                painter.drawText(
                    0, top, width, height, Qt.AlignmentFlag.AlignRight, str(number + 1)
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    def _highlight_current_line(self) -> None:
        # Con el documento vacío la franja tapaba la primera línea del texto
        # de ejemplo (placeholder).
        if self.isReadOnly() or not self.document().toPlainText():
            self.setExtraSelections([])
            return
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(_color("hover"))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])
        self._numbers.update()

    # ------------------------------------------------------------------
    # Sangría
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — API de Qt
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Tab and not event.modifiers():
            if self.textCursor().hasSelection():
                self._indent_selection()
            else:
                self.insertPlainText(INDENT)
            return
        if key == Qt.Key.Key_Backtab:
            self._dedent_selection()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers():
            line = self.textCursor().block().text()
            indent = line[: len(line) - len(line.lstrip())]
            if line.rstrip().endswith(":"):
                indent += INDENT
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return
        super().keyPressEvent(event)

    def _selected_blocks(self) -> tuple[QTextCursor, int, int]:
        cursor = self.textCursor()
        doc = self.document()
        first = doc.findBlock(cursor.selectionStart()).blockNumber()
        last = doc.findBlock(cursor.selectionEnd()).blockNumber()
        return cursor, first, last

    def _indent_selection(self) -> None:
        cursor, first, last = self._selected_blocks()
        cursor.beginEditBlock()
        for number in range(first, last + 1):
            block = self.document().findBlockByNumber(number)
            c = QTextCursor(block)
            c.insertText(INDENT)
        cursor.endEditBlock()

    def _dedent_selection(self) -> None:
        cursor, first, last = self._selected_blocks()
        cursor.beginEditBlock()
        for number in range(first, last + 1):
            block = self.document().findBlockByNumber(number)
            text = block.text()
            remove = len(text) - len(text.lstrip(" "))
            remove = min(remove, len(INDENT))
            if remove:
                c = QTextCursor(block)
                c.movePosition(
                    QTextCursor.MoveOperation.Right,
                    QTextCursor.MoveMode.KeepAnchor,
                    remove,
                )
                c.removeSelectedText()
        cursor.endEditBlock()
