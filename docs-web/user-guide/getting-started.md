# :rocket: Inicio rápido

## Requisitos del sistema

| Componente | Requisito | Notas |
|-----------|---------|-------|
| Sistema operativo | Linux / Windows 10+ | macOS no soportado oficialmente |
| Python | **3.14** | Solo para ejecutar desde el código; los instaladores ya lo incluyen |
| RAM | 4 GB mínimo | 8 GB recomendado para OCR + IA |
| Escáner | SANE (Linux) o TWAIN/WIA (Windows) | Opcional |

## Instalación con el instalador (recomendada)

Descarga la última versión de
[GitHub Releases](https://github.com/ferreret/docscan/releases):

| Sistema | Fichero |
|---------|---------|
| Linux | `docscan-0.1.9-x86_64.AppImage` |
| Windows | `docscan-0.1.9-setup.exe` |

Cada release publica también `SHA256SUMS.txt`, con el SHA-256 de cada
instalador, para comprobar la descarga. No hace falta instalar Python.

=== "Linux"

    ```bash
    sha256sum -c SHA256SUMS.txt --ignore-missing
    chmod +x docscan-0.1.9-x86_64.AppImage
    ./docscan-0.1.9-x86_64.AppImage
    ```

=== "Windows"

    Ejecuta `docscan-0.1.9-setup.exe` y sigue el asistente.

### Actualizaciones

Al arrancar, DocScan comprueba en segundo plano si hay una versión nueva. Si la
hay, el Launcher muestra un aviso «Versión X disponible» con **Ver novedades**,
**Actualizar** e **Ignorar**. También se puede comprobar a mano en **Acerca de →
Buscar actualizaciones**.

La descarga se verifica contra `SHA256SUMS.txt` y se rechaza si la release no
publica el checksum. En Linux se sustituye el AppImage en uso y hay que
reiniciar la aplicación; en Windows se lanza el instalador y la aplicación se
cierra.

## Instalación desde el código

Para desarrollo. El Python 3.14 lo gestiona [uv](https://docs.astral.sh/uv/):
en Linux no hace falta un `python3.14` del sistema.

=== "Linux"

    ```bash
    # Paquetes del sistema (Ubuntu)
    sudo apt install libzbar0t64 libsane-dev libxcb-cursor0 build-essential

    git clone https://github.com/ferreret/docscan.git
    cd docscan
    uv venv --python 3.14 --managed-python
    uv pip install -r requirements.txt
    .venv/bin/python main.py
    ```

=== "Windows"

    ```powershell
    git clone https://github.com/ferreret/docscan.git
    cd docscan
    py -3.14 -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python main.py
    ```

La base de datos se crea y se migra sola al arrancar: no hay que lanzar
`alembic`.

## Modos de ejecución

Desde el código, con el entorno `.venv` activado:

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

Opciones del worker, además de `--app-name` y de `--watch` o `--process-pending`
(una de las dos es obligatoria):

| Opción | Por defecto | Qué hace |
|--------|-------------|----------|
| `--debounce N` | 3 | Segundos sin cambios en la carpeta antes de crear el lote |
| `--sentinel NOMBRE` | — | Modo centinela: crea el lote cuando aparece ese fichero (por ejemplo `GO.txt`) y después lo borra |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING` o `ERROR` |

## Primer arranque

Al ejecutar por primera vez:

1. Se muestra la pantalla de **splash** con el progreso
2. Se crea automáticamente la base de datos SQLite (`docscan.db`) en la carpeta
   de datos: `~/.local/share/docscan/` en Linux y `%LOCALAPPDATA%\docscan\` en
   Windows. Las imágenes de los lotes van en `images/` dentro de esa carpeta
3. Aparece el **Launcher** vacío, listo para crear la primera aplicación

!!! tip "Siguiente paso"
    Continúa con la [guía del Launcher](launcher.md) para crear tu primera aplicación.

