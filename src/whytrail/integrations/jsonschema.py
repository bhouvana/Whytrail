"""whytrail plugin for jsonschema (ADR 0003).

`ValidationError` already carries `.path` (where in the document),
`.validator`/`.validator_value` (which schema rule failed and what it
required), and `.instance` (the actual value that failed) -- detail
`str(exc)` collapses into a paragraph.

Neither `.message` nor `.instance` is used in `description`,
deliberately: `.message` (e.g. "'not a number' is not of type
'integer'") embeds the offending value directly in its text, the same
leak this plugin's own tests caught in whytrail-pymongo (see that
plugin's module docstring) -- there is no "just use exc.message"
shortcut here either. `description` is built only from `.path`,
`.validator`, and `.validator_value` (schema metadata, not document
data); `.message` and `.instance` both go through `locals` (ADR 0002
§3 item 5).
"""

from __future__ import annotations


import jsonschema

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_validation_error(exc: "jsonschema.ValidationError") -> Explanation:
    path = ".".join(str(part) for part in exc.path) or "<root>"
    description = f"{path}: failed {exc.validator!r} (expected {exc.validator_value!r})"
    steps = [
        ExplanationStep(
            description=description,
            confidence=Confidence.EXPLICIT.value,
            kind="value",
            locals={"message": exc.message, "instance": repr(exc.instance)},
        )
    ]
    return Explanation(subject=f"{path}: failed {exc.validator!r}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(jsonschema.ValidationError, _explain_validation_error)
