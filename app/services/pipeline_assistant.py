"""Servicio de asistente IA para construcción de pipelines y scripts.

Genera y modifica pipelines completos o código de eventos lifecycle
a partir de instrucciones en lenguaje natural, usando tool calling
de Anthropic o OpenAI.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.pipeline.serializer import deserialize
from app.pipeline.steps import PipelineStep
from app.services._assistant_constants import (
    IMAGE_OPS_REFERENCE as _IMAGE_OPS_REFERENCE,
    SCRIPT_API_REFERENCE as _SCRIPT_API_REFERENCE,
    EVENT_SIGNATURES as _EVENT_SIGNATURES,
)

log = logging.getLogger(__name__)

# Timeout para llamadas API (segundos)
_API_TIMEOUT = 90
# Reintentos para rate-limit
_RATE_LIMIT_RETRIES = 1
_RATE_LIMIT_DELAY = 2.0

# Modelos por defecto
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
_DEFAULT_OPENAI_MODEL = "gpt-4o"

# ---------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------

_SET_PIPELINE_TOOL = {
    "name": "set_pipeline",
    "description": (
        "Sets the complete pipeline configuration. Always return the FULL "
        "pipeline (all steps), not just changes. Generate working Python code "
        "for ScriptStep.script fields."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "Ordered list of pipeline steps.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["image_op", "barcode", "ocr", "script"],
                        },
                        "enabled": {"type": "boolean", "default": True},
                        # ImageOpStep
                        "op": {"type": "string"},
                        "params": {"type": "object"},
                        "window": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        # BarcodeStep
                        "engine": {"type": "string", "enum": ["motor1", "motor2"]},
                        "symbologies": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "regex": {"type": "string"},
                        "regex_include_symbology": {"type": "boolean"},
                        "orientations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "quality_threshold": {"type": "number"},
                        # OcrStep
                        "languages": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "full_page": {"type": "boolean"},
                        # ScriptStep
                        "label": {"type": "string"},
                        "entry_point": {"type": "string"},
                        "script": {"type": "string"},
                    },
                    "required": ["type"],
                },
            },
            "explanation": {
                "type": "string",
                "description": "Brief explanation of the changes made.",
            },
        },
        "required": ["steps", "explanation"],
    },
}

_SET_EVENT_CODE_TOOL = {
    "name": "set_event_code",
    "description": (
        "Sets the Python code for a lifecycle event. Generate complete, "
        "working Python code using the script context API."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "event_name": {
                "type": "string",
                "description": "Name of the lifecycle event.",
            },
            "code": {
                "type": "string",
                "description": "Complete Python code for the event.",
            },
            "explanation": {
                "type": "string",
                "description": "Brief explanation of what the code does.",
            },
        },
        "required": ["event_name", "code", "explanation"],
    },
}


# ---------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------

@dataclass
class AssistantResponse:
    """Respuesta del asistente IA.

    Attributes:
        steps: Lista de pasos propuestos (solo para set_pipeline).
        event_code: Codigo generado (solo para set_event_code).
        event_name: Nombre del evento (solo para set_event_code).
        explanation: Explicacion de los cambios.
        text: Texto libre del modelo (si no uso tool calling).
        error: Mensaje de error si fallo.
    """

    steps: list[PipelineStep] | None = None
    event_code: str | None = None
    event_name: str | None = None
    explanation: str = ""
    text: str = ""
    error: str | None = None


# ---------------------------------------------------------------
# Servicio principal
# ---------------------------------------------------------------

class PipelineAssistantService:
    """Asistente IA para construir pipelines y generar scripts.

    Usa tool calling (Anthropic o OpenAI) para producir JSON estructurado.

    Args:
        provider: "anthropic" o "openai".
        api_key: Clave API del proveedor.
        model: Modelo a usar (None = default por proveedor).
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str | None = None,
    ) -> None:
        if provider not in ("anthropic", "openai"):
            raise ValueError(f"Proveedor no soportado: {provider}")
        self._provider = provider
        self._api_key = api_key
        self._model = model or (
            _DEFAULT_ANTHROPIC_MODEL
            if provider == "anthropic"
            else _DEFAULT_OPENAI_MODEL
        )
        self._client: Any = None

    def _get_client(self) -> Any:
        """Inicializacion lazy del cliente API."""
        if self._client is not None:
            return self._client

        if self._provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                timeout=_API_TIMEOUT,
            )
        else:
            import openai
            self._client = openai.OpenAI(
                api_key=self._api_key,
                timeout=_API_TIMEOUT,
            )
        return self._client

    # ------------------------------------------------------------------
    # System prompt builders
    # ------------------------------------------------------------------

    def _build_pipeline_system_prompt(self, current_pipeline_json: str) -> str:
        """Construye el system prompt para modo pipeline."""
        return (
            "You are a pipeline configuration assistant for DocScan Studio, "
            "a document scanning and processing application.\n\n"
            "You help users build and modify image processing pipelines by "
            "converting natural language descriptions into structured pipeline steps.\n\n"
            "IMPORTANT RULES:\n"
            "- Always call the set_pipeline tool with the COMPLETE pipeline "
            "(all steps, not just changes).\n"
            "- Generate working Python code for ScriptStep.script fields.\n"
            "- Each ScriptStep must define a function matching entry_point "
            "(default: 'process').\n"
            "- Script function signature: def process(app, batch, page, pipeline):\n"
            "- Use the script context API documented below.\n"
            "- Respond in the same language as the user's message.\n\n"
            f"{_IMAGE_OPS_REFERENCE}\n"
            "## BarcodeStep fields\n"
            "- engine: 'motor1' (pyzbar+opencv) or 'motor2' (zxing-cpp)\n"
            "- symbologies: list of barcode types (e.g., ['Code128', 'QR', "
            "'EAN13', 'Code39', 'DataMatrix', 'PDF417']). Empty = all.\n"
            "- regex: optional filter pattern for barcode values\n"
            "- regex_include_symbology: include symbology prefix in regex match\n"
            "- orientations: ['horizontal', 'vertical', 'diagonal']\n"
            "- quality_threshold: 0.0-1.0 confidence threshold\n"
            "- window: [x, y, w, h] in pixels or null for full page\n\n"
            "## OcrStep fields\n"
            "- engine: 'rapidocr' (fast, recommended), 'easyocr' (needs GPU), "
            "'tesseract' (fallback)\n"
            "- languages: ISO codes, e.g., ['es', 'en', 'fr', 'de', 'ca']\n"
            "- full_page: true for full page, false for window region\n"
            "- window: [x, y, w, h] in pixels or null\n\n"
            f"{_SCRIPT_API_REFERENCE}\n"
            "## Current pipeline\n"
            f"```json\n{current_pipeline_json}\n```\n"
        )

    def _build_event_system_prompt(
        self,
        event_name: str,
        current_code: str,
    ) -> str:
        """Construye el system prompt para modo evento."""
        signature = _EVENT_SIGNATURES.get(event_name, f"def {event_name}(app, batch):")

        return (
            "You are a code generation assistant for DocScan Studio, "
            "a document scanning and processing application.\n\n"
            "You help users write Python code for lifecycle events.\n\n"
            "IMPORTANT RULES:\n"
            "- Always call the set_event_code tool with complete, working Python code.\n"
            "- The code must define the correct function with the right signature.\n"
            "- Use the script context API documented below.\n"
            "- NOTE: lifecycle events do NOT receive the 'pipeline' object "
            "(only ScriptStep does).\n"
            "- Respond in the same language as the user's message.\n\n"
            f"## Event: {event_name}\n"
            f"Signature:\n```python\n{signature}\n```\n\n"
            f"{_SCRIPT_API_REFERENCE}\n"
            "## Current code for this event\n"
            f"```python\n{current_code or '# (empty — no code yet)'}\n```\n"
        )

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    def generate_pipeline(
        self,
        messages: list[dict[str, str]],
        current_pipeline_json: str,
    ) -> AssistantResponse:
        """Genera o modifica un pipeline a partir de mensajes de usuario.

        Args:
            messages: Historial de conversacion [{role, content}, ...].
            current_pipeline_json: Pipeline actual serializado.

        Returns:
            AssistantResponse con steps y explanation, o error.
        """
        system_prompt = self._build_pipeline_system_prompt(current_pipeline_json)
        tools = [_SET_PIPELINE_TOOL]
        return self._call_api(system_prompt, messages, tools, mode="pipeline")

    def generate_event_code(
        self,
        messages: list[dict[str, str]],
        event_name: str,
        current_code: str,
    ) -> AssistantResponse:
        """Genera codigo Python para un evento lifecycle.

        Args:
            messages: Historial de conversacion.
            event_name: Nombre del evento.
            current_code: Codigo actual del evento.

        Returns:
            AssistantResponse con event_code y explanation, o error.
        """
        system_prompt = self._build_event_system_prompt(event_name, current_code)
        tools = [_SET_EVENT_CODE_TOOL]
        return self._call_api(system_prompt, messages, tools, mode="event")

    def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict],
        mode: str,
    ) -> AssistantResponse:
        """Llama a la API del proveedor con tool calling."""
        try:
            if self._provider == "anthropic":
                return self._call_anthropic(system_prompt, messages, tools, mode)
            else:
                return self._call_openai(system_prompt, messages, tools, mode)
        except Exception as e:
            error_msg = _classify_error(e)
            log.error("Error API %s: %s", self._provider, e)
            return AssistantResponse(error=error_msg)

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _call_anthropic(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict],
        mode: str,
    ) -> AssistantResponse:
        """Llamada a Anthropic con tool calling."""
        client = self._get_client()

        response = _call_with_retry(
            lambda: client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )
        )

        # Buscar tool_use en la respuesta
        tool_use = None
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "tool_use":
                tool_use = block
            elif block.type == "text":
                text_parts.append(block.text)

        text = "\n".join(text_parts)

        if tool_use is None:
            # El modelo respondio sin usar tool — devolver texto
            return AssistantResponse(text=text)

        return self._parse_tool_response(
            tool_name=tool_use.name,
            tool_input=tool_use.input,
            text=text,
            mode=mode,
        )

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    def _call_openai(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict],
        mode: str,
    ) -> AssistantResponse:
        """Llamada a OpenAI con tool calling."""
        client = self._get_client()

        # Convertir tool schema al formato OpenAI
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

        openai_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        response = _call_with_retry(
            lambda: client.chat.completions.create(
                model=self._model,
                max_tokens=4096,
                messages=openai_messages,
                tools=openai_tools,
            )
        )

        choice = response.choices[0] if response.choices else None
        if choice is None:
            return AssistantResponse(error="Respuesta vacia del modelo.")

        msg = choice.message
        text = msg.content or ""

        # Comprobar tool calls
        if not msg.tool_calls:
            return AssistantResponse(text=text)

        tool_call = msg.tool_calls[0]
        try:
            tool_input = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return AssistantResponse(
                text=text,
                error="El asistente genero argumentos JSON invalidos.",
            )

        return self._parse_tool_response(
            tool_name=tool_call.function.name,
            tool_input=tool_input,
            text=text,
            mode=mode,
        )

    # ------------------------------------------------------------------
    # Parse tool response
    # ------------------------------------------------------------------

    def _parse_tool_response(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        text: str,
        mode: str,
    ) -> AssistantResponse:
        """Parsea la respuesta del tool calling."""
        explanation = tool_input.get("explanation", "")

        if tool_name == "set_pipeline":
            return self._parse_pipeline_response(tool_input, text, explanation)
        elif tool_name == "set_event_code":
            return self._parse_event_response(tool_input, text, explanation)
        else:
            return AssistantResponse(
                text=text,
                error=f"Tool desconocido: {tool_name}",
            )

    def _parse_pipeline_response(
        self,
        tool_input: dict[str, Any],
        text: str,
        explanation: str,
    ) -> AssistantResponse:
        """Parsea respuesta de set_pipeline."""
        raw_steps = tool_input.get("steps", [])

        # Asignar IDs unicos a cada paso
        for step_data in raw_steps:
            if "id" not in step_data or not step_data["id"]:
                step_data["id"] = f"step_{uuid.uuid4().hex[:8]}"

        # Usar el deserializador existente para validar
        try:
            steps_json = json.dumps(raw_steps, ensure_ascii=False)
            steps = deserialize(steps_json)
        except Exception as e:
            log.warning("Pipeline invalido del asistente: %s", e)
            return AssistantResponse(
                text=text,
                explanation=explanation,
                error=f"El asistente genero un pipeline invalido: {e}",
            )

        return AssistantResponse(
            steps=steps,
            explanation=explanation,
            text=text,
        )

    def _parse_event_response(
        self,
        tool_input: dict[str, Any],
        text: str,
        explanation: str,
    ) -> AssistantResponse:
        """Parsea respuesta de set_event_code."""
        code = tool_input.get("code", "")
        event_name = tool_input.get("event_name", "")

        if not code.strip():
            return AssistantResponse(
                text=text,
                explanation=explanation,
                error="El asistente genero codigo vacio.",
            )

        return AssistantResponse(
            event_code=code,
            event_name=event_name,
            explanation=explanation,
            text=text,
        )


