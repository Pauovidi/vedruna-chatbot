# Conversation Panel Status - Vedruna

## Current status

Panel status: partial.

This repository currently provides the conversational API, persistence models and event storage needed to feed a panel. It does not include an operational panel UI.

## Data already available

| Data | Source |
| --- | --- |
| Conversation state | `conversations.state` via `core/persistence/sqlalchemy_store.py` |
| Messages | `messages` table and `ConversationStore.list_messages()` |
| Events | `events` table and `ConversationStore.list_events()` |
| Tool calls | `tool_calls` table and `ConversationStore.record_tool_call()` |
| Safe health/readiness | `GET /healthz` |

## Missing for an operational panel

- Authenticated admin API endpoints.
- Admin UI.
- Pagination and search over conversations.
- Human/bot mode controls with audit trail.
- Role-based access and secret-safe logging policy.

## Minimum safe next step

Add a read-only admin API protected by `ADMIN_PANEL_API_KEY`:

- `GET /admin/conversations`
- `GET /admin/conversations/{conversation_id}`

Only add mode-changing endpoints after a reviewed safety design. A `POST /admin/conversations/{conversation_id}/mode` endpoint should remain out of scope until bot/human transitions have explicit authorization, audit logging and tests.

## Production recommendation

Use this repo as the API/data source for now. Connect an external panel or add the read-only API first; do not ship a large UI in the same production activation step.
