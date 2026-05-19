import json

import pytest

from src.dashboard import render_dashboard
from src.models import Spec


def _spec(num_slos: int = 1) -> Spec:
    slos = []
    for i in range(num_slos):
        slos.append({
            "name": f"slo-{i}",
            "objective": 99.9,
            "window": "30d",
            "sli": {
                "good_events": "sum(rate(good[{window}]))",
                "total_events": "sum(rate(total[{window}]))",
            },
        })
    return Spec.model_validate({
        "service": "checkout-api",
        "labels": {"team": "payments"},
        "slos": slos,
    })


def test_dashboard_top_level_keys():
    dash = render_dashboard(_spec())
    assert dash["title"] == "SLO - checkout-api"
    assert dash["uid"] == "slo-checkout-api"
    assert dash["schemaVersion"] >= 36
    assert dash["panels"]


def test_dashboard_is_json_serialisable():
    dash = render_dashboard(_spec())
    blob = json.dumps(dash)
    # Round-trip preserves shape.
    again = json.loads(blob)
    assert again["uid"] == dash["uid"]


def test_one_row_plus_five_panels_per_slo():
    dash = render_dashboard(_spec(num_slos=2))
    rows = [p for p in dash["panels"] if p["type"] == "row"]
    non_rows = [p for p in dash["panels"] if p["type"] != "row"]
    assert len(rows) == 2
    assert len(non_rows) == 10


def test_panel_ids_are_unique():
    dash = render_dashboard(_spec(num_slos=3))
    ids = [p["id"] for p in dash["panels"]]
    assert len(ids) == len(set(ids))


def test_grid_widths_sum_to_24_per_row():
    dash = render_dashboard(_spec())
    non_row = [p for p in dash["panels"] if p["type"] != "row"]
    assert sum(p["gridPos"]["w"] for p in non_row) == 24


def test_targets_reference_recording_metrics():
    dash = render_dashboard(_spec())
    exprs = [
        t["expr"]
        for p in dash["panels"]
        if p["type"] != "row"
        for t in p["targets"]
    ]
    assert any("slo:sli_error:ratio_rate5m" in e for e in exprs)
    assert any("slo:sli_error:ratio_rate1h" in e for e in exprs)


def test_selector_is_scoped_to_service_and_slo():
    dash = render_dashboard(_spec())
    exprs = [
        t["expr"]
        for p in dash["panels"]
        if p["type"] != "row"
        for t in p["targets"]
    ]
    assert any('slo="slo-0"' in e and 'service="checkout-api"' in e for e in exprs)


def test_dashboard_tags_include_service_and_labels():
    dash = render_dashboard(_spec())
    assert "slo" in dash["tags"]
    assert "checkout-api" in dash["tags"]
    assert "team:payments" in dash["tags"]
