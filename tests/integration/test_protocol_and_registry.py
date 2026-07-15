from __future__ import annotations

import whytrail
from whytrail import registry
from whytrail.core.explanation import Explanation


def test_why_dunder_protocol_string_result():
    class Money:
        def __init__(self, cents):
            self.cents = cents

        def __why__(self):
            return f"{self.cents} cents, straight from the ledger"

    explanation = whytrail.why(Money(500))
    assert explanation.known
    assert "500 cents" in explanation.text


def test_why_dunder_protocol_explanation_result():
    class Money:
        def __why__(self):
            return Explanation(subject="money", steps=[], tracked=True)

    explanation = whytrail.why(Money())
    assert explanation.subject == "money"


def test_why_dunder_that_raises_falls_through_to_unknown():
    class Hostile:
        def __why__(self):
            raise RuntimeError("nope")

    explanation = whytrail.why(Hostile())
    assert explanation.known is False


def test_why_dunder_with_bad_return_type_falls_through():
    class Weird:
        def __why__(self):
            return 12345  # not an Explanation or str

    explanation = whytrail.why(Weird())
    assert explanation.known is False


def test_register_makes_untracked_type_explainable():
    class Coupon:
        def __init__(self, code):
            self.code = code

    whytrail.register(Coupon, lambda c: f"coupon {c.code} from the promo table")
    explanation = whytrail.why(Coupon("SAVE10"))
    assert "SAVE10" in explanation.text


def test_register_resolves_via_mro():
    class Base:
        pass

    class Derived(Base):
        pass

    whytrail.register(Base, lambda obj: "explained via base class")
    explanation = whytrail.why(Derived())
    assert "explained via base class" in explanation.text


def test_manual_register_overrides_registered_plugin_explainer():
    class Widget:
        pass

    registry.register_from_plugin(Widget, lambda w: "from a plugin")
    whytrail.register(Widget, lambda w: "from the user, wins")

    explanation = whytrail.why(Widget())
    assert "wins" in explanation.text


def test_register_from_plugin_does_not_override_existing_manual_registration():
    class Widget:
        pass

    whytrail.register(Widget, lambda w: "manual wins")
    registry.register_from_plugin(Widget, lambda w: "plugin loses")

    explanation = whytrail.why(Widget())
    assert "manual wins" in explanation.text


def test_broken_registered_explainer_falls_through_to_unknown():
    class Bomb:
        pass

    def boom(obj):
        raise RuntimeError("explainer itself is broken")

    whytrail.register(Bomb, boom)
    explanation = whytrail.why(Bomb())
    assert explanation.known is False
