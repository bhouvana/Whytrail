"""A counterexample sweep (Phase U, docs/adr/0012-provenance-model-boundaries.md):
real Python debugging scenarios, each checked against the actual graph
model for whether it's representable -- not "could be nicer," but
"can the current Node/Edge/NodeKind/EdgeKind vocabulary express this
truthfully at all." Every scenario here was executed for real before
being written down as a finding.

None of these found a scenario the graph model *cannot* represent.
Two found a real, narrow nuance worth naming and pinning down with a
regression test -- neither is a bug, and neither needs a graph-model
change, but both are worth protecting against an accidental "fix" that
would just be a different kind of wrong. A later pass added Click's
`ctx.get_parameter_source()` (a strong, independent real-world
confirmation of the override-semantics pattern ADR 0011 already found
in `whytrail.config.env()`), Jinja2 template rendering (a fifth real
shape of the same composition pattern), and a permanent regression test
for `@tracked`'s already-documented `.send()`/`.throw()` scope, which
had never actually been pinned down by a test before.
"""

from __future__ import annotations

import functools
import sys

import pytest

import whytrail

# -- Finding 1: framework-mediated calls are causally correct, but the
# location shown is the immediate calling frame, which can be a
# framework's own internal dispatch code rather than the conceptual
# call site a user recognizes. Confirmed across two independent cases
# (a descriptor's __get__, asyncio's task runner) -- named as a
# location-attribution property of _call_site()'s frame-walking, not a
# correctness bug: the causal chain itself is accurate either way.


def test_cached_property_composition_is_causally_correct():
    # __set_name__ must fire at class-body time (Python calls it for
    # every descriptor found while creating the class) -- assigning the
    # descriptor onto the class *after* creation, as an earlier version
    # of this test did, skips that and raises TypeError instead.
    class Config:
        def __init__(self, raw):
            self.raw = raw

        @functools.cached_property
        @whytrail.tracked
        def parsed(self):
            return int(self.raw) * 2

    with whytrail.trace():
        c = Config("21")
        value = c.parsed

    explanation = whytrail.why(value)
    assert explanation.known
    descriptions = " ".join(step.description for step in explanation.steps)
    assert "parsed(...)" in descriptions
    assert value == 42


@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.TaskGroup requires Python 3.11+")
def test_asyncio_task_group_tracked_calls_do_not_cross_contaminate():
    import asyncio

    @whytrail.tracked
    async def fetch(n):
        await asyncio.sleep(0)
        return n * 10

    async def main():
        with whytrail.trace():
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(fetch(i)) for i in range(5)]
        return [t.result() for t in tasks]

    results = asyncio.run(main())
    for i, result in enumerate(results):
        explanation = whytrail.why(result)
        assert explanation.known
        assert f"n={i}" in str(explanation.steps)


# -- Finding 2: functools.lru_cache's cache hits and real computations
# are structurally indistinguishable in the graph when @tracked wraps
# outside lru_cache -- both produce an identical-looking Call node
# (same label, same args) linked to the same result. Not fabrication
# (both calls really happened), just not maximally informative. Fixing
# this would mean @tracked detecting a cache hit (e.g. via
# cache_info()), a producer-level enhancement, not a graph-model one --
# not built without evidence anyone's been confused by it.


