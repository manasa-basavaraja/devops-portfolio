"""All built-in audit rules.

Each rule is a callable with the signature::

    def check(doc: ParsedDoc, params: dict) -> Iterable[Finding]

and is registered in :data:`RULES` together with a default severity.
The engine handles enabling/disabling, severity overrides, and merging
rule-specific params from ``policy.yaml``.

Rules never raise on missing keys — Kubernetes manifests are deeply
nested and partial, and a noisy ``KeyError`` would defeat the purpose
of a static analyzer. Instead, helpers like :func:`_get` return
sensible defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .findings import Finding, Severity
from .loader import ParsedDoc


RuleFn = Callable[[ParsedDoc, Dict[str, Any]], Iterable[Finding]]


@dataclass(frozen=True)
class RuleSpec:
    """Static description of a built-in rule."""

    id: str
    default_severity: Severity
    description: str
    fn: RuleFn


_WORKLOAD_KINDS = {
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "ReplicaSet",
    "Job",
    "CronJob",
    "Pod",
}

_NAMESPACED_KINDS = _WORKLOAD_KINDS | {
    "Service",
    "Ingress",
    "ConfigMap",
    "Secret",
    "ServiceAccount",
    "Role",
    "RoleBinding",
    "PersistentVolumeClaim",
    "HorizontalPodAutoscaler",
    "NetworkPolicy",
    "PodDisruptionBudget",
}


def _get(obj: Any, *keys: str, default: Any = None) -> Any:
    """Safely walk a nested dict, returning ``default`` on any miss."""

    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _pod_template(doc: ParsedDoc) -> Tuple[Optional[Dict[str, Any]], str]:
    """Return ``(podSpec, jsonPathToPodSpec)`` for any workload kind.

    Pods carry their spec at ``spec``, while higher-level controllers
    nest it under ``spec.template.spec`` (CronJob nests one level
    deeper). Returns ``(None, "")`` for kinds that have no pod
    template.
    """

    kind = doc.kind
    if kind == "Pod":
        return doc.body.get("spec"), "spec"
    if kind == "CronJob":
        return (
            _get(doc.body, "spec", "jobTemplate", "spec", "template", "spec"),
            "spec.jobTemplate.spec.template.spec",
        )
    if kind in _WORKLOAD_KINDS:
        return (
            _get(doc.body, "spec", "template", "spec"),
            "spec.template.spec",
        )
    return None, ""


def _all_containers(pod_spec: Dict[str, Any], base_path: str) -> Iterable[Tuple[Dict[str, Any], str]]:
    """Yield ``(container, jsonPath)`` for every container + initContainer."""

    for key in ("containers", "initContainers"):
        for idx, c in enumerate(pod_spec.get(key) or []):
            if isinstance(c, dict):
                yield c, f"{base_path}.{key}[{idx}]"


def _mk(rule_id: str, severity: Severity, message: str, doc: ParsedDoc, path: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=message,
        file=doc.file,
        doc_index=doc.doc_index,
        kind=doc.kind,
        name=doc.name,
        namespace=doc.namespace,
        path=path,
    )


def _image_tag(image: str) -> Optional[str]:
    """Return the tag/digest portion of an image ref, or None if missing."""

    if not image:
        return None
    if "@" in image:
        return image.split("@", 1)[1]
    last = image.rsplit("/", 1)[-1]
    if ":" in last:
        return last.rsplit(":", 1)[1]
    return None


def check_image_tag_pinned(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    for c, path in _all_containers(pod_spec, base):
        image = c.get("image", "")
        tag = _image_tag(image)
        if tag is None:
            yield _mk(
                "image-tag-pinned",
                severity,
                f"container {c.get('name', '?')!r} image {image!r} has no tag",
                doc,
                f"{path}.image",
            )
        elif tag == "latest":
            yield _mk(
                "image-tag-pinned",
                severity,
                f"container {c.get('name', '?')!r} uses :latest tag",
                doc,
                f"{path}.image",
            )


def check_image_pull_policy(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    for c, path in _all_containers(pod_spec, base):
        image = c.get("image", "")
        tag = _image_tag(image)
        policy = c.get("imagePullPolicy")
        pinned = tag is not None and tag != "latest"
        if policy == "Always" and pinned:
            yield _mk(
                "image-pull-policy",
                severity,
                f"container {c.get('name', '?')!r} pins {image!r} but uses imagePullPolicy=Always",
                doc,
                f"{path}.imagePullPolicy",
            )
        if policy is None and not pinned:
            yield _mk(
                "image-pull-policy",
                severity,
                f"container {c.get('name', '?')!r} has unpinned image and no explicit imagePullPolicy",
                doc,
                f"{path}.imagePullPolicy",
            )


def _check_resources(doc: ParsedDoc, params: Dict[str, Any], kind: str, rule_id: str) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    for c, path in _all_containers(pod_spec, base):
        block = _get(c, "resources", kind, default={})
        missing = [k for k in ("cpu", "memory") if k not in (block or {})]
        if missing:
            yield _mk(
                rule_id,
                severity,
                (
                    f"container {c.get('name', '?')!r} is missing "
                    f"{kind} for: {', '.join(missing)}"
                ),
                doc,
                f"{path}.resources.{kind}",
            )


def check_resource_requests(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    return _check_resources(doc, params, "requests", "resource-requests")


def check_resource_limits(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    return _check_resources(doc, params, "limits", "resource-limits")


def _check_probe(doc: ParsedDoc, params: Dict[str, Any], probe_key: str, rule_id: str) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    for c, path in _all_containers(pod_spec, base):
        if probe_key not in (c or {}):
            yield _mk(
                rule_id,
                severity,
                f"container {c.get('name', '?')!r} has no {probe_key}",
                doc,
                f"{path}.{probe_key}",
            )


def check_liveness_probe(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    return _check_probe(doc, params, "livenessProbe", "liveness-probe")


def check_readiness_probe(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    return _check_probe(doc, params, "readinessProbe", "readiness-probe")


def check_run_as_non_root(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    pod_sc = pod_spec.get("securityContext") or {}
    pod_setting = pod_sc.get("runAsNonRoot")
    for c, path in _all_containers(pod_spec, base):
        c_sc = c.get("securityContext") or {}
        c_setting = c_sc.get("runAsNonRoot")
        effective = c_setting if c_setting is not None else pod_setting
        if effective is not True:
            yield _mk(
                "run-as-non-root",
                severity,
                f"container {c.get('name', '?')!r} does not set runAsNonRoot=true",
                doc,
                f"{path}.securityContext.runAsNonRoot",
            )


def check_read_only_root_fs(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    for c, path in _all_containers(pod_spec, base):
        c_sc = c.get("securityContext") or {}
        if c_sc.get("readOnlyRootFilesystem") is not True:
            yield _mk(
                "read-only-root-fs",
                severity,
                f"container {c.get('name', '?')!r} does not set readOnlyRootFilesystem=true",
                doc,
                f"{path}.securityContext.readOnlyRootFilesystem",
            )


def check_no_privileged(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    for c, path in _all_containers(pod_spec, base):
        c_sc = c.get("securityContext") or {}
        if c_sc.get("privileged") is True:
            yield _mk(
                "no-privileged",
                severity,
                f"container {c.get('name', '?')!r} runs as privileged",
                doc,
                f"{path}.securityContext.privileged",
            )


def check_no_host_network(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    if pod_spec.get("hostNetwork") is True:
        yield _mk(
            "no-host-network",
            severity,
            "pod template enables hostNetwork",
            doc,
            f"{base}.hostNetwork",
        )


def check_no_host_pid(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    if pod_spec.get("hostPID") is True:
        yield _mk(
            "no-host-pid",
            severity,
            "pod template enables hostPID",
            doc,
            f"{base}.hostPID",
        )
    if pod_spec.get("hostIPC") is True:
        yield _mk(
            "no-host-pid",
            severity,
            "pod template enables hostIPC",
            doc,
            f"{base}.hostIPC",
        )


def check_no_default_namespace(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    if doc.kind not in _NAMESPACED_KINDS:
        return
    ns = doc.namespace
    if ns is None or ns == "default":
        yield _mk(
            "no-default-namespace",
            severity,
            f"{doc.kind} {doc.name!r} has no explicit namespace (falls into 'default')",
            doc,
            "metadata.namespace",
        )


def check_required_labels(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    keys: List[str] = list(params.get("keys") or [])
    if not keys:
        return
    labels = _get(doc.body, "metadata", "labels", default={}) or {}
    missing = [k for k in keys if k not in labels]
    if missing:
        yield _mk(
            "required-labels",
            severity,
            f"missing required labels: {', '.join(missing)}",
            doc,
            "metadata.labels",
        )


def check_service_account(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    pod_spec, base = _pod_template(doc)
    if pod_spec is None:
        return
    sa = pod_spec.get("serviceAccountName")
    if not sa or sa == "default":
        yield _mk(
            "service-account",
            severity,
            "pod template has no explicit serviceAccountName",
            doc,
            f"{base}.serviceAccountName",
        )


def check_replicas_min(doc: ParsedDoc, params: Dict[str, Any]) -> Iterable[Finding]:
    severity = params["_severity"]
    if doc.kind not in {"Deployment", "StatefulSet", "ReplicaSet"}:
        return
    threshold = int(params.get("min", 2))
    replicas = _get(doc.body, "spec", "replicas")
    if replicas is None:
        return
    try:
        n = int(replicas)
    except (TypeError, ValueError):
        return
    if n < threshold:
        yield _mk(
            "replicas-min",
            severity,
            f"{doc.kind} has replicas={n} (< {threshold})",
            doc,
            "spec.replicas",
        )


RULES: List[RuleSpec] = [
    RuleSpec("image-tag-pinned", Severity.HIGH, "container image must be pinned (no :latest, no missing tag)", check_image_tag_pinned),
    RuleSpec("image-pull-policy", Severity.LOW, "imagePullPolicy must match image pinning", check_image_pull_policy),
    RuleSpec("resource-requests", Severity.HIGH, "container must declare CPU and memory requests", check_resource_requests),
    RuleSpec("resource-limits", Severity.HIGH, "container must declare CPU and memory limits", check_resource_limits),
    RuleSpec("liveness-probe", Severity.MEDIUM, "container must define a liveness probe", check_liveness_probe),
    RuleSpec("readiness-probe", Severity.MEDIUM, "container must define a readiness probe", check_readiness_probe),
    RuleSpec("run-as-non-root", Severity.HIGH, "container or pod must set runAsNonRoot=true", check_run_as_non_root),
    RuleSpec("read-only-root-fs", Severity.MEDIUM, "container must set readOnlyRootFilesystem=true", check_read_only_root_fs),
    RuleSpec("no-privileged", Severity.CRITICAL, "container must not run as privileged", check_no_privileged),
    RuleSpec("no-host-network", Severity.CRITICAL, "pod template must not set hostNetwork=true", check_no_host_network),
    RuleSpec("no-host-pid", Severity.CRITICAL, "pod template must not set hostPID/hostIPC=true", check_no_host_pid),
    RuleSpec("no-default-namespace", Severity.MEDIUM, "namespaced resource must declare an explicit namespace", check_no_default_namespace),
    RuleSpec("required-labels", Severity.MEDIUM, "metadata.labels must include the configured keys", check_required_labels),
    RuleSpec("service-account", Severity.LOW, "pod template must declare an explicit serviceAccountName", check_service_account),
    RuleSpec("replicas-min", Severity.LOW, "Deployment/StatefulSet must meet a minimum replica count", check_replicas_min),
]


RULES_BY_ID: Dict[str, RuleSpec] = {r.id: r for r in RULES}
