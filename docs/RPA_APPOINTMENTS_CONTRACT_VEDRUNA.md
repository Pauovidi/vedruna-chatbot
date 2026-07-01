# RPA Appointments Contract - Vedruna

## Environment

```env
RPA_BASE_URL=http://vedruna-rpa:8080
RPA_API_KEY=
RPA_DRY_RUN=true
RPA_TIMEOUT_MS=12000
```

`RPA_DRY_RUN=true` is the default and suppresses real create/cancel/reschedule writes.

## Auth

When `RPA_API_KEY` is set and `RPA_DRY_RUN=false`, the client sends:

```http
Authorization: Bearer <RPA_API_KEY>
Content-Type: application/json
```

Secrets must not be logged or committed.

## Endpoints expected

### Search availability

```http
POST /availability/search
```

Input:

```json
{
  "clinic": "madre_vedruna",
  "service": "podologia",
  "duration_minutes": 20,
  "date_preference": "tuesday",
  "time_preference": "morning",
  "conversation_id": "conv-123"
}
```

Output:

```json
{
  "ok": true,
  "slots": [
    {
      "slot_id": "rpa-slot-1",
      "start": "2026-07-07T10:00:00+02:00",
      "end": "2026-07-07T10:20:00+02:00",
      "clinic": "madre_vedruna",
      "address": "Madre Vedruna 14, bajo derecha"
    }
  ]
}
```

### Create appointment

```http
POST /appointments
```

Input includes patient data, selected `slot_id`, insurance where needed, `conversation_id` and `idempotency_key`.

Visible confirmation is allowed only on `ok=true` and non-dry-run success.

### Find appointment

```http
POST /appointments/find
```

Used by recall, cancellation and reschedule.

### Cancel appointment

```http
POST /appointments/cancel
```

Requires previous lookup and explicit conversational confirmation.

### Reschedule appointment

```http
POST /appointments/reschedule
```

Requires previous lookup, new availability and selected new slot.

### Schedule reminder

```http
POST /reminders
```

Scheduled only after successful create. It is always WhatsApp and 24 hours before the appointment.

## Error handling

- HTTP, timeout or invalid JSON -> `failed/rpa_http_error`.
- `ok=false` -> `failed/<error_code or rpa_not_ok>`.
- Dry-run writes -> `dry_run/dry_run_write_suppressed`.

No RPA failure may produce appointment confirmation copy.

