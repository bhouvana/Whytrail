"""whytrail's flagship feature: install() once, and every uncaught
exception in this process shows the causal chain automatically,
followed by the original traceback (preserved, not replaced).

Run: python examples/ex_install_hook.py
Needs: nothing extra -- built entirely on Tier 1 (core whytrail).

This script is expected to crash -- that's the point. Compare the
"why(...)" summary at the top of the output to the traceback below it:
same information CPython already retained, surfaced automatically
instead of requiring a manual why(exc) call.
"""

from __future__ import annotations

import whytrail

whytrail.install()


def load_codes(region: str) -> dict[str, float]:
    table: dict[str, float] = {}
    if region not in table:
        raise ValueError(f"discount code table missing region {region!r}")
    return table


def apply_discount(price: float, code: str) -> float:
    try:
        load_codes("EU")
    except ValueError as exc:
        raise KeyError(code) from exc
    return price  # unreachable in this demo


if __name__ == "__main__":
    apply_discount(12.5, "SUMMER")
