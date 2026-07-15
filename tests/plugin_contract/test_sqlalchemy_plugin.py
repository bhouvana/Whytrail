"""Validates whytrail-sqlalchemy end to end against a real in-memory
SQLite database -- a real StatementError from a real driver, not a
constructed mock exception."""

from __future__ import annotations

import pytest

sa = pytest.importorskip("sqlalchemy")
pytest.importorskip("whytrail_sqlalchemy")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from sqlalchemy.orm import DeclarativeBase, Session  # noqa: E402


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = sa.Column(sa.Integer, primary_key=True)
    email = sa.Column(sa.String, unique=True, nullable=False)


@pytest.fixture()
def session():
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(sa.exc.StatementError) is not None


def test_why_on_integrity_error_shows_statement_and_params(session):
    session.add(User(id=1, email="a@example.com"))
    session.commit()
    session.add(User(id=2, email="a@example.com"))

    with pytest.raises(sa.exc.IntegrityError) as excinfo:
        session.commit()

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "UNIQUE constraint failed" in explanation.text
    assert "INSERT INTO users" in explanation.text
    assert "a@example.com" in explanation.text


def test_params_are_in_locals_field_not_baked_into_description(session):
    session.add(User(id=1, email="a@example.com"))
    session.commit()
    session.add(User(id=2, email="a@example.com"))

    with pytest.raises(sa.exc.IntegrityError) as excinfo:
        session.commit()

    explanation = whytrail.why(excinfo.value)
    statement_step = next(s for s in explanation.steps if "INSERT INTO" in s.description)
    assert statement_step.locals is not None
    assert "a@example.com" not in statement_step.description


def test_redacted_hides_params_but_keeps_statement(session):
    session.add(User(id=1, email="a@example.com"))
    session.commit()
    session.add(User(id=2, email="a@example.com"))

    with pytest.raises(sa.exc.IntegrityError) as excinfo:
        session.commit()

    explanation = whytrail.why(excinfo.value).redacted()
    assert "a@example.com" not in explanation.text
    assert "INSERT INTO users" in explanation.text


def test_manual_registration_still_overrides_the_plugin(session):
    whytrail.register(sa.exc.StatementError, lambda exc: "overridden by the user")
    session.add(User(id=1, email="a@example.com"))
    session.commit()
    session.add(User(id=2, email="a@example.com"))

    with pytest.raises(sa.exc.IntegrityError) as excinfo:
        session.commit()

    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text
