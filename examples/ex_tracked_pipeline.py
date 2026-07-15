"""Tier 2: opt-in, scoped provenance for a small data pipeline.

Run: python examples/ex_tracked_pipeline.py
"""

from __future__ import annotations

import whytrail


@whytrail.tracked
def parse_price(raw: str) -> float:
    return float(raw)


@whytrail.tracked
def apply_tax(price: float, rate: float) -> float:
    return round(price * (1 + rate), 2)


def main() -> None:
    with whytrail.trace():
        raw_row = whytrail.track({"price": "19.99", "region": "EU"}, label="CSV row 42")
        price = parse_price(raw_row["price"])
        total = apply_tax(price, 0.20)

    print(f"total = {total}")
    print()
    print(whytrail.why(total))
    print()
    print(whytrail.why(total).graph())


if __name__ == "__main__":
    main()
