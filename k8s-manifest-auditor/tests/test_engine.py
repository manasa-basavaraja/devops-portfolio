"""Tests for src.engine and src.reporter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.engine import Engine, Policy
from src.findings import Severity
from src.reporter import to_json, to_markdown


GOOD_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: prod
  labels:
    app.kubernetes.io/name: api
    app.kubernetes.io/version: "1.0.0"
    owner: team
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api
    spec:
      serviceAccountName: api
      securityContext:
        runAsNonRoot: true
      containers:
        - name: api
          image: registry.example.com/api:1.0.0
          imagePullPolicy: IfNotPresent
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits:   {cpu: 500m, memory: 512Mi}
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
          livenessProbe:
            httpGet: {path: /h, port: 8080}
          readinessProbe:
            httpGet: {path: /r, port: 8080}
"""


BAD_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bad
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bad
  template:
    metadata:
      labels: {app: bad}
    spec:
      hostNetwork: true
      containers:
        - name: c
          image: legacy:latest
          imagePullPolicy: Always
          securityContext:
            privileged: true
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_default_policy_clean_on_good_manifest(tmp_path: Path) -> None:
    _write(tmp_path, "good.yaml", GOOD_DEPLOYMENT)
    engine = Engine()
    report = engine.audit_paths([tmp_path])
    assert report.findings == []
    assert report.files_scanned == 1
    assert report.documents_scanned == 1


def test_default_policy_flags_bad_manifest(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", BAD_DEPLOYMENT)
    engine = Engine()
    report = engine.audit_paths([tmp_path])
    rule_ids = {f.rule_id for f in report.findings}
    expected_subset = {
        "image-tag-pinned",
        "resource-requests",
        "resource-limits",
        "no-privileged",
        "no-host-network",
        "no-default-namespace",
        "required-labels",
        "service-account",
        "replicas-min",
        "run-as-non-root",
        "liveness-probe",
        "readiness-probe",
        "read-only-root-fs",
    }
    missing = expected_subset - rule_ids
    assert not missing, f"expected rules to fire but did not: {missing}"
    assert report.max_severity() == Severity.CRITICAL


def test_disable_rule_via_policy(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", BAD_DEPLOYMENT)
    policy = Policy.from_dict(
        {
            "fail_level": "high",
            "rules": {
                "no-privileged": {"enabled": False},
                "no-host-network": {"enabled": False},
            },
        }
    )
    engine = Engine(policy=policy)
    report = engine.audit_paths([tmp_path])
    rule_ids = {f.rule_id for f in report.findings}
    assert "no-privileged" not in rule_ids
    assert "no-host-network" not in rule_ids


def test_severity_override_via_policy(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", BAD_DEPLOYMENT)
    policy = Policy.from_dict(
        {
            "fail_level": "high",
            "rules": {"no-privileged": {"severity": "low"}},
        }
    )
    engine = Engine(policy=policy)
    report = engine.audit_paths([tmp_path])
    privs = [f for f in report.findings if f.rule_id == "no-privileged"]
    assert privs and all(f.severity == Severity.LOW for f in privs)


def test_unknown_rule_in_policy_raises() -> None:
    with pytest.raises(ValueError, match="unknown rule"):
        Policy.from_dict({"rules": {"nope": {"enabled": True}}})


def test_filter_at_or_above() -> None:
    policy = Policy.default()
    policy.fail_level = Severity.CRITICAL
    engine = Engine(policy=policy)
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        Path(d, "bad.yaml").write_text(BAD_DEPLOYMENT, encoding="utf-8")
        report = engine.audit_paths([d])
    over = report.filter_at_or_above(Severity.CRITICAL)
    assert all(f.severity == Severity.CRITICAL for f in over)
    assert len(over) >= 2


def test_to_json_round_trip(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", BAD_DEPLOYMENT)
    report = Engine().audit_paths([tmp_path])
    blob = to_json(report)
    parsed = json.loads(blob)
    assert parsed["files_scanned"] == 1
    assert "counts_by_severity" in parsed
    assert isinstance(parsed["findings"], list)


def test_to_markdown_includes_summary(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", BAD_DEPLOYMENT)
    report = Engine().audit_paths([tmp_path])
    md = to_markdown(report)
    assert "# Kubernetes Manifest Audit Report" in md
    assert "## Summary" in md
    assert "## Findings" in md
    assert "no-privileged" in md


def test_loader_error_becomes_finding(tmp_path: Path) -> None:
    _write(tmp_path, "broken.yaml", "foo: [\n  - unclosed\n")
    report = Engine().audit_paths([tmp_path])
    loader_findings = [f for f in report.findings if f.rule_id == "loader"]
    assert len(loader_findings) == 1
    assert loader_findings[0].severity == Severity.HIGH
