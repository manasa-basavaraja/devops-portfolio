# grafana-slo-forge

Turn a single YAML SLO spec into Prometheus recording rules, multi-window
multi-burn-rate alert rules, and a Grafana dashboard. One source of truth,
one command, no copy-pasted Jsonnet or hand-tuned alerts.

> **Status:** early draft. The spec model and validator are in place.
> Generators and the Grafana API client land in the next iterations.

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
* page + ticket alerts using the canonical 2%/5%/10%/10% budget burns

## Spec at a glance

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
spec stays declarative and you do not template PromQL with Jinja.

## Usage (so far)

```bash
pip install -r requirements.txt
python -m src.cli validate examples/checkout-api.yaml
```

Output:

```
ok: service=checkout-api slos=[availability]
```

## Layout

```
grafana-slo-forge/
  src/
    models.py     # Pydantic spec model
    loader.py     # YAML -> Spec
    cli.py        # `python -m src.cli ...`
  tests/
    test_models.py
    test_loader.py
  examples/
    checkout-api.yaml
```

## Roadmap

- [ ] Prometheus recording + multi-burn-rate alert rule generator
- [ ] Grafana dashboard JSON generator
- [ ] `apply` command that pushes the dashboard to a Grafana instance
- [ ] docker-compose stack (Prometheus + Grafana) for local end-to-end
- [ ] GitHub Actions CI

## License

MIT.
