# :rocket: Inicio rápido

## Requisitos del sistema

| Componente | Requisito | Notas |
|-----------|---------|-------|
| Sistema operativo | Linux / Windows 10+ | macOS no soportado oficialmente |
| Python | **3.14** o superior | En Linux: `python3.14` |
| RAM | 4 GB mínimo | 8 GB recomendado para OCR + IA |
| Escáner | SANE (Linux) o TWAIN/WIA (Windows) | Opcional |

## Instalación

=== "Linux"

    ```bash
    git clone https://github.com/ferreret/docscan.git
    cd docscan
    python3.14 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    alembic upgrade head
    python3.14 main.py
    ```

=== "Windows"

    ```powershell
    git clone https://github.com/ferreret/docscan.git
    cd docscan
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    alembic upgrade head
    python main.py
    ```

## Modos de ejecución

```bash
# Launcher — gestionar aplicaciones
python3.14 main.py

# Abrir directamente una aplicación
python3.14 main.py "Facturas Proveedores"

# Modo headless — escanear y transferir sin UI
python3.14 main.py --direct-mode "Facturas Proveedores"

# Worker desatendido
python3.14 -m docscan_worker --batch-path /ruta/a/documentos
```

## Primer arranque

Al ejecutar por primera vez:

1. Se muestra la pantalla de **splash** con el progreso
2. Se crea automáticamente la base de datos SQLite
3. Aparece el **Launcher** vacío, listo para crear la primera aplicación

!!! tip "Siguiente paso"
    Continúa con la [guía del Launcher](launcher.md) para crear tu primera aplicación.

