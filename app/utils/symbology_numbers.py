"""Leyenda legacy de simbologías: número de dos dígitos por simbología.

Es la ``SymbologyNumberLegend`` de FlexibarNET10, heredada del Flexibar.NET
original. Con «incluir simbología» activado, una regex no se evalúa contra
el valor del código sino contra ``NN`` + valor, donde ``NN`` es este número:
``^(02|10)`` acepta Code128 o Interleaved 2 of 5. Las Apps del Hospital Arnau
de Vilanova dependen de ello, así que los números son los mismos que en
Flexibar. Las claves son los nombres de simbología de DocScan.
"""

from __future__ import annotations

_SYMBOLOGY_NUMBERS: dict[str, int] = {
    "Code39": 1,
    "Code128": 2,
    "UPCA": 3,
    "EAN13": 4,
    "EAN8": 4,
    "UPCE": 6,
    "Code93": 8,
    "Codabar": 9,
    "ITF": 10,  # Interleaved 2 of 5
    "Aztec": 19,
    "DataMatrix": 20,
    "PDF417": 21,
    "QR": 22,
    "MicroQRCode": 38,
    "MaxiCode": 39,
}


def symbology_number(symbology: str) -> int:
    """Número legacy de la simbología, o 0 si no está en la leyenda."""
    return _SYMBOLOGY_NUMBERS.get(symbology or "", 0)


def symbology_prefix(symbology: str) -> str:
    """Número legacy con dos dígitos (``"02"`` para Code128)."""
    return f"{symbology_number(symbology):02d}"


def legend() -> list[tuple[str, str]]:
    """Pares (simbología, ``NN``) ordenados por número, para mostrar en la UI."""
    return sorted(
        ((name, f"{num:02d}") for name, num in _SYMBOLOGY_NUMBERS.items()),
        key=lambda e: (e[1], e[0]),
    )
