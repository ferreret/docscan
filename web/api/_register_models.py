"""Importa todos los modelos ORM para registrar las relaciones SQLAlchemy.

Se importa al arrancar tanto el API (main.py) como el worker ARQ
(tasks/worker.py): cualquier proceso que abra una sesión SQLAlchemy
necesita que todas las clases mapeadas estén cargadas antes de la
primera consulta para que las relationships referenciadas por nombre
puedan resolverse.

Este módulo no exporta nada: el efecto deseado es el side-effect del
import.
"""

from __future__ import annotations

from app.models.application import Application  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.batch import Batch  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.template import Template  # noqa: F401
from web.api.models import AuditLog, Invitation, Tenant, User  # noqa: F401
