# Conversation Policy Authority

La autoridad unica de conversacion es `ConversationPolicy`.

## Reglas

- NLU interpreta, pero no decide la respuesta visible.
- State reducer actualiza contexto, pero no redacta copy.
- Policy decide `ConversationAction`.
- Tool executor ejecuta solo si `ConversationAction` lo requiere y la tool policy lo permite.
- Copy renderer redacta solo desde `ConversationAction`.
- Guardrails finales bloquean lenguaje interno visible.
- `OpenAIProvider.decide()` legacy esta bloqueado y lanza error; no debe usarse para copy.

## Lenguaje interno prohibido

El usuario no debe ver terminos como `red flag`, `handoff`, `intent`, `confidence`, `required_flags`, `risk_level`, `dry_run`, `policy`, `state reducer` o `NLU`.

## Derivacion visible

Si la policy decide derivar a una persona, debe existir una respuesta visible salvo que la conversacion ya este en `mode=human`; en ese caso se persiste inbound y se registra `human_mode_suppressed`.

## Anti-loop

El core conserva `last_reply_key` y `recent_reply_keys`. Si el usuario corrige o insiste y la policy iria a repetir la misma respuesta, cambia estrategia con una aclaracion, cancelacion de flujo o derivacion visible.

## Extensiones por vertical

V0.1 mantiene reglas simples para `mudanzas_example` y `somos_perros_example` dentro de `ConversationPolicy` solo como ejemplos ejecutables. No es el diseño final para produccion por cliente.

Para V0.2/V1, una vertical debe ampliarse asi:

1. NLU sigue devolviendo `NLUResult`.
2. El reducer vertical puede enriquecer `collected_info` y contexto, pero no redacta copy.
3. La policy vertical puede producir `ConversationAction`, pero no ejecuta tools ni responde directamente.
4. El renderer sigue siendo la unica salida visible.
5. Cualquier adapter externo se ejecuta como tool autorizada y se reconcilia antes del copy final.

## Bypass Check

Ejecuta:

```bash
python -m core.tools.check_conversation_authority
```

Este check falla si reaparecen rutas practicas de copy visible fuera del renderer, sends directos fuera de Outbox o APIs legacy de decision LLM-visible.
