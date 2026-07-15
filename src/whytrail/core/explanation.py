"""The result type every why() call returns -- one model, several
renderings (ADR §05)."""

from __future__ import annotations

import dataclasses
import re
import typing as t

from .node import Confidence, Edge, Node

_STYLES = {
    Confidence.EXPLICIT.value: "bold",
    Confidence.INFERRED.value: "yellow",
    Confidence.HEURISTIC.value: "dim yellow",
}

# Plain-English glosses for common builtin exceptions, used only by
# .plain_text (0.2.1). Deliberately a small, honestly-scoped list: this
# is paraphrase, not inference -- KeyError really does mean "looked up
# something that wasn't there" for every KeyError, so glossing it adds
# no uncertainty. An exception type not in this table just keeps its
# own name rather than getting a guessed-at description; ADR §11's
# "never fabricate" applies to prose phrasing exactly as much as it
# applies to the causal chain itself.
_EXCEPTION_GLOSS = {
    "KeyError": "tried to look up something that wasn't there",
    "ValueError": "got a value that didn't make sense for what it was doing",
    "TypeError": "tried to use the wrong type of value",
    "AttributeError": "tried to use a property or method that doesn't exist on that object",
    "IndexError": "tried to access a position in a list that doesn't exist",
    "FileNotFoundError": "tried to open a file that doesn't exist",
    "NotADirectoryError": "expected a folder but got a file instead",
    "IsADirectoryError": "expected a file but got a folder instead",
    "ZeroDivisionError": "tried to divide a number by zero",
    "ConnectionError": "a network connection failed",
    "ConnectionRefusedError": "a network connection was refused by the other side",
    "ConnectionResetError": "a network connection was closed unexpectedly",
    "TimeoutError": "an operation took too long and gave up",
    "PermissionError": "wasn't allowed to do something (a permissions problem)",
    "ImportError": "tried to use code from a module that couldn't be loaded",
    "ModuleNotFoundError": "tried to use a module that isn't installed",
    "NotImplementedError": "hit a part of the code that hasn't been finished yet",
    "RecursionError": "a function kept calling itself until Python ran out of room",
    "MemoryError": "ran out of memory",
    "OverflowError": "a number grew too large to represent",
    "StopIteration": "ran out of items while looping",
    "AssertionError": "an internal check failed (an assert statement)",
    "UnicodeDecodeError": "tried to read text using the wrong character encoding",
    "UnicodeEncodeError": "tried to write text using the wrong character encoding",
    "JSONDecodeError": "tried to read text that wasn't valid JSON",
    "ExceptionGroup": "several independent things failed at the same time (common in concurrent code)",
    "BaseExceptionGroup": "several independent things failed at the same time (common in concurrent code)",
    # PyJWT and cryptography (0.2.1): both checked directly for a
    # dedicated integration and found to carry no structured fields
    # beyond their own message (unlike e.g. stripe's .code/.param) --
    # nothing a bare traceback throws away, so nothing for a full
    # explainer plugin to add. Gloss/fix table entries are still real,
    # cheap value, the same reasoning that keeps redis-py off the
    # integration list entirely (docs/plugin-guide.md).
    "ExpiredSignatureError": "an authentication token's expiration time has passed",
    "InvalidAudienceError": "an authentication token was issued for a different service than the one checking it",
    "InvalidIssuerError": "an authentication token wasn't issued by the party that's supposed to have issued it",
    "InvalidSignatureError": "an authentication token's signature doesn't match -- wrong key, or the token was tampered with",
    "InvalidTokenError": "an authentication token failed validation",
    "DecodeError": "couldn't parse an authentication token -- it's malformed, not just invalid",
    "InvalidToken": "a decryption key didn't match, or the encrypted data was corrupted or tampered with",
    "InvalidSignature": "a cryptographic signature didn't match the data it's supposed to verify",
    "InvalidKey": "a cryptographic key wasn't the right shape or format for what it was used for",
}

_PLAIN_CONFIDENCE_NOTE = {
    "inferred": "(inferred from context, not stated directly)",
    "heuristic": "(whytrail's best guess -- less certain than the rest)",
}

