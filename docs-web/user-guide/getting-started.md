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
python main.py

# Abrir directamente una aplicación
python main.py "Facturas Proveedores"

# Modo headless — escanear y transferir sin UI
python main.py --direct-mode "Facturas Proveedores"

# Worker desatendido — vigilar una carpeta de entrada
python -m docscan_worker --app-name "Facturas Proveedores" --watch /ruta/entrada

# Worker desatendido — procesar lotes pendientes y salir
python -m docscan_worker --app-name "Facturas Proveedores" --process-pending
```

## Primer arranque

Al ejecutar por primera vez:

1. Se muestra la pantalla de **splash** con el progreso
2. Se crea automáticamente la base de datos SQLite
3. Aparece el **Launcher** vacío, listo para crear la primera aplicación

!!! tip "Siguiente paso"
    Continúa con la [guía del Launcher](launcher.md) para crear tu primera aplicación.

