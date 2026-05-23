"""Rule engine: applies a configured set of rules to parsed documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import yaml

from .findings import AuditReport, Finding, Severity
from .loader import LoaderError, ParsedDoc, iter_yaml_files, load_documents
from .rules import RULES, RULES_BY_ID, RuleSpec


@dataclass
class RuleConfig:
    spec: RuleSpec
    enabled: bool
    severity: Severity
    params: Dict[str, Any]


@dataclass
class Policy:
    rules: List[RuleConfig]
    fail_level: Severity = Severity.HIGH

    @classmethod
    def default(cls) -> "Policy":
        return cls(
            rules=[
                RuleConfig(
                    spec=r,
                    enabled=True,
                    severity=r.default_severity,
                    params={},
                )
                for r in RULES
            ],
            fail_level=Severity.HIGH,
        )

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Policy":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"policy file not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{p}: top-level policy must be a mapping")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Policy":
        rules_cfg: Dict[str, Any] = data.get("rules") or {}
        if not isinstance(rules_cfg, dict):
            raise ValueError("`rules` must be a mapping of rule_id -> config")

        unknown = sorted(set(rules_cfg) - set(RULES_BY_ID))
        if unknown:
            raise ValueError(f"unknown rule(s) in policy: {', '.join(unknown)}")

        configured: List[RuleConfig] = []
        for spec in RULES:
            entry = rules_cfg.get(spec.id) or {}
            if not isinstance(entry, dict):
                raise ValueError(f"rules.{spec.id} must be a mapping")
            severity = (
                Severity.parse(entry["severity"])
                if "severity" in entry
                else spec.default_severity
            )
            configured.append(
                RuleConfig(
                    spec=spec,
                    enabled=bool(entry.get("enabled", True)),
                    severity=severity,
                    params=dict(entry.get("params") or {}),
                )
            )

        fail_level = Severity.parse(str(data.get("fail_level", "high")))
        return cls(rules=configured, fail_level=fail_level)


class Engine:
    """Runs a :class:`Policy` against a stream of parsed documents."""

    def __init__(self, policy: Optional[Policy] = None) -> None:
        self.policy = policy or Policy.default()

    def audit_documents(self, docs: Iterable[ParsedDoc]) -> AuditReport:
        report = AuditReport()
        files: set = set()
        for doc in docs:
            files.add(doc.file)
            report.documents_scanned += 1
            for cfg in self.policy.rules:
                if not cfg.enabled:
                    continue
                params = dict(cfg.params)
                params["_severity"] = cfg.severity
                try:
                    findings = list(cfg.spec.fn(doc, params))
                except Exception as exc:
                    findings = [
                        Finding(
                            rule_id=cfg.spec.id,
                            severity=Severity.LOW,
                            message=f"rule raised {type(exc).__name__}: {exc}",
                            file=doc.file,
                            doc_index=doc.doc_index,
                            kind=doc.kind,
                            name=doc.name,
                            namespace=doc.namespace,
                            path="",
                        )
                    ]
                for f in findings:
                    f.severity = cfg.severity
                    report.findings.append(f)
        report.files_scanned = len(files)
        return report

    def audit_paths(self, paths: Iterable[Union[str, Path]]) -> AuditReport:
        docs: List[ParsedDoc] = []
        load_errors: List[Finding] = []
        seen: set = set()
        for p in paths:
            for f in iter_yaml_files(p):
                key = str(f.resolve())
                if key in seen:
                    continue
                seen.add(key)
                try:
                    docs.extend(load_documents(f))
                except LoaderError as exc:
                    load_errors.append(
                        Finding(
                            rule_id="loader",
                            severity=Severity.HIGH,
                            message=str(exc),
                            file=str(f),
                            doc_index=0,
                            kind="",
                            name="",
                        )
                    )
        report = self.audit_documents(docs)
        if load_errors:
            report.findings = load_errors + report.findings
        return report