# General, well-established guidance per exception type (0.2.1) -- not a
# diagnosis of *this* failure (whytrail has no way to know that a fix
# actually applies here), just the standard advice for that class of
# error, the same kind of thing a linter's "did you mean" hint or a
# language's own documentation would say. Framed as "how to avoid this
# *kind* of problem," not "here is your bug," which is the honest claim
# this can actually make. Keyed to the same exception types as
# _EXCEPTION_GLOSS, and only ever shown alongside that step's own gloss
# -- never as a standalone claim about what's wrong.
_EXCEPTION_FIXES = {
    "KeyError": "check the key exists before accessing it (`if key in d`), or use `d.get(key, default)` instead of `d[key]`",
    "ValueError": "validate the value before using it, or check what produced it further up this chain",
    "TypeError": "check the type of the value being used -- often a None where an object was expected, or a mismatched argument",
    "AttributeError": "check the object is the type expected -- often None, or an unexpected type from an earlier step",
    "IndexError": "check the list/sequence has enough items before indexing, or use a bounds check",
    "FileNotFoundError": "check the file path is correct and the file exists before opening it",
    "NotADirectoryError": "check the path actually points to a folder, not a file",
    "IsADirectoryError": "check the path actually points to a file, not a folder",
    "ZeroDivisionError": "check the divisor isn't zero before dividing",
    "ConnectionError": "check the service is reachable, and consider a retry with backoff -- a flaky network is common here",
    "ConnectionRefusedError": "check the target host/port is correct and the service is actually running",
    "ConnectionResetError": "often transient -- retry, and check for a proxy or load balancer dropping idle connections",
    "TimeoutError": "increase the timeout if the operation is legitimately slow, or check why it's taking longer than expected",
    "PermissionError": "check file/resource permissions, or that the process is running as the right user",
    "ImportError": "check the package is installed (`pip install <package>`) and the import path is correct",
    "ModuleNotFoundError": "install the missing package (`pip install <package>`), or check for a typo in the import",
    "NotImplementedError": "this code path is intentionally unfinished -- implement it, or avoid triggering it",
    "RecursionError": "check for a missing base case in a recursive function, or increase sys.setrecursionlimit() if the recursion is legitimate",
    "MemoryError": "process data in smaller chunks, or check for something growing unbounded",
    "OverflowError": "use a data type that can hold larger numbers, or check for a runaway calculation",
    "StopIteration": "check the iterator/generator actually has as many items as expected",
    "AssertionError": "the assumption in the assert statement was violated -- check what changed upstream",
    "UnicodeDecodeError": "check the file/data is actually encoded the way it's being decoded (e.g. try encoding='utf-8')",
    "UnicodeEncodeError": "check the target encoding can represent every character in the text",
    "JSONDecodeError": "check the source actually returned valid JSON -- print the raw text before parsing it",
    "ExceptionGroup": "look at each sub-exception below individually -- they're independent failures, not a single chain",
    "BaseExceptionGroup": "look at each sub-exception below individually -- they're independent failures, not a single chain",
    "ExpiredSignatureError": "the token needs to be refreshed/reissued -- check the client's refresh flow, not just this request",
    "InvalidAudienceError": "check the token was actually issued for this service, and that the `audience` check matches",
    "InvalidIssuerError": "check the token came from the issuer this code expects, and that the `issuer` check matches",
    "InvalidSignatureError": "check both sides are using the same signing key/algorithm, and that the token wasn't modified in transit",
    "InvalidTokenError": "inspect the token's claims and compare against what the validator expects (audience, issuer, expiry)",
    "DecodeError": "check the token wasn't truncated or corrupted before it reached the decoder",
    "InvalidToken": "check the same key used to encrypt is being used to decrypt, and that the data wasn't modified",
    "InvalidSignature": "check the signing and verifying keys are a matching pair, and the data wasn't modified after signing",
    "InvalidKey": "check the key was generated for this algorithm/purpose and hasn't been truncated or corrupted",
}

_EXCEPTION_TYPE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*): (.*)", re.DOTALL)
_LOCATION_RE = re.compile(r"^(.+):(\d+), in (.+)$")


def _confidence_label(confidence: float) -> str:
    if confidence >= Confidence.EXPLICIT.value:
        return "explicit"
    if confidence >= Confidence.INFERRED.value:
        return "inferred"
    if confidence >= Confidence.HEURISTIC.value:
        return "heuristic"
    return "unknown"


def _confidence_marker(confidence: float) -> str:
    # Spelled out, not a symbol: an earlier version used ASCII markers
    # (==/~~/..) that were legible only after reading the docs -- see
    # ADR 0002 §3 item 2. Still plain ASCII deliberately: box-drawing
    # or bracket-free glyphs have crashed stdout on a default Windows
    # console (cp1252) before, and a debugging tool that crashes
    # trying to print its own output would be absurd.
    return f"[{_confidence_label(confidence)}]"


def _confidence_style(confidence: float) -> str:
    return _STYLES.get(confidence, "dim")


