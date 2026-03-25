"""Tests para PipelineAssistantService — asistente IA de pipelines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.pipeline_assistant import (
    AssistantResponse,
    PipelineAssistantService,
    _classify_error,
    _IMAGE_OPS_REFERENCE,
    _SCRIPT_API_REFERENCE,
    _SET_PIPELINE_TOOL,
    _SET_EVENT_CODE_TOOL,
)
from app.pipeline.steps import (
    BarcodeStep,
    ImageOpStep,
    OcrStep,
    ScriptStep,
)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def anthropic_service():
    """Servicio configurado con proveedor Anthropic."""
    return PipelineAssistantService(
        provider="anthropic",
        api_key="test-key-anthropic",
        model="claude-test",
    )


@pytest.fixture
def openai_service():
    """Servicio configurado con proveedor OpenAI."""
    return PipelineAssistantService(
        provider="openai",
        api_key="test-key-openai",
        model="gpt-test",
    )


# ---------------------------------------------------------------
# Helpers para simular respuestas de APIs
# ---------------------------------------------------------------

def _make_anthropic_tool_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Simula una respuesta de Anthropic con tool_use."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Explanation text"

    response = MagicMock()
    response.content = [text_block, tool_block]
    return response


def _make_anthropic_text_response(text: str) -> MagicMock:
    """Simula una respuesta de Anthropic solo texto."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    response = MagicMock()
    response.content = [text_block]
    return response


