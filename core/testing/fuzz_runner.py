from __future__ import annotations

from dataclasses import dataclass

from core.llm.schemas import IncomingMessage
from core.nlu.deterministic_interpreter import DeterministicNLUInterpreter


@dataclass(frozen=True)
class FuzzCase:
    text: str
    expected_intent: str | None = None
    expected_global_intent: str | None = None


FUZZ_CASES = [
    FuzzCase("si", expected_intent="general"),
    FuzzCase("sí por favor", expected_intent="general"),
    FuzzCase("no quiero seguir", expected_intent="cancel_or_stop_flow"),
    FuzzCase("solo informacion", expected_intent="information_only"),
    FuzzCase("no quiero reserva", expected_intent="cancel_or_stop_flow"),
    FuzzCase("mañana a las 10", expected_intent="general"),
    FuzzCase("pasado mañana", expected_intent="general"),
    FuzzCase("a las 10", expected_intent="general"),
    FuzzCase("same time", expected_intent="general"),
    FuzzCase("tambien a la misma hora", expected_intent="general"),
    FuzzCase("me faltan 8, no una", expected_intent="correction"),
    FuzzCase("quiero hablar con una persona", expected_global_intent="handoff"),
    FuzzCase("activar bot", expected_intent="general"),
    FuzzCase("cuanto cuesta?", expected_global_intent="faq"),
]


def run_fuzz_cases(cases: list[FuzzCase] | None = None) -> list[dict[str, str | None]]:
    interpreter = DeterministicNLUInterpreter()
    results: list[dict[str, str | None]] = []
    for index, case in enumerate(cases or FUZZ_CASES):
        result = interpreter.interpret(
            IncomingMessage(conversation_id=f"fuzz-{index}", text=case.text),
            {},
            [],
            [],
        )
        if case.expected_intent is not None:
            assert result.intent == case.expected_intent, (case.text, result.intent)
        if case.expected_global_intent is not None:
            assert result.global_intent == case.expected_global_intent, (
                case.text,
                result.global_intent,
            )
        results.append(
            {
                "text": case.text,
                "intent": result.intent,
                "global_intent": result.global_intent,
            }
        )
    return results


def main() -> None:
    results = run_fuzz_cases()
    print(f"fuzz cases passed: {len(results)}")


if __name__ == "__main__":
    main()
