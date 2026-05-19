import pytest

from src.models import Spec
from src.promrules import (
    BURN_RATE_PAIRS,
    RECORD_WINDOWS,
    render_alert_rules,
    render_recording_rules,
    render_rules,
)


def _spec(**overrides) -> Spec:
    payload = {
        "service": "checkout-api",
        "labels": {"team": "payments"},
        "slos": [{
            "name": "availability",
            "objective": 99.9,
            "window": "30d",
            "sli": {
                "good_events": 'sum(rate(http_requests_total{code!~"5.."}[{window}]))',
                "total_events": "sum(rate(http_requests_total[{window}]))",
            },
        }],
    }
    payload.update(overrides)
    return Spec.model_validate(payload)


def test_recording_rules_one_per_window():
    group = render_recording_rules(_spec())
    assert group["interval"] == "30s"
    assert len(group["rules"]) == len(RECORD_WINDOWS)

    records = [r["record"] for r in group["rules"]]
    for w in RECORD_WINDOWS:
        assert f"slo:sli_error:ratio_rate{w}" in records


def test_recording_rule_substitutes_window_token():
    group = render_recording_rules(_spec())
    rule_5m = next(r for r in group["rules"] if r["record"].endswith("rate5m"))
    assert "[5m]" in rule_5m["expr"]
    assert "{window}" not in rule_5m["expr"]


def test_recording_rule_carries_identity_labels():
    group = render_recording_rules(_spec())
    labels = group["rules"][0]["labels"]
    assert labels["service"] == "checkout-api"
    assert labels["slo"] == "availability"
    assert labels["team"] == "payments"
    assert labels["objective"] == "99.9"


def test_alert_rules_one_per_burn_rate_pair():
    group = render_alert_rules(_spec())
    assert len(group["rules"]) == len(BURN_RATE_PAIRS)


def test_alert_thresholds_use_burn_times_budget():
    group = render_alert_rules(_spec())
    page_1h = next(
        r for r in group["rules"]
        if r["labels"]["severity"] == "page"
        and r["labels"]["long_window"] == "1h"
    )
    # 14.4 * (1 - 0.999) = 0.0144
    assert "0.0144" in page_1h["expr"]


def test_alert_combines_long_and_short_window():
    group = render_alert_rules(_spec())
    page_1h = next(
        r for r in group["rules"]
        if r["labels"]["severity"] == "page"
        and r["labels"]["long_window"] == "1h"
    )
    expr = page_1h["expr"]
    assert "ratio_rate1h" in expr
    assert "ratio_rate5m" in expr
    assert " and\n" in expr


def test_alert_inherits_user_annotations():
    spec = _spec(slos=[{
        "name": "availability",
        "objective": 99.9,
        "window": "30d",
        "sli": {
            "good_events": "sum(rate(x[{window}]))",
            "total_events": "sum(rate(y[{window}]))",
        },
        "alerting": {
            "page": {
                "annotations": {"runbook_url": "https://example.com/rb"},
            },
        },
    }])
    group = render_alert_rules(spec)
    page = next(r for r in group["rules"] if r["labels"]["severity"] == "page")
    assert page["annotations"]["runbook_url"] == "https://example.com/rb"
    assert "summary" in page["annotations"]


def test_alert_disable_skips_variant():
    spec = _spec(slos=[{
        "name": "availability",
        "objective": 99.9,
        "window": "30d",
        "sli": {
            "good_events": "sum(rate(x[{window}]))",
            "total_events": "sum(rate(y[{window}]))",
        },
        "alerting": {"page": {"enabled": False}},
    }])
    group = render_alert_rules(spec)
    severities = {r["labels"]["severity"] for r in group["rules"]}
    assert severities == {"ticket"}


def test_render_rules_top_level_shape():
    out = render_rules(_spec())
    assert list(out.keys()) == ["groups"]
    assert len(out["groups"]) == 2
    assert out["groups"][0]["name"].startswith("slo-recording-")
    assert out["groups"][1]["name"].startswith("slo-alerts-")


def test_promql_label_braces_pass_through():
    spec = _spec()
    group = render_recording_rules(spec)
    expr = group["rules"][0]["expr"]
    # The user's selector should survive untouched.
    assert '{code!~"5.."}' in expr
