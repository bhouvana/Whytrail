"""pytest: whytrail explains a failure automatically -- no code changes
needed beyond `pip install whytrail[pytest]`.

Run: pytest examples/ex_pytest_fixtures.py -v
Needs: pip install whytrail[pytest]

This test is expected to fail -- that's the point. Look at the
"whytrail" section pytest prints alongside the normal failure output.

The whytrail integration registers itself via pytest's own pytest11
entry-point group the moment the extra is installed; the test below is
ordinary pytest, nothing whytrail-specific in it. This fails during
fixture setup, not at the test's own assertion -- exactly the case a
bare traceback is weakest for, and exactly the case a "whytrail"
section on the failure report (with locals, since this runs locally,
not over HTTP) is for.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def discount_table() -> dict[str, float]:
    return {"US": 0.10, "UK": 0.15}  # no "EU" entry -- the bug this demo hits


@pytest.fixture
def price(discount_table: dict[str, float]) -> float:
    region = "EU"
    rate = discount_table[region]  # KeyError: 'EU' -- three calls upstream from the assertion
    return round(19.99 * (1 - rate), 2)


def test_eu_discount_is_applied(price: float) -> None:
    assert price < 19.99
