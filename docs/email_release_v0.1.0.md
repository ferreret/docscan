Asunto: DocScan Studio v0.1.0 — Primera release publicada + Guía de instalación

---

Hola,

Te escribo para informarte de que hemos publicado la primera versión estable de DocScan Studio (v0.1.0). A continuación tienes todo lo necesario para instalar, probar y consultar la documentación.

---

### Descarga e instalación

Los instaladores están disponibles en la página de releases de GitHub:

https://github.com/ferreret/docscan/releases/tag/v0.1.0

| Plataforma | Fichero | Tamaño aprox. |
|------------|---------|---------------|
| Windows | docscan-0.1.0-setup.exe | ~101 MB |
| Linux | docscan-0.1.0-x86_64.AppImage | ~180 MB |

**Windows:**
1. Descargar docscan-0.1.0-setup.exe
2. Ejecutar el instalador (no requiere permisos de administrador)
3. Seguir el asistente — se instala en el directorio del usuario
4. Abrir desde el menú Inicio → DocScan Studio

**Linux:**
1. Descargar docscan-0.1.0-x86_64.AppImage
2. Dar permisos de ejecución: chmod +x docscan-0.1.0-x86_64.AppImage
3. Ejecutar directamente (no requiere instalación)

---

### Documentación

| Recurso | Enlace / Ubicación |
|---------|-------------------|
| README del proyecto | https://github.com/ferreret/docscan#readme |
| Documentación web (MkDocs) | https://ferreret.github.io/docscan/ |
| Manual de usuario (Word) | docs/manual_docscan_studio.docx en el repositorio |
| Historial de cambios | https://github.com/ferreret/docscan/blob/main/CHANGELOG.md |
| Informe de licenciamiento | https://github.com/ferreret/docscan/blob/main/docs/INFORME_LICENCIAMIENTO.md |

---

### Repositorio GitHub

https://github.com/ferreret/docscan

El repositorio contiene el código fuente, la documentación, los tests (849 tests automatizados) y la configuración de CI/CD.

Ramas principales:
- main — desarrollo e integración
- production — versiones estables publicadas

---

### Actualizaciones futuras

La aplicación incluye un sistema de auto-actualización: al abrirse, comprueba automáticamente si hay una versión nueva en GitHub. Si la hay, muestra una notificación en la pantalla principal con la opción de descargar e instalar directamente desde la aplicación.

Para publicar una nueva versión:
1. Se desarrolla en una rama feature/*
2. Se mergea a main tras pasar los tests
3. Se mergea main → production y se crea un tag (ej: v0.2.0)
4. El pipeline de CI/CD genera automáticamente los instaladores y los publica como release en GitHub

---

### Informe de licenciamiento

He preparado un informe completo con análisis de licencias del stack, modelos de negocio, plataformas de venta y estrategia recomendada. Está disponible en:

https://github.com/ferreret/docscan/blob/main/docs/INFORME_LICENCIAMIENTO.md

Quedo pendiente de tus comentarios para tomar decisiones sobre licencia y modelo de distribución.

Un saludo