@dataclasses.dataclass(slots=True)
class ExplanationStep:
    """One causal hop in the chain, ordered root-cause first.

    `locals` is a separate field from `description` on purpose: local
    variables at an exception's origin frame are exactly the kind of
    thing that can hold a password, an API key, or a customer record,
    and anything that exports an Explanation off-box (Sentry, OTel, a
    PR comment, an HTTP error response) needs a way to drop them
    without hand-parsing text out of a human-readable string. See
    Explanation.redacted() and ADR 0002 §3 item 5.
    """

    description: str
    confidence: float = Confidence.EXPLICIT.value
    location: str | None = None
    kind: str = "value"
    locals: dict[str, str] | None = None


@dataclasses.dataclass(slots=True)
class Explanation:
    """Returned by every why() call. Honest by construction: an
    Explanation with no steps says so plainly rather than fabricating a
    chain (ADR §11)."""

    subject: str
    steps: list[ExplanationStep] = dataclasses.field(default_factory=list)
    tracked: bool = True
    nodes: list[Node] = dataclasses.field(default_factory=list)
    edges: list[Edge] = dataclasses.field(default_factory=list)

    @property
    def confidence(self) -> float:
        if not self.steps:
            return Confidence.UNKNOWN.value
        return min(step.confidence for step in self.steps)

    @property
    def known(self) -> bool:
        return bool(self.steps)

    @property
    def text(self) -> str:
        if not self.steps:
            return (
                f"why({self.subject}): unknown -- no provenance captured.\n"
                f"  This value was never tracked. Wrap it with whytrail.track(), "
                f"@whytrail.tracked, or raise it as an exception to get an answer."
            )
        lines = [f"why({self.subject}):"]
        for step in self.steps:
            marker = _confidence_marker(step.confidence)
            loc = f"  [{step.location}]" if step.location else ""
            lines.append(f"  {marker} {step.description}{loc}")
            if step.locals:
                lines.append(f"      locals: {_format_locals(step.locals)}")
        return "\n".join(lines)

    @property
    def plain_text(self) -> str:
        """A prose rendering of the exact same steps as .text, phrased
        for someone without a programming background (0.2.1). Every
        sentence here is a direct paraphrase of a step already present
        -- never new information, never a guess beyond what .text
        already asserts. Not a replacement for .text: the terse
        [confidence] marker format stays the default for local dev and
        anywhere the extra prose would be noise; this is for handing an
        explanation to someone who doesn't read tracebacks for a
        living. Respects .redacted() the same way .text does, since it
        reads from the same `steps`.

        Known exception types (see _EXCEPTION_FIXES) also get a "How to
        avoid this" line -- general guidance for that *class* of error,
        not a diagnosis of this specific failure (whytrail has no way to
        know a fix actually applies here). Same honesty rule as the
        gloss itself: a type outside that table gets no fix line at all,
        not a guessed-at one.
        """
        if not self.steps:
            return (
                f"No explanation available for {self.subject}. It was never "
                "tracked -- wrap it with whytrail.track(), @whytrail.tracked, "
                "or raise it as an exception to get an answer."
            )
        lines = ["Here's what happened, from the root cause to the final result:", ""]
        for i, step in enumerate(self.steps, start=1):
            line = f"{i}. {_plain_gloss(step)}"
            note = _PLAIN_CONFIDENCE_NOTE.get(_confidence_label(step.confidence))
            if note:
                line += f" {note}"
            where = _plain_location(step.location) if step.location else None
            if where:
                line += f" -- {where}"
            lines.append(line)
            if step.locals:
                lines.append(f"   At that point: {_plain_locals(step.locals)}.")
            fix = _fix_for_step(step)
            if fix:
                lines.append(f"   How to avoid this: {fix}.")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return (
            f"<Explanation subject={self.subject!r} steps={len(self.steps)} "
            f"confidence={_confidence_label(self.confidence)} tracked={self.tracked}>"
        )

    def rich(self) -> t.Any:
        """Render as a rich.tree.Tree. Requires the 'rich' extra."""
        try:
            from rich.text import Text
            from rich.tree import Tree
        except ImportError as exc:  # pragma: no cover - exercised via extras test
            raise ImportError(
                "Rich rendering needs the 'rich' extra: pip install whytrail[rich]"
            ) from exc

        tree = Tree(f"why({self.subject})")
        if not self.steps:
            tree.add(Text("unknown -- no provenance captured", style="dim italic"))
            return tree
        for step in self.steps:
            label = Text(step.description, style=_confidence_style(step.confidence))
            if step.location:
                label.append(f"  {step.location}", style="dim")
            label.append(f"  ({_confidence_label(step.confidence)})", style="dim italic")
            if step.locals:
                label.append(f"\n      locals: {_format_locals(step.locals)}", style="dim")
            tree.add(label)
        return tree

    def json(self) -> dict[str, t.Any]:
        return {
            "subject": self.subject,
            "tracked": self.tracked,
            "known": self.known,
            "confidence": self.confidence,
            "steps": [
                {
                    "description": s.description,
                    "confidence": s.confidence,
                    "confidence_label": _confidence_label(s.confidence),
                    "location": s.location,
                    "kind": s.kind,
                    "locals": s.locals,
                    # General guidance for this step's exception type, if
                    # known (0.2.1) -- see _EXCEPTION_FIXES; None means
                    # "no guidance for this type," not "nothing to fix."
                    "suggestion": _fix_for_step(s),
                }
                for s in self.steps
            ],
        }

    def redacted(self) -> "Explanation":
        """A copy with every step's locals stripped -- the one-line
        way for any integration that exports off-box (Sentry, OTel, a
        CI comment, an HTTP error response) to get a safe-to-share
        version. Everything else (description, location, confidence,
        the causal chain itself) is preserved; only the raw local
        variable values are dropped, since those are the one thing
        that can plausibly contain a secret.
        """
        return dataclasses.replace(
            self,
            steps=[dataclasses.replace(step, locals=None) for step in self.steps],
        )

    def graph(self) -> str:
        """Render the traversed provenance subgraph as a Mermaid
        flowchart (ADR §12, Fig. 1)."""
        if not self.nodes:
            return f'graph TD\n    A["{_escape(self.subject)} -- no provenance captured"]'
        lines = ["graph TD"]
        for node in self.nodes:
            marker = " (tombstoned)" if node.tombstoned else ""
            lines.append(f'    N{node.id}["{node.kind.value}: {_escape(node.label)}{marker}"]')
        for edge in self.edges:
            arrow = "-->" if edge.confidence >= Confidence.EXPLICIT.value else "-.->"
            lines.append(f"    N{edge.source} {arrow}|{edge.kind.value}| N{edge.target}")
        return "\n".join(lines)


