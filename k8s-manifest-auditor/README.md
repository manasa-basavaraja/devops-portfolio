# Kubernetes Manifest Auditor

A small, opinionated static analyzer for Kubernetes YAML manifests that
catches the classes of issues that typically slip past `kubectl apply`
and only show up in production: missing resource limits, `:latest`
image tags, privileged containers, unset probes, default-namespace
deployments, missing labels, and so on.

It is designed to be a **shift-left** gate that runs on every PR. The
exit code is wired to fail the build when findings exceed a configured
severity threshold, so it slots cleanly into GitHub Actions, GitLab
CI, Jenkins, or a `pre-commit` hook.

## Why this exists

Most teams I have seen converge on the same loose set of "things we
wish we had caught before the cluster went sideways" rules. Open-source
tools like `kube-linter`, `kubesec`, `polaris`, `conftest` cover a lot
of this ground, but they are heavy and opinionated in ways that do
not always match a given org's standards. This tool is intentionally
~600 lines, dependency-light (only `PyYAML` and `pytest`), and the
rules live in plain Python so any team can fork it, drop in an extra
rule, and ship.

## What it checks

Out of the box, the auditor ships with the following rules. Each rule
has an id, a severity (`low` / `medium` / `high` / `critical`), and a
description. Severities are configurable per-rule in `policy.yaml`,
and individual rules can be disabled.

| Rule id                 | Severity | What it flags                                                                            |
|-------------------------|----------|------------------------------------------------------------------------------------------|
| `image-tag-pinned`      | high     | Container image uses `:latest` or has no tag                                             |
| `image-pull-policy`     | low      | `imagePullPolicy: Always` paired with a non-pinned tag (or unset on a pinned tag)        |
| `resource-requests`     | high     | Container is missing CPU or memory requests                                              |
| `resource-limits`       | high     | Container is missing CPU or memory limits                                                |
| `liveness-probe`        | medium   | Workload pod template has no liveness probe                                              |
| `readiness-probe`       | medium   | Workload pod template has no readiness probe                                             |
| `run-as-non-root`       | high     | Pod / container security context does not set `runAsNonRoot: true`                       |
| `read-only-root-fs`     | medium   | Container does not set `readOnlyRootFilesystem: true`                                    |
| `no-privileged`         | critical | Container has `securityContext.privileged: true`                                         |
| `no-host-network`       | critical | Pod template sets `hostNetwork: true`                                                    |
| `no-host-pid`           | critical | Pod template sets `hostPID: true` or `hostIPC: true`                                     |
| `no-default-namespace`  | medium   | Namespaced resource has no `metadata.namespace` (falls into `default`)                   |
| `required-labels`       | medium   | `metadata.labels` is missing one or more required keys (configurable, default app/owner) |
| `service-account`       | low      | Pod template has no explicit `serviceAccountName`                                        |
| `replicas-min`          | low      | Deployment / StatefulSet has fewer than the configured minimum replicas                  |

The auditor is aware of pod-template-bearing kinds (`Deployment`,
`StatefulSet`, `DaemonSet`, `Job`, `CronJob`, `ReplicaSet`, `Pod`) and
applies container-level rules to the pod template's containers and
init containers.

## Layout

```
k8s-manifest-auditor/
  src/
    loader.py     # recursive YAML loader, multi-doc aware
    findings.py   # Finding / Severity dataclasses
    rules.py      # all rule implementations
    engine.py     # rule runner + policy filtering
    reporter.py   # JSON + Markdown reports
    cli.py        # `python -m src.cli ...` entry point
  tests/
    test_loader.py
    test_rules.py
    test_engine.py
  samples/
    good/         # manifests that pass every rule
    bad/          # manifests that intentionally trip rules
  policy.yaml     # rule on/off + severity overrides + thresholds
  requirements.txt
```

## Quick start

```bash
pip install -r requirements.txt

# Audit the bundled samples (returns non-zero on findings >= high)
python -m src.cli audit samples/ --policy policy.yaml \
    --json reports/audit.json --markdown reports/audit.md

# CI-friendly: only fail on critical
python -m src.cli audit samples/ --fail-level critical

# Run the test suite
pytest tests/
```

The `audit` command exits:

* `0` — no findings at or above `--fail-level` (default `high`)
* `1` — at least one finding at or above `--fail-level`
* `2` — invalid input (bad YAML, missing path, malformed policy)

## Policy file

```yaml
rules:
  image-tag-pinned:
    enabled: true
    severity: high
  required-labels:
    enabled: true
    severity: medium
    params:
      keys: [app.kubernetes.io/name, app.kubernetes.io/version, owner]
  replicas-min:
    enabled: true
    severity: low
    params:
      min: 2

fail_level: high
```

* `enabled: false` skips a rule entirely.
* `severity` overrides the rule's default severity.
* `params` are rule-specific (see `rules.py`).
* `fail_level` is the default exit-code threshold (CLI `--fail-level`
  takes precedence).

## CI integration

A drop-in GitHub Actions workflow is included at
`.github/workflows/audit.yml.example`. Rename it to `audit.yml` and
the auditor will run on every PR that touches `**/*.yaml`.

## Design notes

* **No network, no kubectl.** The tool parses files only. It can run
  in any sandbox, including pre-commit on a developer laptop.
* **Pure-Python rules.** Each rule is a function with a small contract
  (`(doc, params) -> Iterable[Finding]`). Adding a new rule is one
  function plus one entry in `RULES` plus a unit test.
* **Multi-doc aware.** A single file with `---` separators is split
  and each document is audited independently.
* **Path-aware findings.** Every finding records the file, document
  index, kind, name, and a JSON-pointer-ish path
  (`spec.template.spec.containers[0].resources.limits`) so editor
  integrations can jump straight to the offending line.

## License

MIT.
