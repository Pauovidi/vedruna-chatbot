# Persistence

El core usa `ConversationStore` como fuente de verdad para conversaciones, mensajes, estado, eventos y tool calls.

## Modos

- `memory`: desarrollo/tests cuando no hay `DATABASE_URL` y `APP_ENV` no es `production`.
- `sqlite`: desarrollo local con `DATABASE_URL=sqlite:///./conversation-dev.db`.
- `postgres`: requerido para `APP_ENV=production`.

`APP_ENV=production` sin Postgres durable falla de forma explicita.

## Datos persistidos

- Conversaciones y estado/contexto.
- Mensajes inbound y outbound.
- Eventos redacted.
- Resultados NLU resumidos.
- Acciones de policy resumidas.
- Replies renderizadas.
- Tool calls y resultados redacted.

No se deben guardar secretos en eventos ni tool payloads. La capa de redaccion cubre emails, telefonos y claves con nombres sensibles.

Scheduled tasks V1 viven como capability generica (`core/scheduler`) con store en memoria para tests y patron de dedupe/dry-run. La persistencia durable de esas tareas puede añadirse sobre SQLAlchemy siguiendo el mismo contrato antes de activar envios reales.

## Migraciones

V0.1 usa `metadata.create_all()` para mantener el arranque simple. El layout de modelos esta separado en `core/persistence/models.py` para que Alembic pueda añadirse en V1 sin reescribir los stores.
