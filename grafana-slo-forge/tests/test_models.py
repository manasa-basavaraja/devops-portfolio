import pytest
from pydantic import ValidationError

from src.models import SLI, SLO, Alerting, Spec


def _good_sli() -> dict:
    return {
        "good_events": 'sum(rate(http_requests_total{code!~"5.."}[{window}]))',
        "total_events": "sum(rate(http_requests_total[{window}]))",
    }


def _good_slo(**overrides) -> dict:
    base = {
        "name": "availability",
        "objective": 99.9,
        "window": "30d",
        "sli": _good_sli(),
    }
    base.update(overrides)
    return base


def test_minimal_spec_round_trips():
    spec = Spec.model_validate({
        "service": "checkout-api",
        "slos": [_good_slo()],
    })
    assert spec.service == "checkout-api"
    assert len(spec.slos) == 1
    assert spec.slos[0].error_budget == pytest.approx(0.001)


def test_objective_must_be_in_range():
    with pytest.raises(ValidationError):
        Spec.model_validate({
            "service": "x",
            "slos": [_good_slo(objective=100)],
        })
    with pytest.raises(ValidationError):
        Spec.model_validate({
            "service": "x",
            "slos": [_good_slo(objective=0)],
        })


def test_window_must_be_allowed():
    with pytest.raises(ValidationError):
        Spec.model_validate({
            "service": "x",
            "slos": [_good_slo(window="14d")],
        })


def test_sli_requires_window_token():
    bad = _good_sli()
    bad["good_events"] = "sum(rate(http_requests_total[5m]))"
    with pytest.raises(ValidationError):
        SLI.model_validate(bad)


def test_sli_rejects_double_window_token():
    bad = _good_sli()
    bad["good_events"] = "sum(rate(http_requests_total[{window}]))/{window}"
    with pytest.raises(ValidationError):
        SLI.model_validate(bad)


def test_service_name_format_enforced():
    with pytest.raises(ValidationError):
        Spec.model_validate({
            "service": "Has Spaces",
            "slos": [_good_slo()],
        })


def test_duplicate_slo_names_rejected():
    with pytest.raises(ValidationError):
        Spec.model_validate({
            "service": "x",
            "slos": [_good_slo(), _good_slo()],
        })


def test_at_least_one_slo_required():
    with pytest.raises(ValidationError):
        Spec.model_validate({"service": "x", "slos": []})


def test_extra_fields_are_rejected():
    payload = {
        "service": "x",
        "slos": [_good_slo()],
        "made_up": True,
    }
    with pytest.raises(ValidationError):
        Spec.model_validate(payload)


def test_alerting_defaults_are_empty_but_present():
    spec = Spec.model_validate({
        "service": "x",
        "slos": [_good_slo()],
    })
    assert isinstance(spec.slos[0].alerting, Alerting)
    assert spec.slos[0].alerting.page.enabled is True
    assert spec.slos[0].alerting.page.labels == {}


def test_slo_inherits_no_labels_by_default():
    slo = SLO.model_validate(_good_slo(labels={"tier": "1"}))
    assert slo.labels == {"tier": "1"}
