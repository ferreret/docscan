"""Script para crear una aplicación de prueba con pipeline de barcodes.

Uso: python3.14 scripts/create_barcode_app.py
"""

import json
import sys
from pathlib import Path

# Añadir raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import create_db_engine, create_tables, get_session_factory
from app.db.repositories.application_repo import ApplicationRepository
from app.models.application import Application
from app.models.batch import Batch  # noqa: F401
from app.models.page import Page  # noqa: F401
from app.models.barcode import Barcode  # noqa: F401
from app.models.template import Template  # noqa: F401
from app.models.operation_history import OperationHistory  # noqa: F401

APP_NAME = "Lectura Barcodes"

pipeline = [
    {
        "id": "barcode_motor1",
        "type": "barcode",
        "enabled": True,
        "engine": "motor1",
        "symbologies": [],
        "regex": "",
        "regex_include_symbology": False,
        "orientations": ["horizontal", "vertical"],
        "quality_threshold": 0.0,
        "window": None,
    },
    {
        "id": "barcode_motor2",
        "type": "barcode",
        "enabled": True,
        "engine": "motor2",
        "symbologies": [],
        "regex": "",
        "regex_include_symbology": False,
        "orientations": ["horizontal", "vertical"],
        "quality_threshold": 0.0,
        "window": None,
    },
]

batch_fields = [
    {"name": "referencia", "label": "Referencia", "type": "text", "required": False},
    {"name": "operador", "label": "Operador", "type": "text", "required": False},
]

index_fields = [
    {"name": "barcode_value", "label": "Código", "type": "text", "required": False},
    {"name": "barcode_type", "label": "Tipo", "type": "text", "required": False},
]

transfer_config = {
    "mode": "folder",
    "destination": "/tmp/docscan_output",
    "filename_pattern": "{batch_id}_{page_index:04d}",
    "create_subdirs": True,
    "include_metadata": True,
}


def main():
    engine = create_db_engine()
    create_tables(engine)
    factory = get_session_factory(engine)

    with factory() as session:
        repo = ApplicationRepository(session)

        existing = repo.get_by_name(APP_NAME)
        if existing:
            print(f"La aplicación '{APP_NAME}' ya existe (id={existing.id}). Actualizando pipeline...")
            existing.pipeline_json = json.dumps(pipeline, ensure_ascii=False)
            existing.batch_fields_json = json.dumps(batch_fields, ensure_ascii=False)
            existing.index_fields_json = json.dumps(index_fields, ensure_ascii=False)
            existing.transfer_json = json.dumps(transfer_config, ensure_ascii=False)
            session.commit()
            print(f"Aplicación actualizada: id={existing.id}")
        else:
            app = Application(
                name=APP_NAME,
                description="Lectura automática de códigos de barras con Motor 1 (pyzbar) y Motor 2 (zxing-cpp)",
                pipeline_json=json.dumps(pipeline, ensure_ascii=False),
                batch_fields_json=json.dumps(batch_fields, ensure_ascii=False),
                index_fields_json=json.dumps(index_fields, ensure_ascii=False),
                transfer_json=json.dumps(transfer_config, ensure_ascii=False),
                output_format="png",
                default_tab="lote",
            )
            repo.save(app)
            session.commit()
            print(f"Aplicación '{APP_NAME}' creada con id={app.id}")

    print("\nPipeline configurado:")
    print("  1. BarcodeStep (Motor 1 - pyzbar): todas las simbologías")
    print("  2. BarcodeStep (Motor 2 - zxing-cpp): todas las simbologías")
    print("\nPara probar: python3.14 main.py → Abrir 'Lectura Barcodes' → Importar imagen con barcodes")


if __name__ == "__main__":
    main()
