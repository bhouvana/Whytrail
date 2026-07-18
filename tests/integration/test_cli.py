from __future__ import annotations

import json
import subprocess
import sys
import textwrap


import whytrail
from whytrail.cli.__main__ import main
from whytrail.runtime.context import default_graph


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


def test_cli_plugins_lists_a_known_builtin_explainer(capsys):
    exit_code = main(["plugins"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "requests" in out
    assert "Auto-registering" in out
    assert "Integration-shaped" in out


def test_cli_plugins_json_is_valid_and_has_the_expected_shape(capsys):
    exit_code = main(["plugins", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "explainer" in payload
    assert "integration" in payload
    assert "external_entry_points" in payload
    names = {entry["name"] for entry in payload["explainer"]}
    assert "requests" in names
    requests_entry = next(e for e in payload["explainer"] if e["name"] == "requests")
    assert requests_entry["available"] is True  # requests is a real dev dependency here


def test_cli_plugins_marks_a_never_installed_library_unavailable(capsys):
    exit_code = main(["plugins", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    # zeep isn't a dev dependency of this project -- confirms `available`
    # reflects a real import check, not "always true."
    zeep_entry = next(e for e in payload["explainer"] if e["name"] == "zeep")
    assert zeep_entry["available"] is False


def test_cli_json_flag_after_script_path_is_silently_swallowed_by_remainder(tmp_path, capsys):
    """Documents real, confirmed argparse.REMAINDER behavior (not a
    whytrail-specific bug to 'fix' by reparsing): `script_args` must
    swallow everything after `script` so a script's own flags reach it
    unmolested, and --json/--graph are not exempt from that -- placed
    after the script path, they become part of script_args instead of
    whytrail's own parsed flags, with no output difference from
    omitting them entirely (see the warning test below for the actual
    fix: making that silence visible)."""
    script = _write_crashing_script(tmp_path)
    exit_code = main(["run", str(script), "--json"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""  # --json never took effect -- no JSON on stdout
    assert "boom from inner" in captured.err  # plain .text went to stderr instead


def test_cli_warns_when_json_flag_placed_after_script_path(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    main(["run", str(script), "--json"])
    err = capsys.readouterr().err
    assert "'--json' appeared after the script path" in err
    assert f"whytrail run --json {script}" in err


def test_cli_warns_when_graph_flag_placed_after_script_path(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    main(["run", str(script), "--graph"])
    err = capsys.readouterr().err
    assert "'--graph' appeared after the script path" in err


def test_cli_does_not_warn_when_flags_are_placed_correctly(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    main(["run", "--json", "--graph", str(script)])
    err = capsys.readouterr().err
    assert "appeared after the script path" not in err


def test_cli_does_not_warn_when_no_flags_are_used(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    main(["run", str(script)])
    err = capsys.readouterr().err
    assert "appeared after the script path" not in err


def test_cli_json_flag_before_script_path_actually_works(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    exit_code = main(["run", "--json", str(script)])
    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "boom from inner" in payload["subject"]


def test_cli_warning_does_not_block_a_script_that_wants_its_own_json_flag(tmp_path, capsys):
    """The fix warns, it does not reinterpret -- a script that
    genuinely wants a literal --json argument of its own must still
    receive it unchanged."""
    script = tmp_path / "wants_json_arg.py"
    script.write_text("import sys\nprint(sys.argv[1:])\n")
    exit_code = main(["run", str(script), "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "['--json']" in captured.out
    assert "'--json' appeared after the script path" in captured.err


# -- whytrail inspect --------------------------------------------------------


def _write_snapshot(tmp_path, name="snap.json"):
    with whytrail.trace():
        raw = whytrail.track({"price": "12.50"}, label="raw CSV row")
        whytrail.track(float(raw["price"]), derived_from=raw)
    path = tmp_path / name
    path.write_text(whytrail.snapshot())
    return path


def test_cli_inspect_reports_node_and_edge_counts(tmp_path, capsys):
    path = _write_snapshot(tmp_path)
    exit_code = main(["inspect", str(path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "2 nodes, 1 edges" in out
    assert "value: 2" in out
    assert "derived_from: 1" in out


def test_cli_inspect_json(tmp_path, capsys):
    path = _write_snapshot(tmp_path)
    exit_code = main(["inspect", str(path), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["node_count"] == 2
    assert payload["edge_count"] == 1
    assert payload["nodes_by_kind"] == {"value": 2}


def test_cli_inspect_missing_file(capsys):
    exit_code = main(["inspect", "does-not-exist.json"])
    assert exit_code == 1
    assert "no such file" in capsys.readouterr().err


def test_cli_inspect_rejects_a_non_snapshot_file(tmp_path, capsys):
    path = tmp_path / "not_a_snapshot.json"
    path.write_text("not even json{{{")
    exit_code = main(["inspect", str(path)])
    assert exit_code == 1
    assert "could not read" in capsys.readouterr().err


# -- whytrail explain ---------------------------------------------------------


def test_cli_explain_rerenders_a_captured_explanation(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    main(["run", "--json", str(script)])
    payload = capsys.readouterr().out
    json_file = tmp_path / "explanation.json"
    json_file.write_text(payload)

    exit_code = main(["explain", str(json_file)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "boom from inner" in out
    assert "why(ValueError: boom from inner)" in out


def test_cli_explain_graph_flag(tmp_path, capsys):
    script = _write_crashing_script(tmp_path)
    main(["run", "--json", str(script)])
    json_file = tmp_path / "explanation.json"
    json_file.write_text(capsys.readouterr().out)

    exit_code = main(["explain", str(json_file), "--graph"])
    assert exit_code == 0
    assert "graph TD" in capsys.readouterr().out


def test_cli_explain_missing_file(capsys):
    exit_code = main(["explain", "does-not-exist.json"])
    assert exit_code == 1
    assert "no such file" in capsys.readouterr().err


def test_cli_explain_rejects_malformed_json(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("not even json{{{")
    exit_code = main(["explain", str(path)])
    assert exit_code == 1
    assert "could not read" in capsys.readouterr().err


# -- whytrail diff -------------------------------------------------------------


def test_cli_diff_reports_added_and_removed_nodes(tmp_path, capsys):
    # default_graph().clear() between phases: diff compares two
    # independent captures (e.g. from two separate deployments/runs),
    # not two points within one process's ever-growing shared graph --
    # without clearing, "after" would be a superset of "before" within
    # the same test, which isn't the scenario diff is for.
    with whytrail.trace():
        whytrail.track("postgres://old", label="DATABASE_URL")
        whytrail.track("cache-value", label="CACHE_URL")
    before = tmp_path / "before.json"
    before.write_text(whytrail.snapshot())
    default_graph().clear()

    with whytrail.trace():
        whytrail.track("postgres://old", label="DATABASE_URL")
        whytrail.track("service-value", label="NEW_SERVICE_URL")
    after = tmp_path / "after.json"
    after.write_text(whytrail.snapshot())

    exit_code = main(["diff", str(before), str(after)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Added:" in out
    assert "NEW_SERVICE_URL" in out
    assert "Removed:" in out
    assert "CACHE_URL" in out
    assert "1 node(s) unchanged" in out


def test_cli_diff_json(tmp_path, capsys):
    with whytrail.trace():
        whytrail.track("a", label="ONLY_IN_BEFORE")
    before = tmp_path / "before.json"
    before.write_text(whytrail.snapshot())
    default_graph().clear()

    with whytrail.trace():
        whytrail.track("b", label="ONLY_IN_AFTER")
    after = tmp_path / "after.json"
    after.write_text(whytrail.snapshot())

    exit_code = main(["diff", str(before), str(after), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["added"] == [{"kind": "value", "label": "ONLY_IN_AFTER"}]
    assert payload["removed"] == [{"kind": "value", "label": "ONLY_IN_BEFORE"}]


def test_cli_diff_identical_snapshots_reports_no_differences(tmp_path, capsys):
    with whytrail.trace():
        whytrail.track("a", label="SAME_KEY")
    snapshot_data = whytrail.snapshot()
    before = tmp_path / "before.json"
    before.write_text(snapshot_data)
    after = tmp_path / "after.json"
    after.write_text(snapshot_data)

    exit_code = main(["diff", str(before), str(after)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "No node-level differences" in out
    assert "Added:" not in out
    assert "Removed:" not in out


def test_cli_diff_missing_file(tmp_path, capsys):
    existing = tmp_path / "before.json"
    existing.write_text(whytrail.snapshot())
    exit_code = main(["diff", str(existing), "does-not-exist.json"])
    assert exit_code == 1
    assert "no such file" in capsys.readouterr().err


# -- whytrail doctor ------------------------------------------------------------


def test_cli_doctor_reports_python_and_whytrail_versions(capsys):
    exit_code = main(["doctor"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Python version" in out
    assert "whytrail version" in out
    assert whytrail.__version__ in out


def test_cli_doctor_json(capsys):
    exit_code = main(["doctor", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_ok"] is True
    names = {check["name"] for check in payload["checks"]}
    assert "Python version" in names
    assert "explainer-shaped plugins active" in names


# -- whytrail demo ----------------------------------------------------------


def test_cli_demo_plain_shows_the_real_causal_chain(capsys):
    exit_code = main(["demo", "--plain"])
    assert exit_code == 0
    err = capsys.readouterr().err
    assert "why(KeyError: 'SUMMER')" in err
    assert "ValueError: discount code table missing region 'EU'" in err
    assert "which explicitly caused" in err
    assert "whytrail.install()" in err


def test_cli_demo_output_order_survives_merged_stdout_and_stderr(capsys):
    """Real bug found running this manually, not by reading the code:
    printing the explanation to stdout while the surrounding narration
    went to stderr let the two interleave out of order once a caller
    merged both streams (`whytrail demo 2>&1`) -- stdout/stderr buffer
    independently. Fixed by putting everything on one stream; this
    pins that down as the current file's own subprocess output, the
    only way to actually observe stream-merge ordering (capsys keeps
    out/err separate, which wouldn't have caught this)."""
    result = subprocess.run(
        [sys.executable, "-m", "whytrail.cli", "demo", "--plain"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    intro_index = next(i for i, line in enumerate(lines) if "explained with zero setup" in line)
    why_index = next(i for i, line in enumerate(lines) if line.startswith("why("))
    closing_index = next(i for i, line in enumerate(lines) if "Tier 1 answer" in line)
    assert intro_index < why_index < closing_index


def test_cli_demo_without_plain_falls_back_gracefully_when_rich_is_unavailable(capsys, monkeypatch):
    """Simulates the 'rich' extra not being installed -- must still
    print a real explanation, not crash or print nothing."""
    import builtins

    real_import = builtins.__import__

    def _blocking_import(name, *args, **kwargs):
        if name == "rich.console" or name.startswith("rich."):
            raise ImportError("simulated: rich is not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocking_import)
    exit_code = main(["demo"])
    assert exit_code == 0
    err = capsys.readouterr().err
    assert "why(KeyError: 'SUMMER')" in err
