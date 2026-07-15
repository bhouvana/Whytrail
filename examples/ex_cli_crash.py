def load_codes(region):
    table = {}
    if region not in table:
        raise ValueError(f"discount code table missing region {region!r}")
    return table


def apply_discount(price, code):
    try:
        load_codes("EU")
    except ValueError as exc:
        raise KeyError(code) from exc


apply_discount(12.5, "SUMMER")
