# Golden Flows Vedruna

Covered by automated tests:

- Greeting includes both clinics and excludes the inherited voice-name errata.
- Booking without clinic asks Madre Vedruna or Santa Isabel.
- Madre Vedruna asks insurance for any supported service.
- Santa Isabel offers the same services and does not ask insurance.
- Santa Isabel plus Sanitas explains particular-only rule.
- Price query gives clinic phone and no amount.
- Full WhatsApp booking reaches RPA availability and then suppresses real create in dry-run.
- ConversationRelay setup uses voice greeting.
- Voice price with clinic triggers transfer.
- DTMF `1` selects the first offered slot.
- Fuzz phrases remain safe for clinic changes, insurance corrections, price, human request, cancellation and recall.
- RPA create in dry-run does not confirm a real appointment.

Run:

```bash
python -m pytest tests/golden tests/fuzz tests/guardrails tests/tools tests/channels tests/test_vedruna_latency.py -q
python -m core.testing.golden_runner
```
