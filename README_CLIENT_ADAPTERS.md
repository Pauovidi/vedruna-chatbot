# Client Adapters

Un adaptador de cliente define cómo se comporta el core para un negocio concreto sin modificar el núcleo.

La autoridad conversacional sigue dentro del core:

- NLU interpreta.
- `StateReducer` actualiza contexto.
- `ConversationPolicy` decide `ConversationAction`.
- `CopyRenderer` redacta.
- Tools/adapters ejecutan solo despues de autorizacion.

Un adapter de cliente no debe renderizar copy visible por fuera ni mantener un estado paralelo que compita con el store principal.

Las reglas hardcodeadas actuales para `mudanzas_example` y `somos_perros_example` son scaffolding de V0.1 para golden tests, no el patron final de produccion. Al crear un adapter real, extrae la logica especifica a extensiones de reducer/policy sin romper el circuito `NLUResult -> StateReducer -> ConversationAction -> CopyRenderer`.

Usa `docs/ADAPTER_TEMPLATE.md` como plantilla base para nuevos clientes. Incluye pending fields, slot targeting, terms gate, scheduled tasks, preview-only templates, human handoff y channel adapters via Outbox.

## Archivos

- `business_profile.yaml`: nombre del agente, tono, objetivo y datos esperados.
- `system_prompt.md`: instrucciones específicas del negocio.
- `tools.yaml`: tools declarativas disponibles para ese cliente.
- `knowledge_seed.json`: conocimiento semilla anonimizable.
- `golden_tests.yaml`: casos conversacionales críticos.

## Manosalbas

Crear un adaptador propio solo con datos aprobados y anonimizados. No copiar teléfonos, credenciales, prompts privados ni historiales reales. Las tools de agenda o CRM deben requerir flags y confirmación cuando escriban o modifiquen citas.

## Mudanzas

Partir de `clients/mudanzas_example`. Añadir cálculo o creación de lead como handler backend real cuando exista CRM. Mantener la regla de no inventar precios ni disponibilidad.

## Somos Muy Perros

Partir de `clients/somos_perros_example`. Añadir consulta real de disponibilidad y propuesta de reserva como handlers. Mantener la regla de no confirmar plaza sin resultado real.

## Golden suites

Cada cliente debe cubrir saludos, continuidad, preguntas frecuentes, enfado, privacidad, acciones críticas y huecos de datos. Las golden suites son ejecutables con `python -m core.testing.golden_runner` y son la defensa principal contra regresiones de tono y comportamiento.

Mudanzas y Somos Muy Perros en este repo son ejemplos, no integraciones reales. No conectan CRM, calendario, pagos ni disponibilidad real.

## n8n

n8n puede usarse como workflow adapter externo para tareas como crear lead, enviar email, actualizar una hoja, consultar un backend o notificar a una persona. No es el orquestador conversacional: no decide acciones, no redacta copy final, no mantiene estado principal y no puede saltarse confirmaciones o flags.
