# RPA Appointments Contract - Vedruna

## Environment

```env
RPA_BASE_URL=https://vedruna-rpa-rpa.ddxo6v.easypanel.host
RPA_API_KEY=
RPA_DRY_RUN=true
RPA_LIVE_READS_ENABLED=false
RPA_TIMEOUT_MS=12000
```

`RPA_DRY_RUN=true` is the default and suppresses real create/cancel/reschedule writes.
`RPA_LIVE_READS_ENABLED=true` may be combined with dry-run mode to consult real
availability while keeping every appointment write suppressed.

## Auth

When `RPA_API_KEY` is set and `RPA_DRY_RUN=false`, the client sends:

```http
Authorization: Bearer <RPA_API_KEY>
Content-Type: application/json
```

Secrets must not be logged or committed.

## Health

```http
GET /health
```

Health is public and does not require auth.

## Real APClinic endpoints

### Search availability

```http
POST /appointments/availability/search
```

Real request:

```json
{
  "date": "08/07/2026",
  "preference": "todos",
  "limit": 4,
  "emergencia": false
}
```

The internal adapter normalizes the real response:

```json
{
  "ok": true,
  "dry_run": false,
  "date": "08/07/2026",
  "dateISO": "2026-07-08",
  "dateReadable": "miercoles, 8 de julio",
  "slots": [
    {
      "slot_id": "2026-07-08T12:30",
      "date": "08/07/2026",
      "dateISO": "2026-07-08",
      "time": "12:30",
      "start": "2026-07-08T12:30:00+02:00",
      "clinic": "santa_isabel",
      "service": "quiropodia",
      "address": "Avenida Santa Isabel numero 82, local, 50016 Zaragoza"
    }
  ]
}
```

### Create appointment

```http
POST /appointments/create
```

The adapter sends `name`, `phone`, `date`, `time`, `type`, `observaciones`, and
`is_new_patient=true` unless a known-patient flow explicitly says otherwise. The
deployed APClinic RPA prepends `CITA IA - ` to `observaciones`, so the adapter
sends the agenda body `{nombre} {apellidos} {telefono} {motivo}` without a
second prefix. For insurance:

- Sanitas -> `mutua=true`, `idMutua=1`
- Generali -> `mutua=true`, `idMutua=12`

TODO: confirm with clinic/RPA whether Generali maps to OCCIDENT id `12`.

Visible confirmation is allowed only if the normalized result has:

```json
{
  "ok": true,
  "dry_run": false
}
```

The normalized result also models the WhatsApp reminder 24h before the appointment.

### Find appointment

```http
POST /appointments/find
```

The adapter sends `phone` and optional `date`/`time`, then normalizes `idCita` to `appointment_id` and keeps both fields.

### Cancel appointment

```http
POST /appointments/cancel
```

The adapter sends:

```json
{
  "idCita": "52549",
  "phone": "600000001"
}
```

Cancellation requires previous lookup and explicit conversational confirmation.

### Reschedule appointment

```http
POST /appointments/reschedule
```

The adapter sends `idCita`, `name`, `phone`, `date`, `time` and `type`. Reagendado requires previous lookup, new availability and selected new slot.

## Error handling

- HTTP, timeout or invalid JSON -> `failed/rpa_http_error`.
- Missing required fields -> `failed/rpa_missing_required_fields`.
- Real `success` not true -> `failed/rpa_not_ok`.
- Dry-run writes -> `dry_run/dry_run_write_suppressed`.

No RPA failure may produce appointment confirmation copy.
