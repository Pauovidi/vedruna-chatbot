from core.adapters.vedruna.domain_schema import normalize_date_preference


def test_normalize_date_preference_accepts_exact_dates() -> None:
    assert normalize_date_preference("el 30/7/2026") == "30/07/2026"
    assert normalize_date_preference("2026-07-30") == "2026-07-30"
    assert normalize_date_preference("31/02/2026") is None


def test_normalize_date_preference_distinguishes_next_occurrence() -> None:
    assert normalize_date_preference("jueves") == "thursday"
    assert normalize_date_preference("el proximo jueves") == "next:thursday"
    assert (
        normalize_date_preference("el jueves de la semana que viene")
        == "next_week:thursday"
    )
    assert normalize_date_preference("manana") == "relative_tomorrow"
