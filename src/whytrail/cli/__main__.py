"""whytrail CLI (ADR §14 -- v2.0): `whytrail run script.py` runs a script
and, if it raises, prints why() instead of a bare traceback.

Deliberately the only subcommand for now -- a CLI that grows verbs
ahead of demonstrated need repeats the mistake ADR §10 rejected for
the Python API itself.
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
import typing as t
from pathlib import Path

import whytrail


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whytrail", description="Python tells you where. whytrail tells you why.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run a script; on an uncaught exception, print why() instead of a bare traceback."
    )
    run_parser.add_argument("script", help="path to the Python script to run")
    run_parser.add_argument("script_args", nargs=argparse.REMAINDER, help="arguments passed to the script")
    run_parser.add_argument("--json", action="store_true", help="print the explanation as JSON")
    run_parser.add_argument("--graph", action="store_true", help="also print a Mermaid provenance graph")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    parser.print_help()
    return 1


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


if __name__ == "__main__":
    raise SystemExit(main())
