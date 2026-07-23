# Vedruna Domain Schema

## Clinics

- `madre_vedruna`: Clinica Madre Vedruna, Madre Vedruna 14, bajo derecha, telefono `976795117`.
- `santa_isabel`: Clinica Santa Isabel, Avenida Santa Isabel numero 82, local, 50016 Zaragoza, telefono `976582768`.

WhatsApp y voz comparten el mismo `client_id=vedruna` y el mismo pipeline central.

## Hours

- Madre Vedruna: martes y jueves 09:30-13:30 y 15:30-19:30; viernes 09:00-17:00.
- Santa Isabel: lunes y miercoles 09:30-13:30 y 15:30-19:30.

## Services

- Ambas sedes: `podologia`, `quiropodia`, `estudio_biomecanico`, `infiltracion`,
  `ecografia`, `otro_problema`.
- `traumatologia` y `psicologia` no se citan desde el asistente.

Duracion:

- General: 20 minutos.
- `estudio_biomecanico`: 30 minutos.

## Insurance

- Madre Vedruna requiere `Sanitas`, `Catalana Occidente` o `particular`.
- Santa Isabel es solo particular; no se pregunta seguro.
- No se pide numero de poliza ni tarjeta.

## Required booking slots

- `clinic`
- `service`
- `patient_first_name`
- `patient_last_names`
- `patient_phone`
- `consultation_reason`
- `date_preference`
- `insurance_type` solo para Madre Vedruna
- `selected_slot_id` devuelto/ofrecido por RPA antes de crear

## Intents

Implementados en el NLU determinista Vedruna:

- `greeting`
- `book_appointment`
- `choose_clinic`
- `choose_service`
- `provide_insurance`
- `provide_patient_name`
- `provide_patient_phone`
- `provide_date_preference`
- `select_slot`
- `cancel_appointment`
- `reschedule_appointment`
- `recall_appointment`
- `faq_hours`
- `faq_location`
- `faq_services`
- `price_query`
- `insurance_question`
- `unsupported_specialty`
- `urgent_request`
- `human_handoff`
- `correction`
- `unknown`

## State equivalents

The core keeps generic state fields and the Vedruna adapter maps them as:

- `vedruna_appointment`: awaiting clinic/service/insurance/patient/date/slot/create.
- `vedruna_cancellation`: lookup and cancellation confirmation.
- `vedruna_reschedule`: lookup and future reschedule flow.
- `vedruna_recall`: appointment lookup.

`tool_state.last_offered_slots` stores the last RPA availability options so voice DTMF or "la primera" can map to a real `slot_id`.
