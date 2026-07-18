"""Proves the six candidate "provenance primitives" from a Phase U
product-design review (transformation, confidence propagation,
branching, merging, override, composition/algebra) against real,
executed output -- not asserted from reading the code. See
`docs/adr/0011-provenance-vocabulary-is-already-sufficient.md` for the
full per-primitive analysis this file backs.

Every test here demonstrates a pattern the review worried whytrail
couldn't express, using only what's already public and shipped
(`track()`, `@tracked`, `trace()`, `why()`, `whytrail.config.env()`,
`Explanation.graph()`) -- no new `NodeKind`/`EdgeKind`, no new engine
surface. If one of these ever regresses, it means the "vocabulary is
already sufficient" conclusion in that ADR no longer holds and needs
re-litigating, not just a broken test.
"""

from __future__ import annotations

import os

import whytrail
import whytrail.config


def test_transformation_sequence_is_expressible_with_tracked():
    """"A was validated, normalized, clamped" -- a named sequence of
    operations, not just "A became B" -- is already expressible by
    decorating each transform step with @tracked: the call node's own
    label is the function's name."""

    @whytrail.tracked
    def validate(x):
        return x

    @whytrail.tracked
    def normalize(x):
        return x.strip().lower()

    @whytrail.tracked
    def clamp(x):
        return x[:5]

    with whytrail.trace():
        step1 = validate("  Hello World  ")
        step2 = normalize(step1)
        final = clamp(step2)

    descriptions = " ".join(step.description for step in whytrail.why(final).steps)
    assert "validate(...)" in descriptions
    assert "normalize(...)" in descriptions
    assert "clamp(...)" in descriptions
    # Order matters: the chain should read root-cause-first.
    validate_index = descriptions.index("validate(...)")
    normalize_index = descriptions.index("normalize(...)")
    clamp_index = descriptions.index("clamp(...)")
    assert validate_index < normalize_index < clamp_index


def test_confidence_propagates_as_the_weakest_link_across_a_chain():
    """Confidence composability: a chain's overall confidence is
    already the minimum across every hop (already shipped and tested
    elsewhere as test_known_explanation_confidence_is_the_weakest_link
    -- repeated here specifically for a multi-hop tracked chain, not
    just two steps)."""
    with whytrail.trace():
        raw = whytrail.track("raw", label="raw", confidence=whytrail.Confidence.EXPLICIT.value)
        middle = whytrail.track("mid", derived_from=raw, label="mid", confidence=whytrail.Confidence.INFERRED.value)
        final = whytrail.track("final", derived_from=middle, label="final", confidence=whytrail.Confidence.HEURISTIC.value)

    explanation = whytrail.why(final)
    assert explanation.confidence == whytrail.Confidence.HEURISTIC.value


def test_branching_one_value_affects_two_independent_derived_values():
    """One config value informing two different downstream systems --
    already representable structurally (a node can have any number of
    outgoing edges); confirmed here by tracking two independent
    children from the same parent and checking each child's own why()
    correctly traces back to the shared source."""
    with whytrail.trace():
        timeout = whytrail.track(30, label="config.timeout")
        http_client = whytrail.track({"timeout": 30}, derived_from=timeout, label="HTTP client config")
        retry_policy = whytrail.track({"max_wait": 30}, derived_from=timeout, label="Retry policy")

    http_graph = whytrail.why(http_client).graph()
    retry_graph = whytrail.why(retry_policy).graph()
    assert "config.timeout" in http_graph
    assert "config.timeout" in retry_graph
    assert "HTTP client config" in http_graph
    assert "Retry policy" in retry_graph
    # What's genuinely not built (named, not a gap discovered here):
    # a single forward query answering "what does config.timeout
    # affect" in one call, returning both children at once. See the
    # ADR -- roadmap.md Phase F already names this ("richer
    # ProvenanceGraph queries... not started, deliberately") pending a
    # real consumer, not rediscovered as new here.


def test_override_and_merge_semantics_already_exist_in_config_env():
    """"Why did the final value win, not just where it came from" --
    already answered by whytrail.config.env()'s own source_label,
    which names not just the winning source but *why the others
    didn't apply* ("not set in the process environment"). Verified
    across all three priority levels (env > dotenv > default), not
    just one."""
    dotenv = {"MERGE_TEST_KEY": "from-dotenv"}

    # 1. Environment wins over both dotenv and default.
    os.environ["MERGE_TEST_KEY"] = "from-environment"
    try:
        with whytrail.trace():
            value = whytrail.config.env("MERGE_TEST_KEY", "from-default", dotenv=dotenv)
        explanation = whytrail.why(value)
        assert "environment variable" in explanation.text
        assert value == "from-environment"
    finally:
        del os.environ["MERGE_TEST_KEY"]

    # 2. dotenv wins over default once the environment no longer has it --
    #    and the explanation says *why* env didn't win, not just that dotenv did.
    with whytrail.trace():
        value = whytrail.config.env("MERGE_TEST_KEY", "from-default", dotenv=dotenv)
    explanation = whytrail.why(value)
    assert "not set in the process environment" in explanation.text
    assert value == "from-dotenv"

    # 3. default wins once neither source has it, and says what was checked.
    with whytrail.trace():
        value = whytrail.config.env("MERGE_TEST_KEY_MISSING", "from-default", dotenv=dotenv)
    explanation = whytrail.why(value)
    assert "checked the environment, .env, not found" in explanation.text
    assert value == "from-default"


def test_composition_algebra_a_value_derived_from_two_independent_provenances():
    """The example the review was most excited about: Policy(timeout,
    retry) -- why(policy) should show it was "combined from
    independent provenances," not just list two unrelated facts.
    Already true: @tracked's _link_arguments links every argument's
    own node to the call node, so two independently-sourced config
    values converging on one call already produce exactly this shape,
    with the convergence surfaced in .text (not hidden) and the full
    join visible in .graph()."""

    class Policy:
        def __init__(self, timeout, retries):
            self.timeout = timeout
            self.retries = retries

    @whytrail.tracked
    def make_policy(timeout, retries):
        return Policy(timeout, retries)

    with whytrail.trace():
        timeout = whytrail.config.env("ALGEBRA_TIMEOUT_MISSING", 30, cast=int)
        retries = whytrail.config.env("ALGEBRA_RETRIES_MISSING", 3, cast=int)
        policy = make_policy(timeout, retries)

    explanation = whytrail.why(policy)
    # _steps_from_traversal already names this a convergence point in
    # the terse summary, rather than silently picking one parent and
    # hiding the other.
    assert "other path" in explanation.text and "converge here" in explanation.text

    graph = explanation.graph()
    assert "ALGEBRA_TIMEOUT_MISSING" in graph
    assert "ALGEBRA_RETRIES_MISSING" in graph
    assert "make_policy(...)" in graph
    # Both independent provenances actually feed the same call node --
    # not just present in the graph text, but as real edges into it.
    assert graph.count("|passed_to|") == 2
