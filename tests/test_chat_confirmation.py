from core.adapters.vedruna.channels.confirmation import is_explicit_confirmation


def test_explicit_confirmation_accepts_only_clear_phrases() -> None:
    assert is_explicit_confirmation("Sí, confirmo")
    assert is_explicit_confirmation("Confirmo")
    assert is_explicit_confirmation("Sí, confirmo la cancelación")
    assert is_explicit_confirmation("Confirmo que quiero cancelarla")
    assert not is_explicit_confirmation("Creo que sí")
    assert not is_explicit_confirmation("Tal vez")
