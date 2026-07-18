"""pytest: a failing assertion on a track()ed value shows its own
derivation history, not just "assert 12.5 == 999".

Run: pytest examples/ex_pytest_tracked_values.py -v
Needs: pip install whytrail[pytest]

This test is expected to fail -- that's the point. Compare the
"whytrail" section's two extra "was separately track()ed" blocks
against what a bare assertion failure shows: Tier 1 (the exception
explanation) never consults the provenance graph by design (ADR
0008), so without this, a track()ed value that fails an assertion
only ever explains "AssertionError here," never where the value
actually came from.
"""

from __future__ import annotations

import whytrail


def test_price_calculation() -> None:
    with whytrail.trace():
        raw = whytrail.track({"price": "12.50"}, label="raw CSV row")
        price = whytrail.track(float(raw["price"]), derived_from=raw)
        assert price == 999  # deliberately wrong -- see the "whytrail" section on failure