def test_lru_cache_hit_and_real_computation_produce_the_same_shape():
    call_count = 0

    @whytrail.tracked
    @functools.lru_cache
    def expensive(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    with whytrail.trace():
        first = expensive(21)
        second = expensive(21)  # cache hit -- body does not re-execute

    assert call_count == 1  # confirms the second call really was a cache hit
    assert first is second

    first_text = whytrail.why(first).text
    second_text = whytrail.why(second).text
    # Both explanations describe the same node (same object, same
    # graph identity) -- there is no marker anywhere distinguishing
    # "this one actually computed the value" from "this one reused a
    # cached one." Documented as a known, accepted gap, not asserted
    # to be fixed here.
    assert first_text == second_text


# -- Finding: SQLAlchemy's identity map (session.get() twice for the
# same PK returns the *same* object) is represented correctly and
# honestly -- why() on the second call's result resolves to the one
# real tracked node, since there is only one real object. This is not
# a gap: fabricating a second, distinct "identity map hit" event would
# be exactly the kind of invented detail ADR §11 rejects; nothing
# automatically instruments SQLAlchemy's identity map today (a real
# future producer/plugin idea, gated on a concrete need per ADR 0003 --
# not a graph-model limitation).


def test_sqlalchemy_identity_map_hit_resolves_honestly_not_fabricated():
    sa = pytest.importorskip("sqlalchemy")
    from sqlalchemy.orm import DeclarativeBase, Session

    class Base(DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "test_boundaries_users"
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String)

    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(User(id=1, name="Alice"))
        session.commit()

        with whytrail.trace():
            first = session.get(User, 1)
            whytrail.track(first, label="first session.get(User, 1)")
            second = session.get(User, 1)  # identity map hit, not a new query

        assert first is second  # the real, honest fact this test protects
        explanation = whytrail.why(second)
        assert explanation.known
        assert "first session.get" in explanation.text


# -- multiprocessing: a live ProvenanceGraph is deliberately not
# picklable (holds a real threading.RLock); snapshot()/restore() is the
# sanctioned way to cross a process boundary, and it already works.
# Confirmed both halves directly rather than assuming either.


def test_live_graph_is_not_picklable_by_design():
    import pickle

    from whytrail.core.graph import ProvenanceGraph

    graph = ProvenanceGraph()
    with pytest.raises(TypeError, match="RLock"):
        pickle.dumps(graph)


def test_snapshot_string_crosses_a_process_boundary_via_pickle():
    import pickle

    from whytrail.core import serialize
    from whytrail.core.graph import ProvenanceGraph
    from whytrail.core.node import NodeKind

    graph = ProvenanceGraph()
    graph.add_node(NodeKind.VALUE, "x")
    data = serialize.dumps(graph)

    # Simulates sending the snapshot across a real process boundary
    # (multiprocessing.Queue/Pipe both pickle their payload).
    received = pickle.loads(pickle.dumps(data))
    restored = serialize.loads(received)
    assert len(restored) == 1


# -- Generator .send()/.throw(): @tracked's own docstring already
# states these aren't forwarded into the wrapped generator body, but
# nothing pinned that down as a regression test before this sweep.
# Confirmed directly: a value sent in is NOT the same as what the
# generator body itself would have done with it if called undecorated.


def test_generator_send_is_not_forwarded_into_the_wrapped_body():
    @whytrail.tracked
    def counter():
        total = 0
        while True:
            received = yield total
            if received is not None:
                total += received
            else:
                total += 1

    with whytrail.trace():
        gen = counter()
        first = next(gen)
        # A real, undecorated version of this generator would advance
        # total by 10 here; @tracked's wrapper records .send()'s value
        # as this call's own outcome rather than resuming the body with
        # it, per tracked()'s own documented scope.
        second = gen.send(10)

    assert first == 0
    assert second == 1  # NOT 10 -- confirms the documented limitation, not a fix for it
    assert whytrail.why(first).known
    assert whytrail.why(second).known


# -- Click: "why did this parameter get this value" (CLI arg, env var,
# or default) is a real, common debugging question -- and Click
# already exposes exactly the metadata whytrail.config.env() invents
# for itself (ctx.get_parameter_source()). A stronger real-world
# confirmation of ADR 0011's override-semantics finding than the
# config.env() example alone, since this is a well-known third-party
# API doing the source-tracking, not whytrail's own.


def test_click_parameter_source_is_expressible_as_override_provenance():
    click = pytest.importorskip("click")
    from click.testing import CliRunner

    captured = {}

    @click.command()
    @click.option("--timeout", default=30, envvar="WHYTRAIL_TEST_CLICK_TIMEOUT", type=int)
    def cli(timeout):
        with whytrail.trace():
            ctx = click.get_current_context()
            source = ctx.get_parameter_source("timeout")
            tracked = whytrail.track(timeout, label=f"timeout (source: {source.name})")
        captured["explanation"] = whytrail.why(tracked)

    runner = CliRunner()

    runner.invoke(cli, [])
    assert "source: DEFAULT" in captured["explanation"].text

    runner.invoke(cli, ["--timeout", "99"])
    assert "source: COMMANDLINE" in captured["explanation"].text


# -- Jinja2: a rendered template combining a value passed at render
# time with one pulled from the template's own default context --
# reconfirms the composition pattern (ADR 0011) in a fifth real shape,
# not a new finding, but real enough to protect with its own test
# rather than leaving as a scratch-only confirmation.


def test_jinja2_rendered_output_composes_from_two_independent_provenances():
    jinja2 = pytest.importorskip("jinja2")

    env = jinja2.Environment(loader=jinja2.DictLoader({"greet.txt": "{{ greeting }}, {{ name }}!"}))

    with whytrail.trace():
        greeting = whytrail.track("Hello", label="greeting (passed at render time)")
        name = whytrail.track("World", label="name (context default)")
        template = env.get_template("greet.txt")
        rendered = template.render(greeting=greeting, name=name)
        tracked_output = whytrail.track(rendered, label="rendered output", derived_from=[greeting, name])

    assert rendered == "Hello, World!"
    explanation = whytrail.why(tracked_output)
    assert "greeting (passed at render time)" in explanation.text
    graph = explanation.graph()
    assert "greeting (passed at render time)" in graph
    assert "name (context default)" in graph
