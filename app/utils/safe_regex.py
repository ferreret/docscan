"""Aplicación de expresiones regulares de usuario con límite de tiempo.

Las regex que escribe el integrador (filtro de un `BarcodeStep`,
validación del barcode manual) pueden sufrir *backtracking* catastrófico:
un patrón como ``^(a|a)*$`` contra una cadena de cuarenta caracteres que
no encaja tarda más que la edad del universo.

Acotarlo **no se puede hacer con hilos**: el módulo ``re`` no libera el
GIL mientras evalúa, así que un hilo atrapado en un patrón patológico
congela el intérprete entero y ni siquiera el hilo que vigila el plazo
llega a despertar. Comprobado: el proceso queda inerte.

La solución es el módulo ``regex``, que comprueba el plazo desde dentro
del bucle de matching (parámetro ``timeout``) y además resiste por diseño
la mayoría de los patrones que hacen explotar a ``re``. Si no está
instalado se cae a ``re`` sin límite de tiempo, que es el comportamiento
histórico: la aplicación funciona igual, pero pierde la red de seguridad.

Criterio **fail-open**: si el patrón no termina a tiempo se registra un
error claro y se sigue como si no filtrara. Es preferible dejar pasar un
valor a congelar la captura del operador.
"""

from __future__ import annotations

import functools
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Segundos que se le conceden a un patrón antes de darlo por colgado.
DEFAULT_REGEX_TIMEOUT = 1.0

try:  # pragma: no cover - depende del entorno
    import regex as _regex

    HAS_TIMEOUT_SUPPORT = True
except ImportError:  # pragma: no cover - depende del entorno
    _regex = None
    HAS_TIMEOUT_SUPPORT = False
    log.warning(
        "El módulo 'regex' no está instalado: las expresiones regulares de "
        "usuario se evaluarán sin límite de tiempo. Un patrón con "
        "backtracking catastrófico puede colgar el proceso."
    )


@functools.lru_cache(maxsize=128)
def compile_pattern(pattern: str) -> Any | None:
    """Compila un patrón, cacheado por texto.

    Args:
        pattern: Texto de la expresión regular.

    Returns:
        El patrón compilado, o None si es inválido.
    """
    engine = _regex if HAS_TIMEOUT_SUPPORT else re
    try:
        return engine.compile(pattern)
    except Exception as e:  # regex.error y re.error no comparten jerarquía
        log.error("Regex inválido '%s': %s", pattern, e)
        return None


def search(
    pattern: str,
    value: str,
    *,
    timeout: float = DEFAULT_REGEX_TIMEOUT,
    default: bool = True,
) -> bool:
    """¿El patrón encuentra algo en el valor? Acotado en tiempo.

    Args:
        pattern: Texto de la expresión regular.
        value: Texto sobre el que buscar.
        timeout: Segundos máximos de evaluación.
        default: Qué devolver si el patrón se cuelga o es inválido
            (fail-open: True).

    Returns:
        True si hay coincidencia; ``default`` si expira el plazo.
    """
    return _apply("search", pattern, value, timeout, default)


def fullmatch(
    pattern: str,
    value: str,
    *,
    timeout: float = DEFAULT_REGEX_TIMEOUT,
    default: bool = True,
) -> bool:
    """¿El patrón cubre el valor entero? Acotado en tiempo.

    Args:
        pattern: Texto de la expresión regular.
        value: Texto a validar.
        timeout: Segundos máximos de evaluación.
        default: Qué devolver si el patrón se cuelga o es inválido
            (fail-open: True).

    Returns:
        True si coincide por completo; ``default`` si expira el plazo.
    """
    return _apply("fullmatch", pattern, value, timeout, default)


def _apply(
    method: str,
    pattern: str,
    value: str,
    timeout: float,
    default: bool,
) -> bool:
    """Aplica ``method`` del patrón compilado respetando el plazo."""
    compiled = compile_pattern(pattern)
    if compiled is None:
        return default

    fn = getattr(compiled, method)
    try:
        if HAS_TIMEOUT_SUPPORT:
            return fn(value, timeout=timeout) is not None
        return fn(value) is not None
    except TimeoutError:
        log.error(
            "El patrón '%s' excedió el límite de %ss (backtracking "
            "catastrófico); se ignora el filtro para este valor",
            pattern,
            timeout,
        )
        return default
