"""Agente local de DocScan Studio.

Proceso FastAPI ligero que el operario instala en su PC. Expone endpoints
HTTP en localhost que el navegador (web SaaS) usa para escanear documentos
y transferirlos a destinos locales.

Comparte código con la aplicación desktop (importa ``app.services.scanner_service``
sin modificarlo).
"""

from __future__ import annotations

__version__ = "0.1.0"
