"""Property-based redaction tests (docs/testing-maturity.md gap #2:
"the current approach proves the mechanism works but not that it's
exhaustive" -- this file is the first real answer to that).

Every hand-picked-secret test elsewhere in this suite (e.g.
"secret@example.com") proves redaction works for *that* value. These
tests generate a wide range of strings -- unicode, quotes, newlines,
format-string-looking text, empty strings -- via Hypothesis and assert
the property should hold for *any* value, not just the one each
plugin's author happened to choose.

Each test also asserts the generated value appears in the
*unredacted* output first. Without that check, a test that only
asserts "value not in redacted text" would pass vacuously if a plugin
had a bug where it never captured the value at all -- which would look
identical to correct redaction from the outside. Proving redaction
removed something requires first proving it was there.

Scope: plugins whose per-example construction is cheap enough to run
inside a Hypothesis loop (tens of examples) without real I/O -- an
in-memory SQLite round trip, constructing an exception directly, or
parsing a short document. Plugins requiring a real server per example
(grpcio, Prefect) or a real crawl (Scrapy) are covered by their own
single-value tests elsewhere instead; the mechanism being fuzzed here
(locals -> Explanation.redacted()) is identical across all of them, so
this sample is representative of the shared mechanism, not of every
plugin's own message-parsing logic individually.

Widened from 9 exception explainers (plus track()/config.env()) to 20
(roadmap.md Phase I): every plugin with a `locals={...}` redaction-
critical field, checked against each plugin's own source first rather
than assumed. Three named Phase I candidates turned out not to apply
once actually checked, each plugin's own docstring says why: `boto3`
("no locals-redaction concern here worth a special case: `.response`
carries AWS's own error description, not the request parameters that
triggered it"), `aiohttp` ("there is no body-preview step here ...
nothing was omitted for redaction reasons, the data simply isn't
available"), `marshmallow` ("marshmallow's messages don't embed the
actual bad input value"). `oracledb` has a real redaction-critical
field but is excluded from this file for the same reason grpcio/Prefect
are: its exception can only be constructed via a real (if
unreachable-host, thin-mode) connection attempt per example, not a
free-standing object -- covered by its own single-value test instead.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import whytrail
import whytrail.config

# Letters and digits (including non-ASCII letters), 8-80 characters,
# no leading/trailing whitespace.
#
# Two rounds of narrowing from the original design, both real findings
# about *this test's* methodology, not about the plugins:
#
# 1. min_size=1 first: Hypothesis's shrinker finds the simplest failing
#    example, and single characters like "0" or "2" are trivially (and
#    meaninglessly) substrings of legitimate numbers already in a
#    description -- an HTTP status "404" contains "0". min_size=8 makes
#    a coincidental collision with short structural tokens statistically
#    impossible.
#
# 2. Punctuation/backslash/non-ASCII-whitespace next: some plugins store
#    `repr(value)` rather than the raw value (whytrail-openai's body,
#    whytrail-google-cloud's details list), and Python's repr() escapes
#    backslashes, quotes, and non-printable-ish characters like U+00A0 --
#    so the *escaped* text, not the literal character, is what appears
#    in the output. That's still fully captured-then-redacted correctly;
#    it just means a literal substring check on the original character
#    fails without asserting anything false about security. Some
#    libraries (PyYAML's tag parser, huggingface_hub's error parsing)
#    also legitimately strip whitespace from what they're given before
#    whytrail ever sees it. None of that is a redaction bug, and
#    round-tripping every escaping/normalization rule precisely for nine
#    different libraries is its own project -- this alphabet instead
#    sticks to characters that survive repr() and no library here
#    normalizes away, which still exercises the real property (does
#    arbitrary data-shaped content leak) without those false positives.
#
# 3. The confidence-label words themselves next: Explanation.text's
#    confidence marker is `[explicit]`/`[inferred]`/`[heuristic]` (ADR
#    0002 §3 item 2's legibility fix), which is legitimately part of
#    *every* Explanation's unredacted text -- so a randomly generated
#    secret that happens to equal "explicit" (8 letters, within this
#    strategy's size range) collides with the marker word the same way
#    a one-character secret collided with a status code in round 1.
#    Not a leak; the marker isn't user data. Filtered out rather than
#    asserted around, since the point of this suite is testing
#    genuine secrets, not butwhy's own reserved vocabulary.
_RESERVED_WORDS = frozenset({"explicit", "inferred", "heuristic", "unknown"})


def _not_reserved(s: str) -> bool:
    return s.lower() not in _RESERVED_WORDS


_TRICKY_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=8,
    max_size=80,
).filter(_not_reserved)

# ASCII letters/digits only, for the one plugin (PyYAML) whose secret
# gets embedded in a YAML *tag* position rather than a plain string
# value -- tag syntax accepts a narrower character set than YAML
# strings do, so some generated non-ASCII letters get scanner-rejected
# (truncating the secret before any error object exists) rather than
# embedded whole. Found the same way as everything else in this file:
# the test failed first, the cause was diagnosed after.
_ASCII_TRICKY_TEXT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=8,
    max_size=80,
).filter(_not_reserved)

# deadline=None: several of these do real work (an in-memory SQLite
# round trip, a Prefect-free but still non-trivial parse) whose first
# call pays one-time interpreter/import costs -- Hypothesis's default
# 200ms per-example deadline produced a FlakyFailure on
# test_sqlalchemy_params_redaction's cold start (4.1s) that a warm
# re-run didn't reproduce (3ms), which is a timing artifact of the test
# harness, not a property that should ever fail a build.
_FUZZ_SETTINGS = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_sqlalchemy_params_redaction(secret):
    sa = pytest.importorskip("sqlalchemy")
    pytest.importorskip("whytrail.integrations.sqlalchemy")
    from sqlalchemy.orm import DeclarativeBase, Session

    class Base(DeclarativeBase):
        pass

    class FuzzUser(Base):
        __tablename__ = "fuzz_users"
        id = sa.Column(sa.Integer, primary_key=True)
        email = sa.Column(sa.String, unique=True, nullable=False)

    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(FuzzUser(id=1, email=secret))
        session.commit()
        session.add(FuzzUser(id=2, email=secret))
        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            session.commit()

    _assert_redaction_holds(excinfo.value, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_pymongo_redaction(secret):
    pymongo = pytest.importorskip("pymongo")
    pytest.importorskip("whytrail.integrations.pymongo")

    exc = pymongo.errors.OperationFailure(
        f"E11000 duplicate key error: {{ email: {secret!r} }}",
        code=11000,
        details={"keyValue": {"email": secret}},
    )
    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_jsonschema_redaction(secret):
    jsonschema = pytest.importorskip("jsonschema")
    pytest.importorskip("whytrail.integrations.jsonschema")

    schema = {"type": "object", "properties": {"age": {"type": "integer"}}, "required": ["age"]}
    with pytest.raises(jsonschema.ValidationError) as excinfo:
        jsonschema.validate({"age": secret}, schema)

    _assert_redaction_holds(excinfo.value, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT.filter(lambda s: not s.isdigit()))
def test_pydantic_redaction(secret):
    # filter(not isdigit): pydantic's default lax mode coerces a
    # purely-numeric string straight to int without ever raising
    # ValidationError ("00000000" -> 0) -- found because the test
    # failed with "DID NOT RAISE", not anticipated from pydantic's
    # docs. Excluding all-digit strings keeps every example a genuine
    # validation failure.
    pydantic = pytest.importorskip("pydantic")
    pytest.importorskip("whytrail.integrations.pydantic")

    class FuzzModel(pydantic.BaseModel):
        age: int

    with pytest.raises(pydantic.ValidationError) as excinfo:
        FuzzModel(age=secret)

    _assert_redaction_holds(excinfo.value, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_asyncpg_redaction(secret):
    asyncpg = pytest.importorskip("asyncpg")
    pytest.importorskip("whytrail.integrations.asyncpg")

    exc = asyncpg.UniqueViolationError("duplicate key value violates unique constraint")
    exc.sqlstate = "23505"
    exc.table_name = "users"
    exc.column_name = None
    exc.constraint_name = "users_email_key"
    exc.detail = f"Key (email)=({secret}) already exists."

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_ASCII_TRICKY_TEXT)
def test_pyyaml_redaction(secret):
    yaml = pytest.importorskip("yaml")
    pytest.importorskip("whytrail.integrations.pyyaml")

    with pytest.raises(yaml.YAMLError) as excinfo:
        yaml.safe_load(f"a: !!python/object/{secret}")

    _assert_redaction_holds(excinfo.value, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_openai_redaction(secret):
    openai = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("whytrail.integrations.openai")

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request, json={"error": {"message": "rate limited"}})
    exc = openai.RateLimitError("rate limited", response=response, body={"message": secret})

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_huggingface_hub_redaction(secret):
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("huggingface_hub")
    pytest.importorskip("whytrail.integrations.huggingface_hub")
    from huggingface_hub.errors import HfHubHTTPError
    from huggingface_hub.utils import hf_raise_for_status

    request = httpx.Request("GET", "https://huggingface.co/api/models/x")
    response = httpx.Response(404, request=request, json={"error": secret})
    with pytest.raises(HfHubHTTPError) as excinfo:
        hf_raise_for_status(response)

    _assert_redaction_holds(excinfo.value, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_google_cloud_redaction(secret):
    google_exceptions = pytest.importorskip("google.api_core.exceptions")
    pytest.importorskip("whytrail.integrations.google_cloud")

    exc = google_exceptions.NotFound("resource not found", details=[secret])
    # the detail is what's redaction-critical here; the message
    # (treated like a URL, see whytrail_google_cloud's module docstring)
    # is allowed to appear unredacted, so only check the details path
    explanation = whytrail.why(exc)
    detail_steps = [s for s in explanation.steps if s.locals]
    assert detail_steps, "expected at least one step with locals for a NotFound with details"
    assert any(secret in v for step in detail_steps for v in step.locals.values())
    for step in explanation.steps:
        assert secret not in step.description
    redacted = explanation.redacted()
    assert secret not in redacted.text


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_tracked_value_redaction(secret):
    """The gap this file's own docstring names but didn't cover until
    now: every fuzz target above is a Tier 1 exception explainer,
    where `.locals` was always the only redaction-critical field. A
    0.3 audit found `.redacted()` never touched `NodeKind.VALUE` node
    labels at all -- and `track()`'s default label is the tracked
    value's own `repr()` (`runtime/capture.py`), so any Tier 2 chain
    leaked exactly the class of secret `.redacted()` claims to strip,
    just through a field this suite never fuzzed."""
    with whytrail.trace():
        value = whytrail.track(secret)
    explanation = whytrail.why(value)
    assert explanation.known, f"expected a known explanation for secret={secret!r}"
    assert secret in explanation.text, "secret never appeared in unredacted text -- capture itself is broken"

    redacted = explanation.redacted()
    assert secret not in redacted.text, f"secret {secret!r} survived .redacted(): {redacted.text!r}"
    assert secret not in redacted.subject, f"secret {secret!r} survived .redacted() via subject: {redacted.subject!r}"
    assert secret not in redacted.graph(), f"secret {secret!r} survived .redacted() via .graph()"


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_config_env_default_redaction(secret):
    """Same gap, hit through whytrail.config specifically -- a
    default config value (the shape a DB password or API key most
    often takes: `env("DB_PASSWORD", "fallback")`) becomes a
    NodeKind.VALUE node's label the same way track() does."""
    with whytrail.trace():
        value = whytrail.config.env("WHYTRAIL_FUZZ_KEY_DOES_NOT_EXIST", secret)
    explanation = whytrail.why(value)
    assert explanation.known, f"expected a known explanation for secret={secret!r}"
    assert secret in explanation.text, "secret never appeared in unredacted text -- capture itself is broken"

    redacted = explanation.redacted()
    assert secret not in redacted.text, f"secret {secret!r} survived .redacted(): {redacted.text!r}"
    assert secret not in redacted.subject, f"secret {secret!r} survived .redacted() via subject: {redacted.subject!r}"


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_requests_redaction(secret):
    requests = pytest.importorskip("requests")
    pytest.importorskip("whytrail.integrations.requests")

    response = requests.models.Response()
    response.status_code = 500
    response.reason = "Internal Server Error"
    response._content = secret.encode()
    # Without an explicit encoding, `.text` falls back to
    # charset_normalizer's best-guess detection -- which, for a short,
    # ambiguous byte sequence, can guess a charset other than the one
    # actually used to encode `secret`, decoding it to mojibake that
    # never matches the original string. Found by this test failing
    # with a real (if oddly encoded) example, not anticipated in
    # advance; setting the encoding explicitly is also what a real API
    # response almost always does via its own Content-Type header.
    response.encoding = "utf-8"
    request = requests.models.PreparedRequest()
    request.method = "GET"
    request.url = "https://api.example.com/x"
    response.request = request
    # _explain_response reads response.url, not request.url -- the two
    # are independent attributes on a real requests.Response.
    response.url = "https://api.example.com/x"

    _assert_redaction_holds(response, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_httpx_redaction(secret):
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("whytrail.integrations.httpx")

    request = httpx.Request("GET", "https://api.example.com/x")
    response = httpx.Response(500, request=request, text=secret)
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        response.raise_for_status()

    _assert_redaction_holds(excinfo.value, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_anthropic_redaction(secret):
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("whytrail.integrations.anthropic")

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request, json={"error": {"type": "rate_limit_error"}})
    exc = anthropic.RateLimitError("Rate limited", response=response, body={"type": "rate_limit_error", "message": secret})

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_psycopg_redaction(secret):
    psycopg = pytest.importorskip("psycopg")
    pytest.importorskip("whytrail.integrations.psycopg")

    exc = psycopg.errors.UndefinedTable(f'relation "{secret}" does not exist')
    exc.sqlstate = "42P01"

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_pymysql_redaction(secret):
    pymysql = pytest.importorskip("pymysql")
    pytest.importorskip("whytrail.integrations.pymysql")

    exc = pymysql.err.OperationalError(1054, f"Unknown column '{secret}' in 'field list'")

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_ASCII_TRICKY_TEXT)
def test_pymssql_redaction(secret):
    # ASCII-only alphabet: the message is round-tripped through
    # .encode()/.decode("utf-8") the same way whytrail-pyyaml's fuzz
    # target above is, for the same reason -- keeping to the shared
    # alphabet that's already confirmed to survive that round trip
    # rather than re-deriving it for a second plugin.
    pymssql = pytest.importorskip("pymssql")
    pytest.importorskip("whytrail.integrations.pymssql")

    exc = pymssql.OperationalError((208, f"Invalid object name '{secret}'.".encode()))

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_clickhouse_redaction(secret):
    ch_exceptions = pytest.importorskip("clickhouse_connect.driver.exceptions")
    pytest.importorskip("whytrail.integrations.clickhouse")

    exc = ch_exceptions.DatabaseError(
        f"Code: 60. DB::Exception: Table default.{secret} doesn't exist", code=60, name="UNKNOWN_TABLE"
    )

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_snowflake_redaction(secret):
    sf_errors = pytest.importorskip("snowflake.connector.errors")
    pytest.importorskip("whytrail.integrations.snowflake")

    exc = sf_errors.ProgrammingError(
        msg=f"SQL compilation error: Object '{secret}' does not exist",
        errno=2003,
        sqlstate="42S02",
        query=f"SELECT * FROM {secret}",
    )

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_influxdb_redaction(secret):
    influx_rest = pytest.importorskip("influxdb_client.rest")
    pytest.importorskip("whytrail.integrations.influxdb")

    exc = influx_rest.ApiException(status=400, reason="Bad Request")
    exc.body = f'{{"message":"field {secret} not found"}}'

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
@given(secret=_TRICKY_TEXT)
def test_graphql_core_redaction(secret):
    graphql = pytest.importorskip("graphql")
    pytest.importorskip("whytrail.integrations.graphql_core")

    exc = graphql.GraphQLError(f"resolver failed: {secret}", path=["user"])

    _assert_redaction_holds(exc, secret)


