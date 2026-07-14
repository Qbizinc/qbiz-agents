"""``qba`` — the qbiz-agents command line. ``assay`` is its first command group.

- ``qba assay list-collectors`` — render the collector registry: what each check needs
  (files, questionnaires, or MCP connections), so a consultant can see at a glance what can
  be assessed given what a client can share or grant.
- ``qba assay run <profile.yaml>`` — run an assessment exactly as an engagement profile
  describes it and write the markdown report.

The CLI is a thin shell over ``qbiz_assay.profile`` — anything it can do, library callers can
do; nothing lives only here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qbiz_harness import AuditLog

from qbiz_assay.collectors import all_collectors
from qbiz_assay.profile import ProfileError, load_profile, run_profile
from qbiz_assay.report import render_markdown


def _cmd_list_collectors(_args: argparse.Namespace) -> int:
    for registered in all_collectors():
        info = registered.info
        print(f"{info.name}  [{info.mode.value}]")
        if info.description:
            print(f"    {info.description}")
        print(f"    dimensions: {', '.join(sorted(info.dimensions))}")
        for key, description in info.inputs.items():
            print(f"    input {key}: {description}")
        if info.requires_mcp:
            print(f"    requires MCP server(s): {', '.join(info.requires_mcp)}")
        print()
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        profile = load_profile(args.profile)
    except (OSError, ProfileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    audit_path: Path | None = Path(args.audit) if args.audit else None
    audit = AuditLog(path=audit_path) if audit_path else None

    try:
        assessment = run_profile(profile, audit=audit)
    except ProfileError as exc:
        # e.g. a connected collector whose MCP caller only a programmatic run can supply
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = render_markdown(
        assessment, audit_path=str(audit_path) if audit_path else None
    )
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"report written: {args.report}")
        if audit_path:
            print(f"audit trail:    {audit_path}")
    else:
        print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qba", description="qbiz-agents command line")
    commands = parser.add_subparsers(dest="command", required=True)

    assay = commands.add_parser("assay", help="Data & AI readiness assessments")
    assay_commands = assay.add_subparsers(dest="assay_command", required=True)

    list_parser = assay_commands.add_parser(
        "list-collectors", help="show every registered collector and what it needs"
    )
    list_parser.set_defaults(handler=_cmd_list_collectors)

    run_parser = assay_commands.add_parser(
        "run", help="run an assessment from an engagement profile"
    )
    run_parser.add_argument("profile", help="path to the engagement profile YAML")
    run_parser.add_argument(
        "--report", help="write the markdown report here (default: stdout)"
    )
    run_parser.add_argument(
        "--audit", help="persist the audit trail to this JSONL path"
    )
    run_parser.set_defaults(handler=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252 and mangle the report's typography.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
