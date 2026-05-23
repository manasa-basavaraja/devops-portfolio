"""CLI entry point: ``python -m src.cli audit <path> [--policy ...] ...``.

Exit codes:
    0 - no findings at or above the fail level
    1 - findings at or above the fail level
    2 - usage / parsing error (invalid YAML, bad policy, missing path)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from .engine import Engine, Policy
from .findings import Severity
from .reporter import to_json, to_markdown, write_json, write_markdown


_LOG = logging.getLogger("k8s_audit")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="k8s-audit",
        description="Audit Kubernetes manifests against opinionated policies.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Audit one or more files / directories.")
    audit.add_argument(
        "paths",
        nargs="+",
        help="Files or directories of YAML manifests to audit.",
    )
    audit.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Path to a policy.yaml file. Defaults to the built-in policy.",
    )
    audit.add_argument(
        "--fail-level",
        type=str,
        default=None,
        choices=[s.value for s in Severity],
        help="Minimum severity that causes a non-zero exit "
        "(overrides the policy's fail_level).",
    )
    audit.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write a JSON report to this path.",
    )
    audit.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Write a Markdown report to this path.",
    )
    audit.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the human-readable findings table on stdout.",
    )

    list_rules = sub.add_parser("list-rules", help="Print the built-in rules and exit.")
    list_rules.set_defaults(_handler=_handle_list_rules)
    audit.set_defaults(_handler=_handle_audit)
    return parser


def _handle_list_rules(_: argparse.Namespace) -> int:
    from .rules import RULES

    print(f"{'rule_id':<25} {'default_severity':<10}  description")
    print("-" * 80)
    for r in RULES:
        print(f"{r.id:<25} {r.default_severity.value:<10}  {r.description}")
    return 0


def _handle_audit(args: argparse.Namespace) -> int:
    if args.policy is not None:
        try:
            policy = Policy.from_file(args.policy)
        except (FileNotFoundError, ValueError) as exc:
            _LOG.error("policy error: %s", exc)
            return 2
    else:
        policy = Policy.default()

    if args.fail_level is not None:
        policy.fail_level = Severity.parse(args.fail_level)

    for p in args.paths:
        if not Path(p).exists():
            _LOG.error("path does not exist: %s", p)
            return 2

    engine = Engine(policy=policy)
    report = engine.audit_paths(args.paths)

    if args.json is not None:
        write_json(report, args.json)
        _LOG.info("wrote JSON report: %s", args.json)
    if args.markdown is not None:
        write_markdown(report, args.markdown)
        _LOG.info("wrote Markdown report: %s", args.markdown)

    if not args.quiet:
        _print_human_summary(report, policy.fail_level)

    over = report.filter_at_or_above(policy.fail_level)
    return 1 if over else 0


def _print_human_summary(report, fail_level: Severity) -> None:
    counts = report.counts_by_severity
    print(
        f"scanned {report.files_scanned} file(s), {report.documents_scanned} doc(s), "
        f"found {len(report.findings)} finding(s) "
        f"(critical={counts['critical']}, high={counts['high']}, "
        f"medium={counts['medium']}, low={counts['low']})"
    )
    if not report.findings:
        return
    print()
    for f in sorted(report.findings, key=lambda f: (-f.severity.rank, f.file, f.path)):
        print(
            f"  [{f.severity.value:<8}] {f.rule_id:<22} "
            f"{Path(f.file).name}#{f.doc_index} {f.kind}/{f.name or '-'} "
            f"@ {f.path or '-'}: {f.message}"
        )
    over = report.filter_at_or_above(fail_level)
    print()
    print(
        f"fail-level={fail_level.value}: "
        f"{len(over)} finding(s) at or above threshold"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