def _make_openai_tool_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Simula una respuesta de OpenAI con tool_calls."""
    tool_call = MagicMock()
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(tool_input)

    message = MagicMock()
    message.content = "Explanation text"
    message.tool_calls = [tool_call]

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def _make_openai_text_response(text: str) -> MagicMock:
    """Simula una respuesta de OpenAI solo texto."""
    message = MagicMock()
    message.content = text
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------
# Tests de inicializacion
# ---------------------------------------------------------------

class TestServiceInit:
    """Tests de inicializacion del servicio."""

    def test_anthropic_defaults(self):
        svc = PipelineAssistantService(provider="anthropic", api_key="key")
        assert svc._provider == "anthropic"
        assert "claude" in svc._model

    def test_openai_defaults(self):
        svc = PipelineAssistantService(provider="openai", api_key="key")
        assert svc._provider == "openai"
        assert "gpt" in svc._model

    def test_invalid_provider(self):
        with pytest.raises(ValueError, match="no soportado"):
            PipelineAssistantService(provider="gemini", api_key="key")

    def test_custom_model(self):
        svc = PipelineAssistantService(
            provider="anthropic", api_key="key", model="custom-model"
        )
        assert svc._model == "custom-model"


# ---------------------------------------------------------------
# Tests de generacion de pipeline — Anthropic
# ---------------------------------------------------------------

class TestPipelineGenerationAnthropic:
    """Tests de generacion de pipeline con Anthropic."""

    def test_generates_simple_pipeline(self, anthropic_service):
        """El servicio genera un pipeline valido desde tool_use."""
        tool_input = {
            "steps": [
                {"type": "image_op", "op": "AutoDeskew", "params": {}},
                {
                    "type": "barcode",
                    "engine": "motor1",
                    "symbologies": ["Code128"],
                },
                {"type": "ocr", "engine": "rapidocr", "languages": ["es"]},
            ],
            "explanation": "Pipeline basico: deskew, barcode, OCR.",
        }
        mock_response = _make_anthropic_tool_response("set_pipeline", tool_input)

        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = anthropic_service.generate_pipeline(
                messages=[{"role": "user", "content": "Deskew, Code128, OCR espanol"}],
                current_pipeline_json="[]",
            )

        assert result.error is None
        assert result.steps is not None
        assert len(result.steps) == 3
        assert isinstance(result.steps[0], ImageOpStep)
        assert result.steps[0].op == "AutoDeskew"
        assert isinstance(result.steps[1], BarcodeStep)
        assert result.steps[1].symbologies == ["Code128"]
        assert isinstance(result.steps[2], OcrStep)
        assert result.steps[2].languages == ["es"]
        assert result.explanation == "Pipeline basico: deskew, barcode, OCR."

    def test_generates_pipeline_with_script(self, anthropic_service):
        """El servicio genera ScriptStep con codigo Python."""
        script_code = (
            "def process(app, batch, page, pipeline):\n"
            "    for bc in page.barcodes:\n"
            "        if bc.value.startswith('SEP'):\n"
            "            page.fields['separator'] = bc.value\n"
        )
        tool_input = {
            "steps": [
                {
                    "type": "script",
                    "label": "Clasificar barcodes",
                    "entry_point": "process",
                    "script": script_code,
                },
            ],
            "explanation": "Script para clasificar barcodes.",
        }
        mock_response = _make_anthropic_tool_response("set_pipeline", tool_input)

        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = anthropic_service.generate_pipeline(
                messages=[{"role": "user", "content": "Clasificar barcodes"}],
                current_pipeline_json="[]",
            )

        assert result.error is None
        assert result.steps is not None
        assert len(result.steps) == 1
        step = result.steps[0]
        assert isinstance(step, ScriptStep)
        assert step.label == "Clasificar barcodes"
        assert "page.barcodes" in step.script

    def test_text_only_response(self, anthropic_service):
        """Si el modelo no usa tool, devuelve solo texto."""
        mock_response = _make_anthropic_text_response(
            "No entiendo, puedes ser mas especifico?"
        )

        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = anthropic_service.generate_pipeline(
                messages=[{"role": "user", "content": "hola"}],
                current_pipeline_json="[]",
            )

        assert result.steps is None
        assert result.error is None
        assert "No entiendo" in result.text

    def test_assigns_unique_ids(self, anthropic_service):
        """Cada paso recibe un id unico."""
        tool_input = {
            "steps": [
                {"type": "image_op", "op": "AutoDeskew"},
                {"type": "image_op", "op": "FxGrayscale"},
            ],
            "explanation": "Dos pasos de imagen.",
        }
        mock_response = _make_anthropic_tool_response("set_pipeline", tool_input)

        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = anthropic_service.generate_pipeline(
                messages=[{"role": "user", "content": "deskew y grayscale"}],
                current_pipeline_json="[]",
            )

        assert result.steps is not None
        ids = [s.id for s in result.steps]
        assert len(set(ids)) == 2  # IDs unicos
        assert all(id_.startswith("step_") for id_ in ids)

    def test_invalid_pipeline_returns_error(self, anthropic_service):
        """Si el pipeline generado es invalido, devuelve error."""
        tool_input = {
            "steps": [{"type": "invalid_type"}],
            "explanation": "Test.",
        }
        mock_response = _make_anthropic_tool_response("set_pipeline", tool_input)

        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = anthropic_service.generate_pipeline(
                messages=[{"role": "user", "content": "test"}],
                current_pipeline_json="[]",
            )

        assert result.error is not None
        assert "invalido" in result.error


# ---------------------------------------------------------------
# Tests de generacion de pipeline — OpenAI
# ---------------------------------------------------------------

class TestPipelineGenerationOpenAI:
    """Tests de generacion de pipeline con OpenAI."""

    def test_generates_pipeline(self, openai_service):
        """El servicio genera un pipeline valido desde tool_calls."""
        tool_input = {
            "steps": [
                {"type": "image_op", "op": "AutoDeskew", "params": {}},
                {"type": "ocr", "engine": "rapidocr", "languages": ["es", "en"]},
            ],
            "explanation": "Deskew y OCR.",
        }
        mock_response = _make_openai_tool_response("set_pipeline", tool_input)

        with patch.object(openai_service, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = (
                mock_response
            )
            result = openai_service.generate_pipeline(
                messages=[{"role": "user", "content": "Deskew y OCR bilingue"}],
                current_pipeline_json="[]",
            )

        assert result.error is None
        assert result.steps is not None
        assert len(result.steps) == 2
        assert isinstance(result.steps[1], OcrStep)
        assert result.steps[1].languages == ["es", "en"]

    def test_text_only_response(self, openai_service):
        """Si OpenAI no usa tool, devuelve solo texto."""
        mock_response = _make_openai_text_response("Necesito mas detalles.")

        with patch.object(openai_service, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = (
                mock_response
            )
            result = openai_service.generate_pipeline(
                messages=[{"role": "user", "content": "?"}],
                current_pipeline_json="[]",
            )

        assert result.steps is None
        assert "Necesito mas detalles" in result.text

    def test_invalid_json_arguments(self, openai_service):
        """Si OpenAI devuelve JSON invalido en arguments, devuelve error."""
        tool_call = MagicMock()
        tool_call.function.name = "set_pipeline"
        tool_call.function.arguments = "{invalid json"

        message = MagicMock()
        message.content = ""
        message.tool_calls = [tool_call]

        choice = MagicMock()
        choice.message = message

        response = MagicMock()
        response.choices = [choice]

        with patch.object(openai_service, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = response
            result = openai_service.generate_pipeline(
                messages=[{"role": "user", "content": "test"}],
                current_pipeline_json="[]",
            )

        assert result.error is not None
        assert "JSON invalidos" in result.error


# ---------------------------------------------------------------
# Tests de generacion de eventos
# ---------------------------------------------------------------

class TestEventCodeGeneration:
    """Tests de generacion de codigo de eventos."""

    def test_generates_event_code_anthropic(self, anthropic_service):
        """Genera codigo para on_transfer_validate."""
        code = (
            "def on_transfer_validate(app, batch) -> bool:\n"
            "    for page in batch.pages:\n"
            "        if not page.barcodes:\n"
            "            return False\n"
            "    return True\n"
        )
        tool_input = {
            "event_name": "on_transfer_validate",
            "code": code,
            "explanation": "Valida que todas las paginas tengan barcode.",
        }
        mock_response = _make_anthropic_tool_response("set_event_code", tool_input)

        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = anthropic_service.generate_event_code(
                messages=[
                    {"role": "user", "content": "Validar que todas tengan barcode"}
                ],
                event_name="on_transfer_validate",
                current_code="",
            )

        assert result.error is None
        assert result.event_code is not None
        assert "on_transfer_validate" in result.event_code
        assert result.event_name == "on_transfer_validate"
        assert "barcode" in result.explanation.lower()

    def test_generates_event_code_openai(self, openai_service):
        """Genera codigo de evento con OpenAI."""
        code = (
            "def on_app_start(app, batch):\n"
            "    log.info('Application %s started', app.name)\n"
        )
        tool_input = {
            "event_name": "on_app_start",
            "code": code,
            "explanation": "Log al iniciar la aplicacion.",
        }
        mock_response = _make_openai_tool_response("set_event_code", tool_input)

        with patch.object(openai_service, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = (
                mock_response
            )
            result = openai_service.generate_event_code(
                messages=[{"role": "user", "content": "Log al iniciar"}],
                event_name="on_app_start",
                current_code="",
            )

        assert result.error is None
        assert result.event_code is not None
        assert "on_app_start" in result.event_code

    def test_empty_code_returns_error(self, anthropic_service):
        """Si el modelo genera codigo vacio, devuelve error."""
        tool_input = {
            "event_name": "on_app_start",
            "code": "   ",
            "explanation": "test",
        }
        mock_response = _make_anthropic_tool_response("set_event_code", tool_input)

        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = anthropic_service.generate_event_code(
                messages=[{"role": "user", "content": "test"}],
                event_name="on_app_start",
                current_code="",
            )

        assert result.error is not None
        assert "vacio" in result.error


# ---------------------------------------------------------------
# Tests de system prompt
# ---------------------------------------------------------------

class TestSystemPrompt:
    """Tests del contenido del system prompt."""

    def test_pipeline_prompt_includes_ops(self, anthropic_service):
        prompt = anthropic_service._build_pipeline_system_prompt("[]")
        assert "AutoDeskew" in prompt
        assert "BarcodeStep" in prompt
        assert "OcrStep" in prompt
        assert "ScriptStep" in prompt or "script" in prompt.lower()

    def test_pipeline_prompt_includes_current_pipeline(self, anthropic_service):
        pipeline_json = '[{"type": "image_op", "op": "Rotate"}]'
        prompt = anthropic_service._build_pipeline_system_prompt(pipeline_json)
        assert "Rotate" in prompt

    def test_pipeline_prompt_includes_script_api(self, anthropic_service):
        prompt = anthropic_service._build_pipeline_system_prompt("[]")
        assert "page.barcodes" in prompt
        assert "pipeline.skip_step" in prompt
        assert "pipeline.abort" in prompt

    def test_event_prompt_includes_signature(self, anthropic_service):
        prompt = anthropic_service._build_event_system_prompt(
            "on_transfer_validate", ""
        )
        assert "on_transfer_validate" in prompt
        assert "-> bool" in prompt
        assert "Return False to cancel" in prompt

    def test_event_prompt_no_pipeline_object(self, anthropic_service):
        prompt = anthropic_service._build_event_system_prompt("on_app_start", "")
        assert "do NOT receive the 'pipeline' object" in prompt


# ---------------------------------------------------------------
# Tests de clasificacion de errores
# ---------------------------------------------------------------

class TestErrorClassification:
    """Tests de clasificacion de errores."""

    def test_auth_error(self):
        msg = _classify_error(Exception("HTTP 401 Unauthorized"))
        assert "API key" in msg

    def test_rate_limit(self):
        msg = _classify_error(Exception("Error 429 rate limit exceeded"))
        assert "peticiones" in msg.lower()

    def test_timeout(self):
        msg = _classify_error(Exception("Request timeout"))
        assert "Timeout" in msg or "timeout" in msg

    def test_connection(self):
        msg = _classify_error(Exception("Connection refused"))
        assert "conexion" in msg.lower()

    def test_generic_error(self):
        msg = _classify_error(Exception("Something unexpected"))
        assert "proveedor" in msg.lower()


# ---------------------------------------------------------------
# Tests de tool schemas
# ---------------------------------------------------------------

class TestToolSchemas:
    """Tests de integridad de los schemas."""

    def test_pipeline_tool_has_required_fields(self):
        schema = _SET_PIPELINE_TOOL
        assert schema["name"] == "set_pipeline"
        props = schema["input_schema"]["properties"]
        assert "steps" in props
        assert "explanation" in props
        assert "steps" in schema["input_schema"]["required"]

    def test_event_tool_has_required_fields(self):
        schema = _SET_EVENT_CODE_TOOL
        assert schema["name"] == "set_event_code"
        props = schema["input_schema"]["properties"]
        assert "event_name" in props
        assert "code" in props
        assert "explanation" in props

    def test_step_type_enum(self):
        step_schema = _SET_PIPELINE_TOOL["input_schema"]["properties"]["steps"]
        type_prop = step_schema["items"]["properties"]["type"]
        assert set(type_prop["enum"]) == {"image_op", "barcode", "ocr", "script"}


# ---------------------------------------------------------------
# Tests de API error handling
# ---------------------------------------------------------------

class TestApiErrorHandling:
    """Tests de manejo de errores de API."""

    def test_api_error_returns_response_with_error(self, anthropic_service):
        """Un error de API devuelve AssistantResponse con error."""
        with patch.object(anthropic_service, "_get_client") as mock_client:
            mock_client.return_value.messages.create.side_effect = Exception(
                "HTTP 401 Unauthorized"
            )
            result = anthropic_service.generate_pipeline(
                messages=[{"role": "user", "content": "test"}],
                current_pipeline_json="[]",
            )

        assert result.error is not None
        assert "API key" in result.error

    def test_empty_openai_response(self, openai_service):
        """Respuesta vacia de OpenAI devuelve error."""
        response = MagicMock()
        response.choices = []

        with patch.object(openai_service, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = response
            result = openai_service.generate_pipeline(
                messages=[{"role": "user", "content": "test"}],
                current_pipeline_json="[]",
            )

        assert result.error is not None
        assert "vacia" in result.error.lower()