def _escape(label: str) -> str:
    return label.replace('"', "'").replace("\n", " ")


def _format_locals(locals_: dict[str, str]) -> str:
    return ", ".join(f"{name}={value}" for name, value in locals_.items())


def _exception_type_name(step: ExplanationStep) -> str | None:
    """Extract the exception type name from an exception-kind step's
    description, if it's in the one predictable "{TypeName}: {message}"
    shape builtin.py builds (with an optional connective phrase like
    "which explicitly caused " in front, itself containing no colon, so
    the first "Word: " match is always the real type name -- see
    explainers/builtin.py's _step_for()). Returns None for anything
    else: non-exception steps, or exception steps whose description
    doesn't match that shape (a plugin-authored one, say)."""
    if step.kind != "exception":
        return None
    match = _EXCEPTION_TYPE_RE.search(step.description)
    return match.group(1) if match else None


def _plain_gloss(step: ExplanationStep) -> str:
    """Paraphrase one step's description for .plain_text. Anything not
    recognized as a known exception type -- non-exception steps
    (tracked values, plugin-authored descriptions, already free-form
    prose) and exception types outside _EXCEPTION_GLOSS alike -- is used
    as-is rather than guessed at."""
    type_name = _exception_type_name(step)
    if type_name is None:
        return step.description
    gloss = _EXCEPTION_GLOSS.get(type_name)
    if gloss is None:
        return step.description
    match = _EXCEPTION_TYPE_RE.search(step.description)
    assert match is not None  # _exception_type_name already confirmed this matches
    message = match.group(2)
    return f"{type_name} -- {gloss} ({message})"


def _fix_for_step(step: ExplanationStep) -> str | None:
    """General guidance for this step's exception type, if any -- see
    _EXCEPTION_FIXES's own comment for what this is (and isn't)
    claiming."""
    type_name = _exception_type_name(step)
    if type_name is None:
        return None
    return _EXCEPTION_FIXES.get(type_name)


def _plain_location(location: str) -> str | None:
    """"C:\\path\\to\\file.py:12, in load_codes" -> "in load_codes(), line
    12 of file.py" -- drops the full path (not useful to a non-programmer
    reader, and the technical .text rendering already shows it in full
    for anyone who needs it) and reorders to lead with the function name,
    the part a plain-English sentence needs first."""
    match = _LOCATION_RE.match(location)
    if not match:
        return None
    filename, lineno, funcname = match.groups()
    short_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return f"in {funcname}(), line {lineno} of {short_name}"


def _plain_locals(locals_: dict[str, str]) -> str:
    return ", ".join(f"{name} was {value}" for name, value in locals_.items())
