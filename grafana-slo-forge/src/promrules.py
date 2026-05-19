"""
Prometheus rule generation.

Two kinds of artifacts come out of this module:

1. Recording rules. One per (slo, window) pair. The metric is the *error*
   ratio so the alert expressions read straightforwardly as
   ``error_ratio > burn_rate * (1 - objective)``.

2. Multi-window multi-burn-rate alert rules, two severities:

   ====== ============== =============== ===== =================
   page   long window    short window    burn  budget consumed
   ====== ============== =============== ===== =================
   page   1h             5m              14.4  2 percent in 1h
   page   6h             30m             6     5 percent in 6h
   ticket 1d             2h              3     10 percent in 1d
   ticket 3d             6h              1     10 percent in 3d
   ====== ============== =============== ===== =================

   This is the canonical table from the Google SRE workbook chapter on
   alerting on SLOs. Both windows must trip for the alert to fire, which
   is what gives this pattern its low false-positive rate.

The output of :func:`render_rules` is a Python dict that round-trips
cleanly through :func:`yaml.safe_dump` into a Prometheus rule file.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .models import SLO, Spec


# Windows we need recording rules at. Must be a superset of every short and
# long window referenced in BURN_RATE_PAIRS below.
RECORD_WINDOWS: Tuple[str, ...] = ("5m", "30m", "1h", "2h", "6h", "1d", "3d")


# (severity, long_window, short_window, burn_rate). The order is
# significant - alerts are emitted in this order so the higher-burn pair
# fires first when both apply.
BURN_RATE_PAIRS: Tuple[Tuple[str, str, str, float], ...] = (
    ("page", "1h", "5m", 14.4),
    ("page", "6h", "30m", 6.0),
    ("ticket", "1d", "2h", 3.0),
    ("ticket", "3d", "6h", 1.0),
)


def _metric_name(window: str) -> str:
    return f"slo:sli_error:ratio_rate{window}"


def _slo_labels(spec: Spec, slo: SLO) -> Dict[str, str]:
    """
    Identity labels stamped onto recording rules and used as the matcher
    in alert expressions. Service-level labels override slo-level labels
    intentionally - the service identity is the more specific one.
    """
    labels: Dict[str, str] = {}
    labels.update(slo.labels)
    labels.update(spec.labels)
    labels["service"] = spec.service
    labels["slo"] = slo.name
    labels["objective"] = format(slo.objective, "g")
    return labels


def _expand(query: str, window: str) -> str:
    """
    Substitute ``{window}`` in the user's SLI fragment.

    We use ``str.replace`` rather than ``str.format`` because the queries
    contain other ``{...}`` constructs (PromQL label selectors) that must
    pass through untouched.
    """
    return query.replace("{window}", window).strip()


def _recording_rule(spec: Spec, slo: SLO, window: str) -> Dict[str, object]:
    good = _expand(slo.sli.good_events, window)
    total = _expand(slo.sli.total_events, window)
    expr = f"1 - (\n  {good}\n  /\n  {total}\n)"
    return {
        "record": _metric_name(window),
        "expr": expr,
        "labels": _slo_labels(spec, slo),
    }


def _selector(spec: Spec, slo: SLO) -> str:
    """Render an instant-vector selector that matches a single SLO."""
    return (
        '{slo="' + slo.name + '",service="' + spec.service + '"}'
    )


def _alert_expr(spec: Spec, slo: SLO, long_w: str, short_w: str, burn: float) -> str:
    sel = _selector(spec, slo)
    threshold = burn * slo.error_budget
    return (
        f"(\n"
        f"  {_metric_name(long_w)}{sel} > {threshold:g}\n"
        f"  and\n"
        f"  {_metric_name(short_w)}{sel} > {threshold:g}\n"
        f")"
    )


def _alert_rule(
    spec: Spec, slo: SLO, severity: str, long_w: str, short_w: str, burn: float
) -> Dict[str, object]:
    variant = (
        slo.alerting.page if severity == "page" else slo.alerting.ticket
    )
    labels: Dict[str, str] = {}
    labels.update(_slo_labels(spec, slo))
    labels["severity"] = severity
    labels["long_window"] = long_w
    labels["short_window"] = short_w
    labels.update(variant.labels)

    annotations: Dict[str, str] = {
        "summary": (
            f"SLO burn rate ({severity}): {burn:g}x over {long_w}/{short_w} "
            f"for {spec.service}/{slo.name}"
        ),
    }
    annotations.update(variant.annotations)

    name = f"SLOBurn{severity.capitalize()}_{spec.service}_{slo.name}_{long_w}"
    return {
        "alert": name,
        "expr": _alert_expr(spec, slo, long_w, short_w, burn),
        "for": "2m",
        "labels": labels,
        "annotations": annotations,
    }


def render_recording_rules(spec: Spec) -> Dict[str, object]:
    rules: List[Dict[str, object]] = []
    for slo in spec.slos:
        for window in RECORD_WINDOWS:
            rules.append(_recording_rule(spec, slo, window))
    return {
        "name": f"slo-recording-{spec.service}",
        "interval": "30s",
        "rules": rules,
    }


def render_alert_rules(spec: Spec) -> Dict[str, object]:
    rules: List[Dict[str, object]] = []
    for slo in spec.slos:
        for severity, long_w, short_w, burn in BURN_RATE_PAIRS:
            variant = (
                slo.alerting.page if severity == "page" else slo.alerting.ticket
            )
            if not variant.enabled:
                continue
            rules.append(_alert_rule(spec, slo, severity, long_w, short_w, burn))
    return {
        "name": f"slo-alerts-{spec.service}",
        "rules": rules,
    }


def render_rules(spec: Spec) -> Dict[str, object]:
    """Top-level rule file: one recording group, one alert group."""
    return {
        "groups": [
            render_recording_rules(spec),
            render_alert_rules(spec),
        ],
    }