@_FUZZ_SETTINGS
# .filter(...): the description this plugin builds is
# f"{type(exc).__name__}: code=... status=..." -- always including the
# literal, non-secret class name "ClientError". A generated secret that
# happens to be a same-case contiguous substring of that name (found:
# secret='ClientEr') makes `secret in step.description` true for a
# reason that has nothing to do with whether the plugin redacted
# anything, the same false-positive class _RESERVED_WORDS exists to
# filter out above, just via class-name collision instead of a
# confidence-marker word.
@given(secret=_TRICKY_TEXT.filter(lambda s: s.lower() not in "clienterror"))
def test_google_genai_redaction(secret):
    genai_errors = pytest.importorskip("google.genai.errors")
    genai_requests = pytest.importorskip("requests")
    pytest.importorskip("whytrail.integrations.google_genai")
    import json

    response = genai_requests.models.Response()
    response.status_code = 400
    response._content = json.dumps({"error": {"code": 400, "message": secret, "status": "INVALID_ARGUMENT"}}).encode()
    # `except ... as exc:` implicitly deletes `exc` at the end of the
    # except block, so referencing it afterward raises UnboundLocalError
    # -- found by this test failing, not anticipated. Return from inside
    # the block instead, the same pattern test_google_genai_plugin.py's
    # own _api_error() helper already uses.
    exc = _raise_for_response(genai_errors, response)
    _assert_redaction_holds(exc, secret)


def _raise_for_response(genai_errors, response):
    try:
        genai_errors.APIError.raise_for_response(response)
    except genai_errors.APIError as exc:
        return exc
    raise AssertionError("expected raise_for_response to raise")


def _assert_redaction_holds(obj, secret: str) -> None:
    """Shared assertion: the raw Explanation captured `secret`
    somewhere (proving the test isn't vacuous), it never appears in
    any step's `description` or the subject (proving it went through
    `locals`, not unredactable text), and `.redacted()` removes it
    completely."""
    explanation = whytrail.why(obj)
    assert explanation.known, f"expected a known explanation for secret={secret!r}"

    raw_text = explanation.text
    assert secret in raw_text, (
        f"secret {secret!r} never appeared in unredacted text -- either it wasn't "
        "captured at all (making the redaction check below vacuous) or something "
        "about this specific value breaks the plugin's own formatting"
    )

    for step in explanation.steps:
        assert secret not in step.description, f"secret {secret!r} leaked into description: {step.description!r}"
    assert secret not in explanation.subject, f"secret {secret!r} leaked into subject: {explanation.subject!r}"

    redacted_text = explanation.redacted().text
    assert secret not in redacted_text, f"secret {secret!r} survived .redacted(): {redacted_text!r}"
