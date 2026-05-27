# grafana-slo-forge

Turn a single YAML SLO spec into Prometheus recording rules, multi-window
multi-burn-rate alert rules, and a Grafana dashboard - and push the
dashboard straight into a running Grafana via its HTTP API. One source
of truth, one command, no copy-pasted Jsonnet or hand-tuned alerts.

## Why

Every team I have worked on ends up with the same problem: the SLO is
written down in a doc somewhere, the recording rules live in a Helm
chart, the alerts live in a different repo, and the dashboard was hand
built six months ago by someone who has since left. They drift. The
burn-rate alerts almost always disagree with the dashboard.

There are good open-source SLO tools out there - `sloth`, `pyrra`,
`OpenSLO` - but they each lock you into part of the stack: a Kubernetes
operator, a particular alert format, a specific dashboard generator.
`grafana-slo-forge` is intentionally a single small Python package
(~500 lines of source, four runtime deps) that emits plain Prometheus
YAML and a plain Grafana dashboard JSON. You can drop it into any
Prometheus + Grafana setup, kube-native or not, without committing to a
new operator.

The shape of the spec, and the alert rules that come out of it, follow
the [Google SRE workbook chapter on alerting on
SLOs](https://sre.google/workbook/alerting-on-slos/) - in particular
the multi-window multi-burn-rate pattern, with both windows required
to trip together for low false-positive rates.

## Spec at a glance

```yaml
service: checkout-api

labels:
  team: payments
  env: prod

slos:
  - name: availability
    description: Non-5xx HTTP responses on the public checkout API.
    objective: 99.9
    window: 30d
    sli:
      good_events: |
        sum(rate(http_requests_total{job="checkout-api",code!~"5.."}[{window}]))
      total_events: |
        sum(rate(http_requests_total{job="checkout-api"}[{window}]))
    alerting:
      page:
        annotations:
          runbook_url: https://runbooks.example.com/checkout-availability
      ticket:
        annotations:
          runbook_url: https://runbooks.example.com/checkout-availability
```

The `{window}` token is the only piece of magic. The generator
substitutes it with each rate window when emitting recording rules -
that way the spec stays declarative and you do not have to template
PromQL with Jinja or Jsonnet.

## Install and run

```bash
pip install -r requirements.txt

# 1. Validate the spec
python -m src.cli validate examples/checkout-api.yaml

# 2. Generate Prometheus rules + Grafana dashboard JSON
python -m src.cli generate examples/checkout-api.yaml --out-dir out/

# 3. Push the dashboard straight to a Grafana instance
python -m src.cli apply examples/checkout-api.yaml \
    --grafana-url   http://localhost:3000 \
    --grafana-token "$GRAFANA_TOKEN" \
    --rules-out     out/checkout-api.rules.yaml
```

After step 2 you get:

* `out/checkout-api.rules.yaml` - drop into your Prometheus
  `rule_files:` section, or onto a `kube-prometheus-stack`
  `PrometheusRule` resource.
* `out/checkout-api.dashboard.json` - import via the Grafana UI
  (Dashboards -> Import) or POST to `/api/dashboards/db`.

`apply` does step 3 for the dashboard half, and optionally writes the
rules file too. Use `--dry-run` to print the full POST envelope without
touching Grafana.

## What gets generated

For every SLO in the spec, the generator emits:

**Recording rules** (one rule group per service, evaluated every 30s):

| Metric                          | Window |
|---------------------------------|--------|
| `slo:sli_error:ratio_rate5m`    | 5m     |
| `slo:sli_error:ratio_rate30m`   | 30m    |
| `slo:sli_error:ratio_rate1h`    | 1h     |
| `slo:sli_error:ratio_rate2h`    | 2h     |
| `slo:sli_error:ratio_rate6h`    | 6h     |
| `slo:sli_error:ratio_rate1d`    | 1d     |
| `slo:sli_error:ratio_rate3d`    | 3d     |

Each carries the labels `service`, `slo`, `objective`, plus everything
from the spec's `labels:` block, so an alert from one SLO never matches
a recording rule from another.

**Alert rules** (multi-window multi-burn-rate, one rule group per service):

| Alert                  | Severity | Long  | Short | Burn rate | Budget consumed |
|------------------------|----------|-------|-------|-----------|-----------------|
| `SLOBurnPage_*_1h`     | page     | 1h    | 5m    | 14.4      | 2 percent in 1h |
| `SLOBurnPage_*_6h`     | page     | 6h    | 30m   | 6         | 5 percent in 6h |
| `SLOBurnTicket_*_1d`   | ticket   | 1d    | 2h    | 3         | 10 percent in 1d|
| `SLOBurnTicket_*_3d`   | ticket   | 3d    | 6h    | 1         | 10 percent in 3d|

Both windows must trip together (the alert expression is
`long_window > burn_rate * budget AND short_window > burn_rate * budget`)
which is what gives this pattern its low false-positive rate.

You can disable a severity per-SLO with `alerting: { page: { enabled: false } }`
- handy for latency SLOs where pager noise is rarely justified.

**Grafana dashboard**: one row per SLO with five panels:

1. **Objective** (static stat) - the target percentage.
2. **Compliance** - `100 * (1 - avg_over_time(error_ratio[<window>]))`,
   the actual SLO over the compliance window.
3. **Error budget remaining** - what fraction of the budget has not
   been consumed yet, as a percentage.
4. **Burn rate (1h)** - error ratio divided by error budget. A value of
   1 means burning budget exactly fast enough to exhaust it over the
   compliance window. 14.4 is the page threshold.
5. **Error ratio (5m)** - the raw 5m SLI for visual context.

The dashboard targets schema version 39 (Grafana 10.x); 9.x renders it
fine but prompts a one-time migration on import.

## Local end-to-end with Docker Compose

A self-contained Prometheus + Grafana stack ships in `docker-compose.yml`.
Generated rule files mounted into Prometheus pick up automatically, and
the bundled provisioning gives Grafana a `Prometheus` datasource at the
right UID for the dashboards.

```bash
make generate     # write rules + dashboards into ./out
make up           # start prometheus + grafana
make apply-checkout    # push the checkout-api dashboard to grafana
```

Then open:

* Prometheus: <http://localhost:9090> - check
  `Status -> Rules` to see the generated SLO group.
* Grafana: <http://localhost:3000> (admin / admin).

To make the dashboard show real data, either point Prometheus at a
service that exposes `http_requests_total` (edit
`deploy/prometheus/prometheus.yml`) or change the SLI in your spec to
match metrics you already have.

## Layout

```
grafana-slo-forge/
  src/
    models.py        # Pydantic spec model
    loader.py        # YAML -> Spec
    promrules.py     # Prometheus recording + multi-burn-rate alert generator
    dashboard.py     # Grafana dashboard JSON generator
    grafana.py       # tiny Grafana HTTP client (urllib only)
    cli.py           # `python -m src.cli ...`
  tests/
    test_models.py
    test_loader.py
    test_promrules.py
    test_dashboard.py
    test_grafana.py
  examples/
    checkout-api.yaml
    payments-api.yaml      # two SLOs (availability + latency) on one service
  deploy/
    prometheus/prometheus.yml
    grafana/provisioning/datasources/prometheus.yaml
  docker-compose.yml
  Makefile
  .github/workflows/ci.yml
```

## CI

The shipped GitHub Actions workflow runs the test matrix on Python 3.10
/ 3.11 / 3.12, then validates every spec under `examples/`, generates
the artifacts, runs `promtool check rules` against the generated rule
files, and uploads the output as a build artifact. That last step
catches any case where a generator change emits PromQL that
Prometheus's own parser will not accept - a regression I have hit more
than once when fiddling with the rule expression formatting.

## Design notes

* **Single ratio SLI per SLO.** Distribution-style SLIs (latency
  histograms) are expressed as a ratio against a histogram bucket -
  see `examples/payments-api.yaml`. Splitting the model into "ratio"
  vs "latency" SLIs added complexity without paying for itself.
* **`{window}` substitution, not Jinja.** The user's PromQL has braces
  in label selectors. Parsing PromQL would be too much work; using a
  literal token avoids both Jinja-as-a-build-step and accidental
  `format()` collisions with `{}` in selectors.
* **Identity labels stamped at generation time.** Every recording rule
  and every alert carries `service` and `slo` labels. Alert expressions
  use them as selectors so cross-SLO label collisions are impossible
  even when two SLOs share the same SLI shape.
* **Standard library HTTP client.** The Grafana side only needs two
  endpoints. `urllib.request` is enough, the package keeps a small
  dependency surface, and the opener is parameterised so tests use a
  fake without monkeypatching urllib.

## Roadmap

- [ ] Distribution / "latency target" SLI as a first-class spec type
      (sugar over the histogram-bucket pattern in the example)
- [ ] Optional Alertmanager route YAML output
- [ ] PrometheusRule (kube-prometheus-stack) CRD output

## License

MIT.
