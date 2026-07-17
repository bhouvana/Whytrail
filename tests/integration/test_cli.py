from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from whytrail.cli.__main__ import main


def _write_crashing_script(tmp_path):
    script = tmp_path / "crash.py"
    script.write_text(
        textwrap.dedent(
            """
            def inner():
                raise ValueError("boom from inner")

            def outer():
                inner()

            outer()
            """
        )
    )
    return script


def test_cli_run_returns_nonzero_on_uncaught_exception(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    exit_code = main(["run", str(script)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "boom from inner" in captured.err


def test_cli_run_json_flag_produces_valid_json(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    exit_code = main(["run", "--json", str(script)])
    assert exit_code == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["known"] is True
    assert "boom from inner" in payload["steps"][0]["description"]


def test_cli_run_missing_script_gives_a_clean_error_not_runpy_internals(tmp_path, capsys):
    missing = tmp_path / "does_not_exist.py"
    exit_code = main(["run", str(missing)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "no such file" in captured.err
    assert str(missing) in captured.err
    # The old behavior let runpy.run_path() raise, which why() then
    # rendered honestly but unhelpfully -- a <frozen runpy> frame with
    # the interpreter's own internal locals, not anything about the
    # user's actual mistake.
    assert "frozen runpy" not in captured.err
    assert "read_code" not in captured.err


def test_cli_run_clean_script_returns_zero(tmp_path, capsys):
    script = tmp_path / "clean.py"
    script.write_text("x = 1 + 1\n")
    exit_code = main(["run", str(script)])
    assert exit_code == 0


def test_cli_run_passes_through_script_arguments(tmp_path, capsys):
    script = tmp_path / "echo_args.py"
    script.write_text("import sys\nprint(sys.argv[1:])\n")
    exit_code = main(["run", str(script), "--", "hello", "world"])
    assert exit_code == 0
    assert "['hello', 'world']" in capsys.readouterr().out


def test_cli_as_subprocess_end_to_end(tmp_path):
    script = _write_crashing_script(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "whytrail.cli", "run", str(script)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "boom from inner" in result.stderr
