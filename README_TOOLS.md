# Tools

Las tools son contratos internos entre la policy y el backend. El NLU/modelo interpreta; la `Conversation Policy Engine` decide si una accion requiere tool; el backend decide si se permite y solo entonces ejecuta.

## Contrato

Cada tool define:

- `name`: identificador interno.
- `description`: objetivo funcional.
- `risk_level`: `low`, `medium`, `high` o `critical`.
- `required_confirmation`: si exige confirmación explícita.
- `required_flags`: flags que deben estar activas.
- `allowed_channels`: canales donde se puede usar.
- `handler`: handler backend que ejecutará la acción.

## Riesgo y confirmación

Acciones informativas suelen ser `low`. Escrituras de CRM, agenda, cancelaciones, cambios de fecha y outbound suelen ser `medium` o `high`. Las acciones de alto riesgo deben requerir confirmación y flags activas.

La definicion backend es la fuente de verdad. Si una peticion contradice `required_confirmation`, `required_flags`, canal permitido o `risk_level`, prevalece la definicion y la tool se bloquea.

## Resultado post-tool

- `blocked`: el copy pide confirmacion, dato faltante o revision; no afirma que la accion se haya hecho.
- `failed`: el copy explica que no se ha podido completar y deriva o reintenta de forma segura.
- `dry_run`: el copy dice que queda como propuesta o pendiente, sin mencionar el termino interno.
- `success`: solo entonces se puede afirmar la accion, si el handler real lo permite.

Los resultados y payloads de tools se registran redacted en persistencia.

## Ejemplo

```yaml
name: confirm_cancellation
description: Confirmar cancelacion de una cita.
risk_level: high
required_confirmation: true
required_flags:
  - appointments_enabled
allowed_channels:
  - whatsapp
  - webchat
handler: appointments_backend
```

## Built-ins V0

- `handoff_to_human`
- `register_timeline_event`
- `set_conversation_mode`
- `reset_conversation_state`
- `mark_priority`
- `search_knowledge`
- `get_business_faq`
- `get_service_info`
- `request_new_appointment_handoff`
- `find_existing_appointment`
- `propose_reschedule_options`
- `confirm_reschedule`
- `confirm_cancellation`
- `find_customer`
- `add_customer_note`
- `flag_customer_review`
- `register_media_handoff`
- `transcribe_audio_stub`
- `send_template_message_stub`
- `send_reminder_stub`

El usuario nunca debe ver nombres técnicos de tools, flags, handlers ni políticas internas.

Adapters de workflow como n8n solo pueden entrar como handlers de tool despues de que `ConversationPolicy` haya producido una `ConversationAction` y la tool policy haya autorizado la ejecucion.
