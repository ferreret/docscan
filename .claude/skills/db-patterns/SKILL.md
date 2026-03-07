---
name: db-patterns
description: Patrones de SQLAlchemy 2.x y SQLite para DocScan Studio. Usar siempre que se toque database.py, repositorios, modelos ORM o migraciones.
---

## WAL mode — OBLIGATORIO en engine creation
```python
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
```

## Session pattern
Usar context manager siempre, nunca session global:
```python
with Session(engine) as session:
    with session.begin():
        session.add(obj)
```

## Repositorios
Un repositorio por entidad (BatchRepository, PageRepository, AppRepository).
Reciben Session por parámetro, no la crean internamente.

## Antipatrones prohibidos
- SQLite sin WAL (corrupción con DocScanWorker concurrente)
- API keys en texto plano en BD (usar cryptography Fernet)
- Session como atributo de clase (no thread-safe)