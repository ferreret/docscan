---
name: Plan versión web DocScan Studio (revisado)
description: Plan revisado para versión web SaaS — stack simplificado, dos modos de despliegue, agente local
type: project
---

Plan de versión web SaaS de DocScan Studio, revisado el 2026-04-07 (original 2026-03-27).

**Why:** Ampliar DocScan de app desktop mono-estación a plataforma web multi-empresa con gestión de usuarios. Soportar despliegue on-premise y cloud.

**How to apply:** El plan detallado está en `/home/nicolas/.claude/plans/polished-riding-mist.md`. Empezar creando rama `feature/web` desde main.

## Stack revisado (cambios vs original)
- Backend: FastAPI (sin cambio)
- Frontend: Vue 3 + Vite + TypeScript + Tailwind CSS + Pinia (sin cambio)
- Auth: **JWT custom con python-jose** (antes: Supabase Auth) — control total multi-tenancy
- Storage: **MinIO en Docker** (antes: no especificado) — gratuito, API S3-compatible
- Task queue: **ARQ + Redis** (antes: Celery + Redis) — más ligero, async-nativo
- Database: **PostgreSQL + asyncpg directo** (antes: Supabase) — sin vendor lock-in
- Realtime: **FastAPI WebSocket** (antes: no especificado)
- Scripts multi-tenant: **RestrictedPython + subprocess** (antes: no contemplado)
- Escáner: **Agente local = docscan_worker + mini FastAPI** (reutiliza código existente)
- Despliegue: **Docker Compose con overrides** para on-premise y cloud

## Cambios clave vs plan original
1. Eliminado Supabase completamente (vendor lock-in innecesario)
2. Celery → ARQ (sobredimensionado para pipeline síncrono)
3. Reestructura a docscan_core como paquete compartido (desktop + web + worker)
4. Sandboxing de scripts añadido (crítico en cloud multi-tenant)
5. MVP reducido (excluye configurador drag-and-drop, AI Mode, editor scripts web)
6. Dos modos despliegue: on-premise (transferencias directas) y cloud (vía agente local)

## Reutilización: ~85% del código Python existente
