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


def test_a_builtin_explainer_actually_registers_and_wins_over_tier_1():
    """Regression guard for a real bug this project shipped and caught
    within the same session: _load_builtin_explainers() silently
    swallowed a NameError via its own `except Exception: continue`
    (a deliberately broad catch for a *missing extra*, not for a typo
    in registry.py itself), so every built-in explainer quietly
    stopped registering and every plugin_contract test still needed a
    real, separately-installed library to catch it. `requests` is a
    real dev dependency here, so this exercises the actual
    import-and-register path end to end, not a mock of it."""
    import requests

    try:
        raise requests.exceptions.RequestException("boom")
    except requests.exceptions.RequestException as exc:
        explanation = whytrail.why(exc)
    # requests' own explainer adds method/URL detail Tier 1 can't --
    # if this ever reads like a bare Tier 1 "RequestException: boom"
    # again, the builtin-explainer load path is broken again.
    assert "raised as RequestException" in explanation.text


def test_list_builtin_plugins_reports_a_real_dev_dependency_as_available():
    statuses = registry.list_builtin_plugins()
    by_name = {p.name: p for p in statuses}
    assert by_name["requests"].available is True
    assert all(p.kind == "explainer" for p in statuses)


def test_list_builtin_plugins_reports_a_never_installed_library_as_unavailable():
    statuses = registry.list_builtin_plugins()
    by_name = {p.name: p for p in statuses}
    assert by_name["zeep"].available is False  # not a dev dependency of this project


def test_list_hook_based_plugins_covers_the_non_explainer_integrations():
    statuses = registry.list_hook_based_plugins()
    names = {p.name for p in statuses}
    assert "fastapi" in names
    assert "django" in names
    assert all(p.kind == "integration" for p in statuses)
    # the two lists partition the 63 integrations, not overlap with each other
    assert names.isdisjoint({p.name for p in registry.list_builtin_plugins()})


def test_every_hook_based_integration_has_an_underlying_import_mapped():
    # Prevents a future integration from being added to
    # _HOOK_BASED_INTEGRATIONS without a matching entry in
    # _HOOK_BASED_UNDERLYING_IMPORT, which would KeyError inside
    # list_hook_based_plugins() the moment it's called.
    assert set(registry._HOOK_BASED_INTEGRATIONS) == set(registry._HOOK_BASED_UNDERLYING_IMPORT)


def test_list_hook_based_plugins_does_not_trust_the_wrapper_module_alone(monkeypatch):
    # bugsnag.py (like several other hook-based integrations) imports its
    # real dependency lazily inside a function body, so
    # `whytrail.integrations.bugsnag` itself imports cleanly whether or
    # not the real `bugsnag` package is installed. availability must be
    # keyed off the real underlying import, not the wrapper module --
    # simulated here by pointing the mapping at a package that can never
    # exist, independent of whether the real `bugsnag` happens to be
    # installed in this dev environment.
    monkeypatch.setitem(registry._HOOK_BASED_UNDERLYING_IMPORT, "bugsnag", "definitely_not_a_real_package_xyz")
    statuses = registry.list_hook_based_plugins()
    by_name = {p.name: p for p in statuses}
    assert by_name["bugsnag"].available is False


def test_list_entry_point_plugins_returns_a_sorted_list_of_names():
    names = registry.list_entry_point_plugins()
    assert names == sorted(names)
