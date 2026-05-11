from pathlib import Path

import pytest

from src.loader import SpecError, load_spec


GOOD_YAML = """\
service: checkout-api
labels:
  team: payments
slos:
  - name: availability
    objective: 99.9
    window: 30d
    sli:
      good_events: 'sum(rate(http_requests_total{code!~"5.."}[{window}]))'
      total_events: 'sum(rate(http_requests_total[{window}]))'
"""


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "spec.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_valid_spec(tmp_path):
    spec = load_spec(_write(tmp_path, GOOD_YAML))
    assert spec.service == "checkout-api"
    assert spec.labels == {"team": "payments"}


def test_missing_file_raises(tmp_path):
    with pytest.raises(SpecError, match="not found"):
        load_spec(tmp_path / "nope.yaml")


def test_empty_file_raises(tmp_path):
    with pytest.raises(SpecError, match="empty"):
        load_spec(_write(tmp_path, ""))


def test_non_mapping_raises(tmp_path):
    with pytest.raises(SpecError, match="mapping"):
        load_spec(_write(tmp_path, "- 1\n- 2\n"))


def test_invalid_yaml_raises(tmp_path):
    with pytest.raises(SpecError, match="invalid YAML"):
        load_spec(_write(tmp_path, "service: [unclosed\n"))


def test_validation_error_surfaces(tmp_path):
    bad = GOOD_YAML.replace("99.9", "150")
    with pytest.raises(SpecError):
        load_spec(_write(tmp_path, bad))
