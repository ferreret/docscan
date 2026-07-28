"""Modelos ORM de DocScan Studio.

Este paquete importa **todos** los modelos a propósito. SQLAlchemy
resuelve las relaciones por nombre (``relationship("OperationHistory")``)
y solo puede hacerlo si la clase referida ya está registrada; si un
módulo se importa suelto, la configuración del mapper falla con un
``NameError`` que no señala a ningún sitio útil.

Importarlos aquí garantiza que traer cualquier modelo registre el
conjunto entero. Es también lo que permite ejecutar un fichero de tests
por separado sin arrastrar la batería completa.
"""

from app.models.application import Application
from app.models.barcode import Barcode
from app.models.batch import Batch
from app.models.operation_history import OperationHistory
from app.models.page import Page
from app.models.template import Template

__all__ = [
    "Application",
    "Barcode",
    "Batch",
    "OperationHistory",
    "Page",
    "Template",
]
