"""loguru: every logged exception gains a whytrail explanation
appended to the message, reaching whatever sink(s) you already
configured.

Run: python examples/ex_loguru.py
Needs: pip install whytrail[loguru]
"""

from __future__ import annotations

from whytrail.integrations import loguru as whytrail_loguru


def load_codes(region: str) -> dict[str, float]:
    table: dict[str, float] = {}
    if region not in table:
        raise ValueError(f"discount code table missing region {region!r}")
    return table


def main() -> None:
    logger = whytrail_loguru.install()  # locals redacted by default

    try:
        load_codes("EU")
    except ValueError:
        logger.exception("failed to load discount codes")


if __name__ == "__main__":
    main()
