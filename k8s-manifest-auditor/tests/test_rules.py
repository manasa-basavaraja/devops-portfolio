"""Tests for individual rule implementations in src.rules."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pytest

from src.findings import Severity
from src.loader import ParsedDoc
from src.rules import (
    check_image_pull_policy,
    check_image_tag_pinned,
    check_liveness_probe,
    check_no_default_namespace,
    check_no_host_network,
    check_no_host_pid,
    check_no_privileged,
    check_read_only_root_fs,
    check_readiness_probe,
    check_replicas_min,
    check_required_labels,
    check_resource_limits,
    check_resource_requests,
    check_run_as_non_root,
    check_service_account,
)


def _doc(body: Dict[str, Any]) -> ParsedDoc:
    return ParsedDoc(file="<mem>", doc_index=0, body=body)


def _params(severity: Severity = Severity.HIGH, **extra: Any) -> Dict[str, Any]:
    p: Dict[str, Any] = {"_severity": severity}
    p.update(extra)
    return p


def _ids(findings: Iterable[Any]) -> List[str]:
    return sorted(f.rule_id for f in findings)


def _make_deployment(container: Dict[str, Any], **pod_extras: Any) -> Dict[str, Any]:
    pod_spec = {"containers": [container]}
    pod_spec.update(pod_extras)
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "x", "namespace": "ns"},
        "spec": {"template": {"spec": pod_spec}},
    }


def test_image_tag_latest_flagged() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "nginx:latest"}))
    findings = list(check_image_tag_pinned(doc, _params()))
    assert _ids(findings) == ["image-tag-pinned"]


def test_image_tag_missing_flagged() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "nginx"}))
    findings = list(check_image_tag_pinned(doc, _params()))
    assert _ids(findings) == ["image-tag-pinned"]


def test_image_tag_pinned_ok() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "nginx:1.27.1"}))
    assert list(check_image_tag_pinned(doc, _params())) == []


def test_image_tag_digest_ok() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "nginx@sha256:abc123"}))
    assert list(check_image_tag_pinned(doc, _params())) == []


def test_image_pull_policy_always_with_pinned_flagged() -> None:
    doc = _doc(
        _make_deployment(
            {"name": "c", "image": "nginx:1.27.1", "imagePullPolicy": "Always"}
        )
    )
    findings = list(check_image_pull_policy(doc, _params(severity=Severity.LOW)))
    assert _ids(findings) == ["image-pull-policy"]


def test_image_pull_policy_missing_with_unpinned_flagged() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "nginx:latest"}))
    findings = list(check_image_pull_policy(doc, _params(severity=Severity.LOW)))
    assert _ids(findings) == ["image-pull-policy"]


def test_resource_requests_missing_flagged() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "nginx:1"}))
    assert _ids(check_resource_requests(doc, _params())) == ["resource-requests"]


def test_resource_limits_missing_flagged() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "nginx:1"}))
    assert _ids(check_resource_limits(doc, _params())) == ["resource-limits"]


def test_resource_partial_flagged() -> None:
    doc = _doc(
        _make_deployment(
            {
                "name": "c",
                "image": "nginx:1",
                "resources": {"requests": {"cpu": "100m"}, "limits": {"memory": "1Gi"}},
            }
        )
    )
    assert _ids(check_resource_requests(doc, _params())) == ["resource-requests"]
    assert _ids(check_resource_limits(doc, _params())) == ["resource-limits"]


def test_resource_complete_ok() -> None:
    doc = _doc(
        _make_deployment(
            {
                "name": "c",
                "image": "nginx:1",
                "resources": {
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                    "limits": {"cpu": "500m", "memory": "512Mi"},
                },
            }
        )
    )
    assert list(check_resource_requests(doc, _params())) == []
    assert list(check_resource_limits(doc, _params())) == []


def test_liveness_and_readiness_probes() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "n:1"}))
    assert _ids(check_liveness_probe(doc, _params(severity=Severity.MEDIUM))) == ["liveness-probe"]
    assert _ids(check_readiness_probe(doc, _params(severity=Severity.MEDIUM))) == ["readiness-probe"]
    doc_with = _doc(
        _make_deployment(
            {
                "name": "c",
                "image": "n:1",
                "livenessProbe": {"httpGet": {"path": "/h", "port": 8080}},
                "readinessProbe": {"httpGet": {"path": "/r", "port": 8080}},
            }
        )
    )
    assert list(check_liveness_probe(doc_with, _params(severity=Severity.MEDIUM))) == []
    assert list(check_readiness_probe(doc_with, _params(severity=Severity.MEDIUM))) == []


def test_run_as_non_root_pod_level_satisfies() -> None:
    body = _make_deployment(
        {"name": "c", "image": "n:1"},
        securityContext={"runAsNonRoot": True},
    )
    doc = _doc(body)
    assert list(check_run_as_non_root(doc, _params())) == []


def test_run_as_non_root_missing_flagged() -> None:
    doc = _doc(_make_deployment({"name": "c", "image": "n:1"}))
    assert _ids(check_run_as_non_root(doc, _params())) == ["run-as-non-root"]


def test_read_only_root_fs() -> None:
    bad = _doc(_make_deployment({"name": "c", "image": "n:1"}))
    assert _ids(check_read_only_root_fs(bad, _params(severity=Severity.MEDIUM))) == ["read-only-root-fs"]
    good = _doc(
        _make_deployment(
            {
                "name": "c",
                "image": "n:1",
                "securityContext": {"readOnlyRootFilesystem": True},
            }
        )
    )
    assert list(check_read_only_root_fs(good, _params(severity=Severity.MEDIUM))) == []


def test_no_privileged() -> None:
    bad = _doc(
        _make_deployment(
            {
                "name": "c",
                "image": "n:1",
                "securityContext": {"privileged": True},
            }
        )
    )
    assert _ids(check_no_privileged(bad, _params(severity=Severity.CRITICAL))) == ["no-privileged"]
    ok = _doc(_make_deployment({"name": "c", "image": "n:1"}))
    assert list(check_no_privileged(ok, _params(severity=Severity.CRITICAL))) == []


def test_no_host_network_and_pid() -> None:
    body = _make_deployment(
        {"name": "c", "image": "n:1"},
        hostNetwork=True,
        hostPID=True,
        hostIPC=True,
    )
    doc = _doc(body)
    assert _ids(check_no_host_network(doc, _params(severity=Severity.CRITICAL))) == ["no-host-network"]
    assert _ids(check_no_host_pid(doc, _params(severity=Severity.CRITICAL))) == ["no-host-pid", "no-host-pid"]


def test_no_default_namespace() -> None:
    no_ns = _doc({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "x"}})
    explicit_default = _doc(
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "x", "namespace": "default"},
        }
    )
    ok = _doc(
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "x", "namespace": "team-a"},
        }
    )
    assert _ids(check_no_default_namespace(no_ns, _params(severity=Severity.MEDIUM))) == [
        "no-default-namespace"
    ]
    assert _ids(check_no_default_namespace(explicit_default, _params(severity=Severity.MEDIUM))) == [
        "no-default-namespace"
    ]
    assert list(check_no_default_namespace(ok, _params(severity=Severity.MEDIUM))) == []


def test_no_default_namespace_skips_cluster_scoped() -> None:
    cr = _doc({"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "ClusterRole", "metadata": {"name": "r"}})
    assert list(check_no_default_namespace(cr, _params(severity=Severity.MEDIUM))) == []


def test_required_labels() -> None:
    keys = ["app.kubernetes.io/name", "owner"]
    bad = _doc(
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "x", "labels": {"owner": "team"}},
            "spec": {"template": {"spec": {"containers": []}}},
        }
    )
    assert _ids(check_required_labels(bad, _params(severity=Severity.MEDIUM, keys=keys))) == [
        "required-labels"
    ]
    good = _doc(
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "x",
                "labels": {"app.kubernetes.io/name": "x", "owner": "team"},
            },
            "spec": {"template": {"spec": {"containers": []}}},
        }
    )
    assert list(check_required_labels(good, _params(severity=Severity.MEDIUM, keys=keys))) == []


def test_service_account() -> None:
    doc_default = _doc(_make_deployment({"name": "c", "image": "n:1"}))
    assert _ids(check_service_account(doc_default, _params(severity=Severity.LOW))) == [
        "service-account"
    ]
    doc_ok = _doc(
        _make_deployment({"name": "c", "image": "n:1"}, serviceAccountName="foo")
    )
    assert list(check_service_account(doc_ok, _params(severity=Severity.LOW))) == []


@pytest.mark.parametrize(
    "replicas, threshold, expect_finding",
    [
        (1, 2, True),
        (2, 2, False),
        (3, 2, False),
        (None, 2, False),
        ("oops", 2, False),
    ],
)
def test_replicas_min(replicas: Any, threshold: int, expect_finding: bool) -> None:
    body = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "x"},
        "spec": {"template": {"spec": {"containers": []}}},
    }
    if replicas is not None:
        body["spec"]["replicas"] = replicas
    findings = list(
        check_replicas_min(_doc(body), _params(severity=Severity.LOW, min=threshold))
    )
    assert bool(findings) is expect_finding


def test_cronjob_pod_template_is_inspected() -> None:
    body = {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {"name": "x"},
        "spec": {
            "schedule": "* * * * *",
            "jobTemplate": {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {"name": "c", "image": "img:latest"}
                            ]
                        }
                    }
                }
            },
        },
    }
    doc = _doc(body)
    assert _ids(check_image_tag_pinned(doc, _params())) == ["image-tag-pinned"]
