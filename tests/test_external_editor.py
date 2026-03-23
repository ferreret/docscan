"""Tests del servicio de editor externo y generador de stubs."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.services.script_stubs import (
    STUB_DELIMITER,
    generate_stubs,
    strip_stubs,
)
from app.services.external_editor_service import detect_editor, edit_script


# ==================================================================
# Tests de script_stubs
# ==================================================================


class TestGenerateStubs:
    """Generación de bloques de stubs para distintos contextos."""

    def test_pipeline_stubs_contain_all_contexts(self) -> None:
        result = generate_stubs("pipeline")
        assert "pipeline: PipelineContext" in result
        assert "page: PageContext" in result
        assert "app: AppContext" in result
        assert "batch: BatchContext" in result

    def test_event_stubs_without_page(self) -> None:
        result = generate_stubs("event", "on_app_start")
        assert "app: AppContext" in result
        assert "batch: BatchContext" in result
        assert "page: PageContext" not in result

    def test_event_stubs_with_page(self) -> None:
        result = generate_stubs("event", "on_scan_complete")
        assert "page: PageContext" in result

    def test_stubs_delimited(self) -> None:
        result = generate_stubs("pipeline")
        lines = result.split("\n")
        assert lines[0] == STUB_DELIMITER
        assert STUB_DELIMITER in lines[-2]  # penúltima línea

    def test_builtins_listed(self) -> None:
        result = generate_stubs("pipeline")
        assert "log" in result
        assert "Path" in result


class TestStripStubs:
    """Eliminación de bloques de stubs."""

    def test_strip_removes_stub_block(self) -> None:
        code = (
            f"{STUB_DELIMITER}\n# Stubs aquí\n{STUB_DELIMITER}\n"
            "def run():\n    pass\n"
        )
        result = strip_stubs(code)
        assert STUB_DELIMITER not in result
        assert "def run():" in result

    def test_strip_preserves_code_without_stubs(self) -> None:
        code = "def hello():\n    return 42\n"
        assert strip_stubs(code) == code

    def test_strip_handles_empty_string(self) -> None:
        assert strip_stubs("") == ""

    def test_roundtrip(self) -> None:
        original = "def process(app, batch, page, pipeline):\n    pass\n"
        stubs = generate_stubs("pipeline")
        combined = stubs + original
        restored = strip_stubs(combined)
        assert restored.strip() == original.strip()


# ==================================================================
# Tests de external_editor_service
# ==================================================================


class TestDetectEditor:
    """Detección de VS Code."""

    def test_detect_when_available(self) -> None:
        with patch("app.services.external_editor_service.shutil.which") as mock:
            mock.return_value = "/usr/bin/code"
            assert detect_editor() == "/usr/bin/code"

    def test_detect_when_not_available(self) -> None:
        with patch("app.services.external_editor_service.shutil.which") as mock:
            mock.return_value = None
            assert detect_editor() is None


class TestEditScript:
    """Edición bloqueante con VS Code."""

    def test_returns_none_when_no_editor(self) -> None:
        with patch("app.services.external_editor_service.detect_editor", return_value=None):
            result = edit_script("code here")
            assert result is None

    def test_returns_modified_code(self, tmp_path) -> None:
        modified = "def run():\n    return 42\n"

        def fake_run(cmd, check=False):
            # Simular que VS Code modifica el archivo
            path = cmd[2]  # ["code", "--wait", path]
            from pathlib import Path
            p = Path(path)
            content = p.read_text(encoding="utf-8")
            # Reemplazar todo con código nuevo (sin stubs)
            p.write_text(
                f"{STUB_DELIMITER}\n# stubs\n{STUB_DELIMITER}\n{modified}",
                encoding="utf-8",
            )
            return MagicMock(returncode=0)

        with (
            patch("app.services.external_editor_service.detect_editor", return_value="/usr/bin/code"),
            patch("app.services.external_editor_service.subprocess.run", side_effect=fake_run),
            patch("app.services.external_editor_service._SCRIPTS_TMP_DIR", tmp_path),
        ):
            result = edit_script("original code", "pipeline")

        assert result is not None
        assert "def run():" in result
        assert STUB_DELIMITER not in result

    def test_returns_none_on_nonzero_exit(self, tmp_path) -> None:
        with (
            patch("app.services.external_editor_service.detect_editor", return_value="/usr/bin/code"),
            patch("app.services.external_editor_service.subprocess.run", return_value=MagicMock(returncode=1)),
            patch("app.services.external_editor_service._SCRIPTS_TMP_DIR", tmp_path),
        ):
            result = edit_script("code", "pipeline")
            assert result is None
