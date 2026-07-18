from __future__ import annotations

import sys
import threading

import pytest

import whytrail
from whytrail import hook

SECRET = "sk-super-secret-token"


@pytest.fixture(autouse=True)
def _restore_real_hooks():
    """install() mutates process-global sys.excepthook/threading.excepthook
    -- leaking a replaced hook into later tests (or the test runner's
    own error reporting) would be a real, silent bug, not just an
    inconvenience, so every test gets a clean slate on both sides."""
    real_sys_hook = sys.excepthook
    real_threading_hook = threading.excepthook
    yield
    sys.excepthook = real_sys_hook
    threading.excepthook = real_threading_hook
    hook._original_sys_excepthook = None  # noqa: SLF001 - test-only reset of hook.py's own module state
    hook._original_threading_excepthook = None  # noqa: SLF001


def _raise_and_capture_sys_hook(exc: BaseException) -> None:
    try:
        raise exc
    except type(exc) as caught:
        sys.excepthook(type(caught), caught, caught.__traceback__)


def test_install_replaces_sys_excepthook():
    before = sys.excepthook
    whytrail.install()
    assert sys.excepthook is not before


def test_install_replaces_threading_excepthook():
    before = threading.excepthook
    whytrail.install()
    assert threading.excepthook is not before


def test_uninstall_restores_the_original_sys_excepthook():
    before = sys.excepthook
    whytrail.install()
    whytrail.uninstall()
    assert sys.excepthook is before


def test_uninstall_restores_the_original_threading_excepthook():
    before = threading.excepthook
    whytrail.install()
    whytrail.uninstall()
    assert threading.excepthook is before


def test_uninstall_without_install_is_a_safe_no_op():
    before = sys.excepthook
    whytrail.uninstall()
    assert sys.excepthook is before


def test_sys_hook_prints_the_explanation_then_the_original_traceback(capsys):
    whytrail.install()
    _raise_and_capture_sys_hook(ValueError("bad input"))
    err = capsys.readouterr().err
    assert "why(ValueError: bad input)" in err
    assert "Traceback (most recent call last):" in err
    # explanation must come first -- that's the whole point of the demo
    assert err.index("why(") < err.index("Traceback (most recent call last):")


def test_sys_hook_preserves_the_full_traceback_not_just_the_summary():
    """Nothing is lost by installing this -- the real multi-frame
    traceback still prints in full, only whytrail's summary is added
    ahead of it."""
    whytrail.install()

    def inner():
        raise ValueError("boom")

    def outer():
        inner()

    def capture():
        try:
            outer()
        except ValueError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)

    import io
    from contextlib import redirect_stderr

    buf = io.StringIO()
    with redirect_stderr(buf):
        capture()
    err = buf.getvalue()
    assert "in outer" in err
    assert "in inner" in err
    assert "in capture" in err


def test_sys_hook_redacts_locals_by_default(capsys):
    whytrail.install()

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError as exc:
        sys.excepthook(type(exc), exc, exc.__traceback__)

    err = capsys.readouterr().err
    assert SECRET not in err
    assert "payment failed" in err


def test_sys_hook_log_locals_true_includes_locals(capsys):
    whytrail.install(log_locals=True)

    def charge():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    try:
        charge()
    except ValueError as exc:
        sys.excepthook(type(exc), exc, exc.__traceback__)

    assert SECRET in capsys.readouterr().err


def test_sys_hook_plain_true_uses_plain_text(capsys):
    whytrail.install(plain=True)
    _raise_and_capture_sys_hook(ValueError("bad input"))
    err = capsys.readouterr().err
    assert "Here's what happened, from the root cause to the final result:" in err


def test_threading_hook_reports_the_thread_name_and_redacts_by_default(capsys):
    whytrail.install()

    def worker():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed in worker")

    t = threading.Thread(target=worker, name="my-worker")
    t.start()
    t.join()

    err = capsys.readouterr().err
    assert "my-worker" in err
    assert "why(ValueError: payment failed in worker)" in err
    assert SECRET not in err


def test_main_thread_is_unaffected_by_a_worker_thread_crash():
    """install() must never make an unrelated thread's crash affect
    the main thread's own control flow."""
    whytrail.install()
    ran_after = []

    def worker():
        raise ValueError("boom")

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    ran_after.append(True)
    assert ran_after == [True]
