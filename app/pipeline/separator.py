"""Condición de separador de documento de un ``BarcodeStep``.

Paridad con ``SeparatorMatcher`` de FlexibarNET10: la misma lógica sirve a
la detección automática (executor) y a la marca manual del Workbench, que
propone el valor del primer código que cumple la condición.

Modos (``separator_by``):

- ``symbology``: la simbología del código es ``separator_symbology``.
- ``regex``: ``separator_regex`` encuentra algo en el valor (o en ``NN`` +
  valor con ``separator_regex_include_symbology``, donde ``NN`` es el número
  legacy de la simbología).
- ``fixed_value``: el valor es exactamente ``separator_fixed_value``.

Una regex inválida o que agota el tiempo cuenta como «no casa», como en
Flexibar: nunca marca un separador por error.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.utils import safe_regex
from app.utils.symbology_numbers import symbology_prefix

SEPARATOR_MODES = ("symbology", "regex", "fixed_value")


def matches(step: Any, barcode: Any) -> bool:
    """¿El código cumple la condición de separador del paso?

    Args:
        step: ``BarcodeStep`` con los campos ``separator_*``.
        barcode: Resultado de lectura con ``value`` y ``symbology``.
    """
    mode = getattr(step, "separator_by", "regex")
    value = getattr(barcode, "value", "") or ""
    symbology = getattr(barcode, "symbology", "") or ""

    if mode == "symbology":
        wanted = getattr(step, "separator_symbology", "") or ""
        return bool(wanted) and symbology.lower() == wanted.lower()

    if mode == "regex":
        pattern = getattr(step, "separator_regex", "") or ""
        if not pattern:
            return False
        text = value
        if getattr(step, "separator_regex_include_symbology", False):
            text = f"{symbology_prefix(symbology)}{value}"
        return safe_regex.search(pattern, text, default=False)

    if mode == "fixed_value":
        wanted = getattr(step, "separator_fixed_value", "") or ""
        return bool(wanted) and value == wanted

    return False


def find_matching_value(step: Any, barcodes: Iterable[Any]) -> str | None:
    """Valor del primer código que cumple la condición, o None."""
    for barcode in barcodes:
        if matches(step, barcode):
            return getattr(barcode, "value", "") or ""
    return None


def suggest_manual_value(step: Any | None, barcodes: Iterable[Any]) -> str:
    """Valor con el que se pre-rellena la marca manual de separador.

    Orden de Flexibar: código que cumple la condición (salvo en
    ``fixed_value``, cuya constante no identifica un documento) → primer
    código de la página → ``separator_default_value`` → vacío.
    """
    barcodes = list(barcodes)
    if step is not None and getattr(step, "separator_by", "") != "fixed_value":
        found = find_matching_value(step, barcodes)
        if found:
            return found
    if barcodes:
        return getattr(barcodes[0], "value", "") or ""
    if step is not None:
        return getattr(step, "separator_default_value", "") or ""
    return ""


def manual_value_error(step: Any | None, value: str) -> str | None:
    """Valida el valor que teclea el operador contra ``separator_manual_regex``.

    Returns:
        None si es válido (o no hay regex), o el motivo si no lo es.
    """
    pattern = getattr(step, "separator_manual_regex", "") if step else ""
    if not pattern or not value:
        return None
    if safe_regex.compile_pattern(pattern) is None:
        return None
    if safe_regex.search(pattern, value, default=True):
        return None
    return f"El valor no cumple el formato esperado ({pattern})"


def detection_step(steps: Iterable[Any]) -> Any | None:
    """Primer ``BarcodeStep`` activo con detección de separador."""
    for step in steps:
        if (
            getattr(step, "type", "") == "barcode"
            and getattr(step, "enabled", True)
            and getattr(step, "separator_enabled", False)
        ):
            return step
    return None
