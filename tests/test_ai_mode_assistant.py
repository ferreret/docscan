"""Tests para AiModeAssistantService — asistente IA unificado."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_mode_assistant import (
    AiModeAssistantService,
    AiModeResponse,
    AiModeToolCall,
    TOOLS,
    _build_system_prompt,
    _classify_error,
    _process_tool_input,
    validate_pipeline,
)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def anthropic_service():
    return AiModeAssistantService("anthropic", "test-key", "claude-test")


@pytest.fixture
def openai_service():
    return AiModeAssistantService("openai", "test-key", "gpt-test")


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _anthropic_tool_response(*tool_uses):
    """Simula respuesta Anthropic con N tool_use blocks."""
    blocks = []
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "OK"
    blocks.append(text_block)

    for name, input_data in tool_uses:
        tb = MagicMock()
        tb.type = "tool_use"
        tb.name = name
        tb.input = input_data
        blocks.append(tb)

    response = MagicMock()
    response.content = blocks
    return response


def _openai_tool_response(*tool_uses):
    """Simula respuesta OpenAI con N tool_calls."""
    tool_calls = []
    for name, input_data in tool_uses:
        tc = MagicMock()
        tc.function.name = name
        tc.function.arguments = json.dumps(input_data)
        tool_calls.append(tc)

    msg = MagicMock()
    msg.content = "OK"
    msg.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = msg

    response = MagicMock()
    response.choices = [choice]
    return response


def _text_response_anthropic(text):
    tb = MagicMock()
    tb.type = "text"
    tb.text = text
    response = MagicMock()
    response.content = [tb]
    return response


# ---------------------------------------------------------------
# Tests de inicializacion
# ---------------------------------------------------------------

class TestInit:
    def test_invalid_provider(self):
        with pytest.raises(ValueError, match="no soportado"):
            AiModeAssistantService("gemini", "key")

    def test_default_models(self):
        svc_a = AiModeAssistantService("anthropic", "key")
        svc_o = AiModeAssistantService("openai", "key")
        assert "claude" in svc_a._model
        assert "gpt" in svc_o._model


# ---------------------------------------------------------------
# Tests de create_application — Anthropic
# ---------------------------------------------------------------

class TestCreateApplication:
    def test_creates_app_with_pipeline(self, anthropic_service):
        tool_input = {
            "name": "Facturas",
            "description": "App para escanear facturas",
            "pipeline": [
                {"type": "image_op", "op": "AutoDeskew"},
                {"type": "barcode", "engine": "motor1", "symbologies": ["Code128"]},
                {"type": "ocr", "engine": "rapidocr", "languages": ["es"]},
            ],
            "events": {
                "on_transfer_validate": (
                    "def on_transfer_validate(app, batch) -> bool:\n"
                    "    return True\n"
                ),
            },
            "batch_fields": [
                {"label": "Referencia", "type": "texto", "required": True},
            ],
            "explanation": "App de facturas con pipeline basico.",
        }
        mock_resp = _anthropic_tool_response(("create_application", tool_input))

        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.return_value = mock_resp
            result = anthropic_service.generate(
                [{"role": "user", "content": "Crea app facturas"}],
                "No applications yet.",
            )

        assert result.error is None
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.tool_name == "create_application"
        assert tc.tool_input["name"] == "Facturas"
        assert len(tc.tool_input["pipeline"]) == 3
        # Verificar que se asignaron IDs
        for step in tc.tool_input["pipeline"]:
            assert step["id"].startswith("step_")

    def test_creates_app_with_script(self, anthropic_service):
        tool_input = {
            "name": "Test",
            "pipeline": [
                {
                    "type": "script",
                    "label": "Clasificar",
                    "entry_point": "process",
                    "script": "def process(app, batch, page, pipeline):\n    pass\n",
                },
            ],
            "explanation": "test",
        }
        mock_resp = _anthropic_tool_response(("create_application", tool_input))

        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.return_value = mock_resp
            result = anthropic_service.generate(
                [{"role": "user", "content": "test"}], "",
            )

        assert result.tool_calls[0].tool_input["pipeline"][0]["script"]


# ---------------------------------------------------------------
# Tests de update_application
# ---------------------------------------------------------------

class TestUpdateApplication:
    def test_partial_update(self, anthropic_service):
        tool_input = {
            "app_name": "Facturas",
            "pipeline": [
                {"type": "image_op", "op": "AutoDeskew"},
                {"type": "image_op", "op": "RemoveLines", "params": {"direction": "HV"}},
            ],
            "explanation": "Anade RemoveLines.",
        }
        mock_resp = _anthropic_tool_response(("update_application", tool_input))

        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.return_value = mock_resp
            result = anthropic_service.generate(
                [{"role": "user", "content": "Anade RemoveLines a Facturas"}], "",
            )

        tc = result.tool_calls[0]
        assert tc.tool_name == "update_application"
        assert tc.tool_input["app_name"] == "Facturas"
        assert len(tc.tool_input["pipeline"]) == 2


# ---------------------------------------------------------------
# Tests de duplicate_application
# ---------------------------------------------------------------

class TestDuplicateApplication:
    def test_duplicate_with_mods(self, openai_service):
        tool_input = {
            "source_app_name": "Facturas",
            "new_name": "Albaranes",
            "pipeline": [
                {"type": "image_op", "op": "AutoDeskew"},
                {"type": "ocr", "engine": "rapidocr", "languages": ["ca"]},
            ],
            "explanation": "Clon de Facturas con OCR catalan.",
        }
        mock_resp = _openai_tool_response(("duplicate_application", tool_input))

        with patch.object(openai_service, "_get_client") as mc:
            mc.return_value.chat.completions.create.return_value = mock_resp
            result = openai_service.generate(
                [{"role": "user", "content": "Duplica Facturas como Albaranes con OCR catalan"}],
                "",
            )

        tc = result.tool_calls[0]
        assert tc.tool_name == "duplicate_application"
        assert tc.tool_input["source_app_name"] == "Facturas"
        assert tc.tool_input["new_name"] == "Albaranes"


# ---------------------------------------------------------------
# Tests de delete_application
# ---------------------------------------------------------------

class TestDeleteApplication:
    def test_delete(self, anthropic_service):
        tool_input = {
            "app_name": "Albaranes",
            "explanation": "Eliminada por peticion del usuario.",
        }
        mock_resp = _anthropic_tool_response(("delete_application", tool_input))

        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.return_value = mock_resp
            result = anthropic_service.generate(
                [{"role": "user", "content": "Elimina Albaranes"}], "",
            )

        tc = result.tool_calls[0]
        assert tc.tool_name == "delete_application"
        assert tc.tool_input["app_name"] == "Albaranes"


# ---------------------------------------------------------------
# Tests de set_event_code
# ---------------------------------------------------------------

class TestSetEventCode:
    def test_set_event(self, anthropic_service):
        tool_input = {
            "app_name": "Facturas",
            "event_name": "on_transfer_validate",
            "code": "def on_transfer_validate(app, batch) -> bool:\n    return True\n",
            "explanation": "Validacion basica.",
        }
        mock_resp = _anthropic_tool_response(("set_event_code", tool_input))

        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.return_value = mock_resp
            result = anthropic_service.generate(
                [{"role": "user", "content": "Anade validacion a Facturas"}], "",
            )

        tc = result.tool_calls[0]
        assert tc.tool_name == "set_event_code"
        assert tc.tool_input["event_name"] == "on_transfer_validate"
        assert "on_transfer_validate" in tc.tool_input["code"]


# ---------------------------------------------------------------
# Tests de multi-tool
# ---------------------------------------------------------------

class TestMultiTool:
    def test_multiple_tool_calls(self, anthropic_service):
        """El modelo puede llamar multiples tools en una respuesta."""
        mock_resp = _anthropic_tool_response(
            ("create_application", {
                "name": "App1", "explanation": "Primera.",
            }),
            ("create_application", {
                "name": "App2", "explanation": "Segunda.",
            }),
        )

        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.return_value = mock_resp
            result = anthropic_service.generate(
                [{"role": "user", "content": "Crea App1 y App2"}], "",
            )

        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].tool_input["name"] == "App1"
        assert result.tool_calls[1].tool_input["name"] == "App2"


# ---------------------------------------------------------------
# Tests de text-only response
# ---------------------------------------------------------------

class TestTextResponse:
    def test_text_only(self, anthropic_service):
        mock_resp = _text_response_anthropic("Necesito mas detalles.")

        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.return_value = mock_resp
            result = anthropic_service.generate(
                [{"role": "user", "content": "hola"}], "",
            )

        assert len(result.tool_calls) == 0
        assert "Necesito mas detalles" in result.text


# ---------------------------------------------------------------
# Tests de system prompt
# ---------------------------------------------------------------

class TestSystemPrompt:
    def test_includes_all_sections(self):
        prompt = _build_system_prompt("[]")
        assert "AI MODE" in prompt
        assert "AutoDeskew" in prompt
        assert "page.barcodes" in prompt
        assert "on_transfer_validate" in prompt
        assert "batch_fields" in prompt or "texto" in prompt
        assert "image_config" in prompt or "tiff" in prompt

    def test_includes_apps_summary(self):
        summary = '[{"name": "TestApp", "active": true}]'
        prompt = _build_system_prompt(summary)
        assert "TestApp" in prompt


# ---------------------------------------------------------------
# Tests de utilidades
# ---------------------------------------------------------------

class TestUtilities:
    def test_process_tool_input_assigns_ids(self):
        ti = {"pipeline": [{"type": "image_op", "op": "AutoDeskew"}]}
        result = _process_tool_input("create_application", ti)
        assert result["pipeline"][0]["id"].startswith("step_")

    def test_process_tool_input_preserves_existing_ids(self):
        ti = {"pipeline": [{"type": "image_op", "op": "AutoDeskew", "id": "my_id"}]}
        result = _process_tool_input("create_application", ti)
        assert result["pipeline"][0]["id"] == "my_id"

    def test_validate_pipeline_valid(self):
        steps = [
            {"id": "s1", "type": "image_op", "op": "AutoDeskew"},
            {"id": "s2", "type": "ocr", "engine": "rapidocr", "languages": ["es"]},
        ]
        assert validate_pipeline(steps) is None

    def test_validate_pipeline_invalid(self):
        steps = [{"id": "s1", "type": "invalid_type"}]
        error = validate_pipeline(steps)
        assert error is not None


# ---------------------------------------------------------------
# Tests de tool schemas
# ---------------------------------------------------------------

class TestToolSchemas:
    def test_all_tools_have_name_and_schema(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "input_schema" in tool
            assert "description" in tool

    def test_tool_names(self):
        names = {t["name"] for t in TOOLS}
        assert names == {
            "list_applications",
            "get_application",
            "create_application",
            "update_application",
            "duplicate_application",
            "delete_application",
            "set_event_code",
        }

    def test_create_requires_name_and_explanation(self):
        create = next(t for t in TOOLS if t["name"] == "create_application")
        assert "name" in create["input_schema"]["required"]
        assert "explanation" in create["input_schema"]["required"]


# ---------------------------------------------------------------
# Tests de errores
# ---------------------------------------------------------------

class TestErrors:
    def test_api_error(self, anthropic_service):
        with patch.object(anthropic_service, "_get_client") as mc:
            mc.return_value.messages.create.side_effect = Exception("401 Unauthorized")
            result = anthropic_service.generate(
                [{"role": "user", "content": "test"}], "",
            )
        assert result.error is not None
        assert "API key" in result.error

    def test_classify_errors(self):
        assert "API key" in _classify_error(Exception("401"))
        assert "peticiones" in _classify_error(Exception("429")).lower()
        assert "conexion" in _classify_error(Exception("Connection refused")).lower()
