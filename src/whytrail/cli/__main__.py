"""whytrail CLI (ADR §14 -- v2.0): `whytrail run script.py` runs a script
and, if it raises, prints why() instead of a bare traceback.

Seven subcommands total (0.3): `run`, `plugins`, `inspect`, `explain`,
`diff`, `doctor`, `demo`. Grown past the "no third subcommand without the
same bar" line the module docstring used to draw -- each one added in
0.3 still reuses existing public API (`core.graph.all_nodes`/
`all_edges`, `Explanation.json`/`from_json`, `registry.list_*`,
`why()`/`.rich()`) rather than adding new engine surface; none of them
changes resolution order or the graph model itself. `demo` specifically
exists to answer one question: what can a user run in the first 30
seconds after `pip install whytrail`, with zero code of their own,
that shows what `why()` actually looks like? Everything else in the
CLI assumes a script or a snapshot file already exists.
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
import typing as t
from pathlib import Path

import whytrail
from whytrail import registry
from whytrail.core import serialize
from whytrail.core.explanation import Explanation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whytrail", description="Python tells you where. whytrail tells you why a value is the way it is."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run a script; on an uncaught exception, print why() instead of a bare traceback."
    )
    run_parser.add_argument("script", help="path to the Python script to run")
    run_parser.add_argument("script_args", nargs=argparse.REMAINDER, help="arguments passed to the script")
    run_parser.add_argument("--json", action="store_true", help="print the explanation as JSON")
    run_parser.add_argument("--graph", action="store_true", help="also print a Mermaid provenance graph")

    plugins_parser = subparsers.add_parser(
        "plugins", help="List whytrail's 63 bundled integrations and whether each is active in this environment."
    )
    plugins_parser.add_argument("--json", action="store_true", help="print the plugin list as JSON")

    inspect_parser = subparsers.add_parser(
        "inspect", help="Summarize a snapshot() file: node/edge counts by kind."
    )
    inspect_parser.add_argument("snapshot", help="path to a snapshot file written by whytrail.snapshot()")
    inspect_parser.add_argument("--json", action="store_true", help="print the summary as JSON")

    explain_parser = subparsers.add_parser(
        "explain", help="Re-render a previously captured explanation (from `whytrail run --json`)."
    )
    explain_parser.add_argument("file", help="path to a JSON file produced by `whytrail run --json`")
    explain_parser.add_argument("--graph", action="store_true", help="also print a Mermaid provenance graph")

    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare two snapshot() files: which nodes were added or removed.",
        description=(
            "Compare two snapshot() files: which nodes were added or removed. "
            "For two independent captures (two deployments, two test runs, "
            "before/after a config change) -- not two snapshot() calls made "
            "moments apart in the same live process without clearing the graph "
            "between them, since the default graph accumulates across a "
            "process's lifetime and a later snapshot would then be a superset "
            "of an earlier one rather than a meaningful comparison."
        ),
    )
    diff_parser.add_argument("before", help="path to the earlier snapshot file")
    diff_parser.add_argument("after", help="path to the later snapshot file")
    diff_parser.add_argument("--json", action="store_true", help="print the diff as JSON")

    doctor_parser = subparsers.add_parser(
        "doctor", help="Check whytrail's own install health: Python version, extras, active plugins."
    )
    doctor_parser.add_argument("--json", action="store_true", help="print the checks as JSON")

    demo_parser = subparsers.add_parser(
        "demo",
        help="See what why() looks like on a real exception, with zero setup and zero code of your own.",
    )
    demo_parser.add_argument(
        "--plain", action="store_true", help="force plain text even if the 'rich' extra is installed"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "plugins":
        return _plugins(args)
    if args.command == "inspect":
        return _inspect(args)
    if args.command == "explain":
        return _explain(args)
    if args.command == "diff":
        return _diff(args)
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "demo":
        return _demo(args)
    parser.print_help()
    return 1


_KNOWN_RUN_FLAGS = ("--json", "--graph")


def _warn_about_swallowed_flags(args: argparse.Namespace) -> None:
    """`script_args` uses `nargs=argparse.REMAINDER` so a script's own
    flags (e.g. `whytrail run script.py --verbose`) reach the script
    unmolested rather than confusing whytrail's own parser -- correct
    behavior for a wrapper CLI. The real gap it opens: `--json`/
    `--graph` placed *after* the script path -- the order this
    project's own docs write it, and the only order most CLI users
    would guess -- get swallowed into `script_args` by that same
    REMAINDER, with no error at all (confirmed, not hypothetical: this
    is standard argparse.REMAINDER behavior, not a whytrail-specific
    parsing bug). A CI script piping `whytrail run script.py --json`
    into a JSON parser gets plain text instead and fails downstream
    with no clue why.

    Warns rather than silently reinterpreting the flag as whytrail's
    own: the script's own argv might genuinely want a literal --json
    argument, and guessing which meaning was intended would trade one
    kind of silent surprise for another. This makes the actual failure
    (silence) visible without changing what actually ran.
    """
    swallowed = [flag for flag in _KNOWN_RUN_FLAGS if flag in args.script_args]
    if not swallowed:
        return
    flags = " and ".join(repr(f) for f in swallowed)
    example = f"whytrail run {' '.join(swallowed)} {args.script}"
    print(
        f"whytrail: note: {flags} appeared after the script path, so it was passed "
        f"to the script instead of enabled for whytrail -- put it before the script "
        f"path instead (e.g. `{example}`)",
        file=sys.stderr,
    )


def _run(args: argparse.Namespace) -> int:
    # Checked explicitly rather than letting runpy.run_path() raise its
    # own FileNotFoundError: that error's traceback frame is inside
    # <frozen runpy>, so why() (correctly) renders runpy's own internal
    # locals (a raw function repr, a memory address) instead of anything
    # about the user's actual mistake -- accurate, but not a good first
    # impression for the one command a brand-new user is most likely to
    # run first.
    if not Path(args.script).is_file():
        print(f"whytrail: no such file: {args.script}", file=sys.stderr)
        return 1

    _warn_about_swallowed_flags(args)

    old_argv = sys.argv
    sys.argv = [args.script, *args.script_args]
    try:
        runpy.run_path(args.script, run_name="__main__")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except BaseException as exc:  # noqa: BLE001 - the whole point is to catch whatever the script raises
        explanation = whytrail.why(exc)
        _report(explanation, as_json=args.json, with_graph=args.graph)
        return 1
    finally:
        sys.argv = old_argv
    return 0


def _report(explanation: "whytrail.Explanation", *, as_json: bool, with_graph: bool) -> None:
    if as_json:
        payload: dict[str, t.Any] = explanation.json()
        if with_graph:
            payload["graph"] = explanation.graph()
        print(json.dumps(payload, indent=2))
        return
    print(explanation.text, file=sys.stderr)
    if with_graph:
        print(file=sys.stderr)
        print(explanation.graph(), file=sys.stderr)


def _plugins(args: argparse.Namespace) -> int:
    explainers = registry.list_builtin_plugins()
    hooks = registry.list_hook_based_plugins()
    external = registry.list_entry_point_plugins()

    if args.json:
        payload = {
            "explainer": [{"name": p.name, "available": p.available} for p in explainers],
            "integration": [{"name": p.name, "available": p.available} for p in hooks],
            "external_entry_points": external,
        }
        print(json.dumps(payload, indent=2))
        return 0

    active = [p for p in explainers if p.available]
    print(f"Auto-registering (explainer-shaped), active in this environment: {len(active)}/{len(explainers)}")
    for p in explainers:
        mark = "x" if p.available else " "
        print(f"  [{mark}] {p.name}")

    print()
    hook_available = [p for p in hooks if p.available]
    print(f"Integration-shaped (need explicit install()/wiring in your code): {len(hook_available)}/{len(hooks)} importable")
    for p in hooks:
        mark = "x" if p.available else " "
        print(f"  [{mark}] {p.name}")

    print()
    if external:
        print(f"External plugins found via the whytrail.explainers entry point: {', '.join(external)}")
    else:
        print("No external plugins found via the whytrail.explainers entry point.")
    return 0


def _inspect(args: argparse.Namespace) -> int:
    path = Path(args.snapshot)
    if not path.is_file():
        print(f"whytrail: no such file: {args.snapshot}", file=sys.stderr)
        return 1
    try:
        graph = serialize.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"whytrail: could not read {args.snapshot} as a snapshot: {exc}", file=sys.stderr)
        return 1

    nodes = graph.all_nodes()
    edges = graph.all_edges()
    node_kind_counts: dict[str, int] = {}
    for node in nodes:
        node_kind_counts[node.kind.value] = node_kind_counts.get(node.kind.value, 0) + 1
    edge_kind_counts: dict[str, int] = {}
    for edge in edges:
        edge_kind_counts[edge.kind.value] = edge_kind_counts.get(edge.kind.value, 0) + 1
    # Every node in a loaded snapshot is tombstoned, always (see
    # core/serialize.py: "replayed graphs never hold live object
    # references" -- 100% is the only value this could ever be, so a
    # count of it here would look like a signal when it's actually a
    # constant. Not shown for that reason, confirmed by testing this
    # against a real snapshot before writing it this way.

    if args.json:
        payload = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes_by_kind": node_kind_counts,
            "edges_by_kind": edge_kind_counts,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"{args.snapshot}: {len(nodes)} nodes, {len(edges)} edges")
    print()
    print("Nodes by kind:")
    for kind, count in sorted(node_kind_counts.items()):
        print(f"  {kind}: {count}")
    print()
    print("Edges by kind:")
    for kind, count in sorted(edge_kind_counts.items()):
        print(f"  {kind}: {count}")
    return 0


def _explain(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        print(f"whytrail: no such file: {args.file}", file=sys.stderr)
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        explanation = Explanation.from_json(data)
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"whytrail: could not read {args.file} as a whytrail explanation: {exc}", file=sys.stderr)
        return 1

    print(explanation.text)
    if args.graph:
        print()
        print(explanation.graph())
    return 0


def _diff(args: argparse.Namespace) -> int:
    before_path = Path(args.before)
    after_path = Path(args.after)
    for path in (before_path, after_path):
        if not path.is_file():
            print(f"whytrail: no such file: {path}", file=sys.stderr)
            return 1
    try:
        before_graph = serialize.loads(before_path.read_text(encoding="utf-8"))
        after_graph = serialize.loads(after_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"whytrail: could not read one of these as a snapshot: {exc}", file=sys.stderr)
        return 1

    # Node IDs are process-lifetime counters, not stable across two
    # independently-captured snapshots -- (kind, label) is the closest
    # thing to a real identity two separate captures share. A node
    # whose label changed between captures therefore shows as one
    # removed + one added entry, not a single "changed" one: whytrail
    # has no way to know two differently-labeled nodes are "the same
    # thing that changed" without guessing, and guessing here would be
    # exactly the kind of fabrication why() itself never does.
    before_keys = {(n.kind.value, n.label) for n in before_graph.all_nodes()}
    after_keys = {(n.kind.value, n.label) for n in after_graph.all_nodes()}
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    unchanged = len(before_keys & after_keys)

    if args.json:
        payload = {
            "added": [{"kind": kind, "label": label} for kind, label in added],
            "removed": [{"kind": kind, "label": label} for kind, label in removed],
            "unchanged_count": unchanged,
        }
        print(json.dumps(payload, indent=2))
        return 0

    if not added and not removed:
        print("No node-level differences.")
    if added:
        print("Added:")
        for kind, label in added:
            print(f"  [{kind}] {label}")
    if removed:
        if added:
            print()
        print("Removed:")
        for kind, label in removed:
            print(f"  [{kind}] {label}")
    print()
    print(
        f"{unchanged} node(s) unchanged. Matched by (kind, label): a node whose value changed "
        f"between the two snapshots but kept the same label appears as one removed and one added "
        f"entry above, not a single 'changed' one."
    )
    return 0


def _doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append(("Python version", py_ok, sys.version.split()[0] + ("" if py_ok else " (below whytrail's 3.10 floor)")))
    checks.append(("whytrail version", True, whytrail.__version__))

    try:
        import rich  # noqa: F401

        rich_detail = "installed"
        rich_ok = True
    except ImportError:
        rich_detail = "not installed -- pip install whytrail[rich] for .rich()/richer CLI output"
        rich_ok = False
    checks.append(("rich extra (Explanation.rich(), CLI)", rich_ok, rich_detail))

    explainers = registry.list_builtin_plugins()
    hooks = registry.list_hook_based_plugins()
    external = registry.list_entry_point_plugins()
    active_explainers = sum(1 for p in explainers if p.available)
    available_hooks = sum(1 for p in hooks if p.available)
    # Zero active plugins isn't wrong by itself -- core whytrail works
    # with none installed -- so this check is always "ok", informational.
    checks.append(("explainer-shaped plugins active", True, f"{active_explainers}/{len(explainers)}"))
    checks.append(("integration-shaped plugins importable", True, f"{available_hooks}/{len(hooks)}"))
    checks.append(("external entry-point plugins found", True, str(len(external)) if external else "none"))

    if args.json:
        payload = {
            "checks": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks],
            "all_ok": all(ok for _, ok, _ in checks),
        }
        print(json.dumps(payload, indent=2))
        return 0 if payload["all_ok"] else 1

    for name, ok, detail in checks:
        mark = "OK" if ok else "!!"
        print(f"[{mark}] {name}: {detail}")
    return 0 if all(ok for _, ok, _ in checks) else 1


def _demo(args: argparse.Namespace) -> int:
    """Zero-setup, zero-code demonstration of why(): raises a real,
    two-level exception chain (the same scenario `examples/
    ex_install_hook.py` uses -- a config lookup failing, chained into
    the KeyError it causes) and prints why()'s answer. Not a mockup:
    the exception is really raised and really caught, the same way
    `whytrail run`/`whytrail.install()` handle one.

    Uses `.rich()` when the `rich` extra is installed (falls back to
    plain `.text` otherwise, or with --plain) -- this is the one CLI
    command where the terminal output *is* the point, not a byproduct
    of debugging a real script.
    """

    # compile()/exec() with a synthetic filename rather than plain
    # nested functions: a real user's first `whytrail demo` run showed
    # why()'s location line pointing into whytrail's own installed
    # cli/__main__.py (frame.f_code.co_filename is wherever a function
    # is *defined*, not run from) -- confusing for a brand-new user with
    # no idea what that file is. `<whytrail demo>` reads as demo content
    # instead of an accidental peek into site-packages.
    demo_source = (
        "def load_codes(region):\n"
        "    table = {}\n"
        "    if region not in table:\n"
        "        raise ValueError(f\"discount code table missing region {region!r}\")\n"
        "    return table\n"
        "\n"
        "def apply_discount(price, code):\n"
        "    try:\n"
        "        load_codes('EU')\n"
        "    except ValueError as exc:\n"
        "        raise KeyError(code) from exc\n"
    )
    demo_globals: dict[str, t.Any] = {}
    exec(compile(demo_source, "<whytrail demo>", "exec"), demo_globals)  # noqa: S102 - fixed, no-input demo code

    try:
        demo_globals["apply_discount"](12.5, "SUMMER")
    except KeyError as exc:
        explanation = whytrail.why(exc)

    # Real bug, found by running this rather than reading it: printing
    # explanation.text to stdout while every surrounding line goes to
    # stderr let the two interleave out of order once both streams were
    # merged (e.g. `whytrail demo 2>&1`, or some terminals/redirects) --
    # stdout and stderr buffer independently. Everything in this command
    # goes to stderr now, the same stream _report() already uses for
    # `whytrail run`'s explanation output, so there's one consistent
    # stream and no ordering surprise regardless of how output is
    # captured.
    print("A real exception, explained with zero setup -- this is why(exc):", file=sys.stderr)
    print(file=sys.stderr)

    rendered_rich = False
    if not args.plain:
        try:
            from rich.console import Console

            Console(file=sys.stderr).print(explanation.rich(panel=True))
            rendered_rich = True
        except ImportError:
            pass
    if not rendered_rich:
        print(explanation.text, file=sys.stderr)

    print(file=sys.stderr)
    print(
        "That's a Tier 1 answer: zero config, reconstructed entirely from data\n"
        "CPython already retains for every exception (__traceback__, __cause__,\n"
        "__context__). Add this near the top of your own program and every\n"
        "uncaught exception shows this automatically, not just this demo:\n"
        "\n"
        "    import whytrail\n"
        "    whytrail.install()\n",
        file=sys.stderr,
    )
    if not rendered_rich and not args.plain:
        print("(pip install whytrail[rich] for the panel/tree rendering shown in the README)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
