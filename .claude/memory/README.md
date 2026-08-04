# Memoria de proyecto versionada

Instantánea del contexto acumulado entre sesiones de Claude Code, versionada en
el repo para que cualquier equipo (Linux, Windows) arranque con el mismo
histórico.

## Por qué existe

La memoria nativa de Claude Code vive **fuera del repo**, en un directorio local
por máquina:

```
~/.claude/projects/<slug-de-la-ruta-del-proyecto>/memory/
```

El slug deriva de la ruta absoluta del proyecto, así que ni siquiera copiándolo
a mano coincide entre máquinas: en Linux es
`-media-nicolas-DATA-Tecnomedia-DocScan` y en Windows sería otro distinto. Sin
esta copia, un equipo nuevo empieza sin saber nada de las decisiones ya
cerradas, los bugs conocidos ni las preferencias de trabajo.

## Cómo se usa

`CLAUDE.md` referencia este directorio, así que Claude lo carga al arrancar.
Empieza siempre por `MEMORY.md`, que es el índice; el resto de ficheros son una
entrada cada uno y se enlazan entre sí con `[[nombre]]`.

## Cómo se mantiene sincronizado

Esta copia **no se actualiza sola**. Al cerrar una sesión en la que se haya
escrito o modificado memoria:

```bash
cp ~/.claude/projects/<slug>/memory/*.md .claude/memory/
```

Revisa el diff antes de commitear (ver aviso de credenciales abajo) y súbelo con
el resto del trabajo.

En sentido inverso, en una máquina nueva se puede sembrar la memoria nativa
copiando estos ficheros al directorio local correspondiente.

## ⚠️ El repo es público

Antes de commitear cualquier actualización de esta carpeta, comprueba que no
entran credenciales:

```bash
grep -rniE "password|secret|token|api[_-]?key|\\\$2b\\\$" .claude/memory/
```

En el volcado inicial se redactaron las contraseñas de la BD docker del proyecto
web archivado (marcadas como `<REDACTADO>`). Los valores reales están en el
gestor de contraseñas, no aquí.
