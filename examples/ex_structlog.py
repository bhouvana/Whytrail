"""structlog: every logged exception gains a structured `why` key in
the event dict, ready for a JSON renderer or a log aggregator.

Run: python examples/ex_structlog.py
Needs: pip install whytrail[structlog]
"""

from __future__ import annotations

import structlog

from whytrail.integrations import structlog as whytrail_structlog


def load_codes(region: str) -> dict[str, float]:
    table: dict[str, float] = {}
    if region not in table:
        raise ValueError(f"discount code table missing region {region!r}")
    return table


def main() -> None:
    structlog.configure(
        processors=[
            whytrail_structlog.add_whytrail_explanation(),  # must run before format_exc_info
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(indent=2),
        ]
    )
    log = structlog.get_logger()

    try:
        load_codes("EU")
    except ValueError:
        log.exception("failed to load discount codes")


if __name__ == "__main__":
    main()
