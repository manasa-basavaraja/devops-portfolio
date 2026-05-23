"""JSON and Markdown reporters for an :class:`AuditReport`."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union

from .findings import AuditReport, Finding, Severity


def to_json(report: AuditReport, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), indent=indent, sort_keys=False)


def write_json(report: AuditReport, path: Union[str, Path], indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_json(report, indent=indent), encoding="utf-8")


_SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]


def to_markdown(report: AuditReport) -> str:
    lines: List[str] = []
    lines.append("# Kubernetes Manifest Audit Report")
    lines.append("")
    lines.append(
        f"Scanned **{report.files_scanned}** file(s), "
        f"**{report.documents_scanned}** document(s), "
        f"found **{len(report.findings)}** finding(s)."
    )
    lines.append("")

    counts = report.counts_by_severity
    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|------:|")
    for sev in _SEVERITY_ORDER:
        lines.append(f"| {sev.value} | {counts[sev.value]} |")
    lines.append("")

    if not report.findings:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"

    by_file: Dict[str, List[Finding]] = defaultdict(list)
    for f in report.findings:
        by_file[f.file].append(f)

    lines.append("## Findings")
    lines.append("")
    for file in sorted(by_file):
        lines.append(f"### `{file}`")
        lines.append("")
        lines.append("| Severity | Rule | Kind | Name | Path | Message |")
        lines.append("|----------|------|------|------|------|---------|")
        sorted_findings = sorted(
            by_file[file],
            key=lambda f: (-f.severity.rank, f.rule_id, f.doc_index, f.path),
        )
        for f in sorted_findings:
            lines.append(
                "| {sev} | `{rule}` | {kind} | {name} | `{path}` | {msg} |".format(
                    sev=f.severity.value,
                    rule=f.rule_id,
                    kind=f.kind or "-",
                    name=f.name or "-",
                    path=f.path or "-",
                    msg=f.message.replace("|", "\\|"),
                )
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def write_markdown(report: AuditReport, path: Union[str, Path]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_markdown(report), encoding="utf-8")
