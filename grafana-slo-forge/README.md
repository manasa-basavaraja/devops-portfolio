# grafana-slo-forge

Turn a single YAML SLO spec into Prometheus recording rules, multi-window
multi-burn-rate alert rules, and a Grafana dashboard. One source of truth,
one command, no copy-pasted Jsonnet or hand-tuned alerts.

## Why

Every team I have worked on ends up with the same problem: the SLO is
written down in a doc somewhere, the recording rules live in a Helm
chart, the alerts live in a different repo, and the dashboard was hand
built six months ago by someone who has since left. They drift. The
burn-rate alerts almost always disagree with the dashboard.

`grafana-slo-forge` collapses all four artifacts into one declarative
spec, in the same shape as the [Google SRE
workbook](https://sre.google/workbook/alerting-on-slos/) recommends:

* one ratio SLI per SLO, defined as two PromQL fragments
* one objective + compliance window
* recording rules at every burn-rate window the alerts need
* page + ticket alerts using the canonical 2 / 5 / 10 / 10 percent
  budget burns over 1h, 6h, 1d, and 3d windows

## Spec

```yaml
service: checkout-api

labels:
  team: payments
  env: prod

slos:
  - name: availability
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
```

The `{window}` token is the one piece of magic. The generator substitutes
it with each rate window when emitting recording rules - that way the
spec stays declarative and you do not have to template PromQL with Jinja.

## Usage

```bash
pip install -r requirements.txt

# Validate
python -m src.cli validate examples/checkout-api.yaml

# Generate Prometheus rules + Grafana dashboard
python -m src.cli generate examples/checkout-api.yaml --out-dir out/
```

That writes:

* `out/checkout-api.rules.yaml` - drop into your Prometheus
  `rule_files:` section, or onto a `kube-prometheus-stack`
  `PrometheusRule` resource.
* `out/checkout-api.dashboard.json` - import via the Grafana UI
  (Dashboards -> Import) or POST to `/api/dashboards/db`.

## What gets generated

For every SLO, the generator emits:

**Recording rules** (one rule group, evaluated every 30s):

| Metric                          | Window |
|---------------------------------|--------|
| `slo:sli_error:ratio_rate5m`    | 5m     |
| `slo:sli_error:ratio_rate30m`   | 30m    |
| `slo:sli_error:ratio_rate1h`    | 1h     |
| `slo:sli_error:ratio_rate2h`    | 2h     |
| `slo:sli_error:ratio_rate6h`    | 6h     |
| `slo:sli_error:ratio_rate1d`    | 1d     |
| `slo:sli_error:ratio_rate3d`    | 3d     |

Each metric carries identity labels (`service`, `slo`, `objective`,
plus everything from the spec's `labels:` block) so an alert from one
SLO never matches recording rules from another.

**Alert rules** (multi-window multi-burn-rate, one rule group):

| Alert       | Severity | Long  | Short | Burn rate | Budget consumed |
|-------------|----------|-------|-------|-----------|-----------------|
| `SLOBurn1h` | page     | 1h    | 5m    | 14.4      | 2%  in 1h       |
| `SLOBurn6h` | page     | 6h    | 30m   | 6         | 5%  in 6h       |
| `SLOBurn1d` | ticket   | 1d    | 2h    | 3         | 10% in 1d       |
| `SLOBurn3d` | ticket   | 3d    | 6h    | 1         | 10% in 3d       |

Both windows must trip together for an alert to fire, which is what
gives this pattern its low false-positive rate.

**Grafana dashboard**: one row per SLO with five panels - objective,
compliance over the compliance window, error budget remaining, burn
rate (1h), and the 5m error ratio.

## Layout

```
grafana-slo-forge/
  src/
    models.py     # Pydantic spec model
    loader.py     # YAML -> Spec
    promrules.py  # Prometheus recording + alert rule generator
    dashboard.py  # Grafana dashboard JSON generator
    cli.py        # `python -m src.cli ...`
  tests/
    test_models.py
    test_loader.py
    test_promrules.py
    test_dashboard.py
  examples/
    checkout-api.yaml
    payments-api.yaml      # two SLOs (availability + latency) on one service
```

## Roadmap

- [ ] `apply` command that pushes the dashboard to a Grafana instance
- [ ] docker-compose stack (Prometheus + Grafana) for local end-to-end
- [ ] GitHub Actions CI

## License

MIT.