# ---------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------

def _call_with_retry(fn: Any, retries: int = _RATE_LIMIT_RETRIES) -> Any:
    """Ejecuta fn() con retry para rate-limit."""
    for attempt in range(1 + retries):
        try:
            return fn()
        except Exception as e:
            error_type = type(e).__name__
            is_rate_limit = "rate" in error_type.lower() or "429" in str(e)
            if is_rate_limit and attempt < retries:
                log.warning(
                    "Rate limit detectado, reintentando en %.1fs...",
                    _RATE_LIMIT_DELAY,
                )
                time.sleep(_RATE_LIMIT_DELAY)
                continue
            raise


def _classify_error(e: Exception) -> str:
    """Clasifica el error para mostrar un mensaje amigable."""
    error_str = str(e).lower()
    error_type = type(e).__name__.lower()

    if "401" in error_str or "unauthorized" in error_str or "invalid" in error_type:
        return "API key invalida. Revisa tu configuracion."
    if "429" in error_str or "rate" in error_type:
        return "Limite de peticiones alcanzado. Intentalo en unos segundos."
    if "timeout" in error_str or "timeout" in error_type:
        return "Timeout en la peticion. Intentalo de nuevo."
    if "connection" in error_str or "network" in error_str:
        return "Error de conexion. Verifica tu conexion a internet."

    return f"Error del proveedor: {e}"
