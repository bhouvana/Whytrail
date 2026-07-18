"""stdlib logging: every logged exception gains a whytrail explanation
automatically, on whatever handlers are already configured.

Run: python examples/ex_logging.py
Needs: nothing extra -- whytrail.integrations.logging has no
third-party dependency.
"""

from __future__ import annotations

import logging

from whytrail.integrations import logging as whytrail_logging


def load_codes(region: str) -> dict[str, float]:
    table: dict[str, float] = {}
    if region not in table:
        raise ValueError(f"discount code table missing region {region!r}")
    return table


def main() -> None:
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    whytrail_logging.install()  # root logger, locals redacted by default

    try:
        load_codes("EU")
    except ValueError:
        logging.exception("failed to load discount codes")


if __name__ == "__main__":
    main()
