# Conversation Latency Runbook

## Target

Voice should start a spoken response in under 1200 ms when no slow external tool is needed.

## Measured stages

AuthorityTurnTrace records:

- `loadStateMs`
- `nluTotalMs`
- `nluProviderMs`
- `deterministicParserMs`
- `reducerMs`
- `policyMs`
- `toolsMs`
- `rendererMs`
- `persistenceMs`
- `eventLogMs`
- `outboxMs`
- `totalDurationMs`

## Vedruna expectations

- Deterministic NLU is the default when no `OPENAI_API_KEY` is set.
- RPA calls have `RPA_TIMEOUT_MS=12000`.
- Slow RPA must not cause fake confirmation.
- If RPA fails or times out, renderer uses safe failure copy.

## Local smoke

```bash
python -m pytest tests/test_vedruna_latency.py -q
python -m core.testing.latency_smoke
```

Inspect `authority_turn_timing_completed` events for stage timings.

## Regression rule

Do not reduce latency by bypassing:

- StateReducer
- Policy
- ToolExecutor
- CopyRenderer
- RPA success requirement

