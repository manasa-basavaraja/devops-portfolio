"""
Grafana dashboard generation.

Each SLO becomes a row of panels:

  * objective stat (the target, static)
  * compliance stat (1 - average error ratio over the compliance window)
  * error budget remaining gauge (% of budget left)
  * burn rate timeseries (1h window, in units of "x of budget per hour")
  * SLI error ratio timeseries (5m window)

The output is a Grafana dashboard model dict, ready to ``json.dump`` into
a file or to POST to ``/api/dashboards/db`` after wrapping in
``{"dashboard": ..., "overwrite": true}``.

Schema version 39 corresponds to Grafana 10.x. The dashboard renders
fine in 9.x as well; older versions get a one-time migration prompt.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .models import SLO, Spec


SCHEMA_VERSION = 39
DEFAULT_DATASOURCE = "${DS_PROMETHEUS}"

# Each row is one SLO, this many grid units tall.
ROW_HEIGHT = 8

# Panels in a row, left-to-right. Total width = 24 grid units.
_PANEL_WIDTHS: Tuple[int, ...] = (4, 4, 4, 6, 6)


def _selector(spec: Spec, slo: SLO) -> str:
    return '{slo="' + slo.name + '",service="' + spec.service + '"}'


def _datasource() -> Dict[str, str]:
    return {"type": "prometheus", "uid": DEFAULT_DATASOURCE}


def _stat_panel(
    panel_id: int, title: str, expr: str, x: int, y: int, w: int,
    *, unit: str = "percent", decimals: int = 3,
    thresholds: List[Dict[str, object]] | None = None,
) -> Dict[str, object]:
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "datasource": _datasource(),
        "gridPos": {"h": ROW_HEIGHT, "w": w, "x": x, "y": y},
        "targets": [{
            "refId": "A",
            "expr": expr,
            "datasource": _datasource(),
        }],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": decimals,
                "thresholds": {
                    "mode": "absolute",
                    "steps": thresholds or [
                        {"color": "red", "value": None},
                        {"color": "yellow", "value": 99.0},
                        {"color": "green", "value": 99.5},
                    ],
                },
            },
            "overrides": [],
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto",
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "center",
        },
    }


def _timeseries_panel(
    panel_id: int, title: str, expr: str, legend: str,
    x: int, y: int, w: int,
    *, unit: str = "short",
) -> Dict[str, object]:
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "datasource": _datasource(),
        "gridPos": {"h": ROW_HEIGHT, "w": w, "x": x, "y": y},
        "targets": [{
            "refId": "A",
            "expr": expr,
            "legendFormat": legend,
            "datasource": _datasource(),
        }],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "smooth",
                    "fillOpacity": 10,
                    "lineWidth": 1,
                },
            },
            "overrides": [],
        },
        "options": {
            "tooltip": {"mode": "multi", "sort": "desc"},
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
        },
    }


def _row_panel(panel_id: int, title: str, y: int) -> Dict[str, object]:
    return {
        "id": panel_id,
        "type": "row",
        "title": title,
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
        "panels": [],
    }


def _panels_for_slo(
    spec: Spec, slo: SLO, *, panel_id_start: int, y: int,
) -> Tuple[List[Dict[str, object]], int]:
    """
    Build the panels for one SLO, starting at ``panel_id_start`` and at
    grid row ``y``. Returns (panels, next_y).
    """
    sel = _selector(spec, slo)
    pid = panel_id_start
    panels: List[Dict[str, object]] = []

    panels.append(_row_panel(pid, f"{slo.name} - {slo.description or ''}".rstrip(" -"), y))
    pid += 1
    y += 1

    objective_thresholds = [
        {"color": "blue", "value": None},
    ]
    panels.append(_stat_panel(
        pid, "Objective",
        expr=format(slo.objective, "g"),
        x=0, y=y, w=_PANEL_WIDTHS[0],
        unit="percent", decimals=3,
        thresholds=objective_thresholds,
    ))
    pid += 1

    compliance_expr = (
        f"100 * (1 - avg_over_time(slo:sli_error:ratio_rate5m{sel}[{slo.window}]))"
    )
    panels.append(_stat_panel(
        pid, f"Compliance ({slo.window})",
        expr=compliance_expr,
        x=_PANEL_WIDTHS[0], y=y, w=_PANEL_WIDTHS[1],
        unit="percent", decimals=3,
    ))
    pid += 1

    budget_expr = (
        f"100 * (1 - "
        f"avg_over_time(slo:sli_error:ratio_rate5m{sel}[{slo.window}]) "
        f"/ {slo.error_budget:g})"
    )
    panels.append(_stat_panel(
        pid, f"Error budget remaining ({slo.window})",
        expr=budget_expr,
        x=_PANEL_WIDTHS[0] + _PANEL_WIDTHS[1], y=y,
        w=_PANEL_WIDTHS[2],
        unit="percent", decimals=2,
        thresholds=[
            {"color": "red", "value": None},
            {"color": "yellow", "value": 25},
            {"color": "green", "value": 50},
        ],
    ))
    pid += 1

    burn_expr = f"slo:sli_error:ratio_rate1h{sel} / {slo.error_budget:g}"
    x4 = _PANEL_WIDTHS[0] + _PANEL_WIDTHS[1] + _PANEL_WIDTHS[2]
    panels.append(_timeseries_panel(
        pid, "Burn rate (1h)",
        expr=burn_expr,
        legend="burn rate",
        x=x4, y=y, w=_PANEL_WIDTHS[3],
        unit="short",
    ))
    pid += 1

    sli_expr = f"slo:sli_error:ratio_rate5m{sel}"
    x5 = x4 + _PANEL_WIDTHS[3]
    panels.append(_timeseries_panel(
        pid, "Error ratio (5m)",
        expr=sli_expr,
        legend="error ratio",
        x=x5, y=y, w=_PANEL_WIDTHS[4],
        unit="percentunit",
    ))
    pid += 1

    return panels, y + ROW_HEIGHT


def render_dashboard(spec: Spec) -> Dict[str, object]:
    panels: List[Dict[str, object]] = []
    next_id = 1
    next_y = 0
    for slo in spec.slos:
        slo_panels, next_y = _panels_for_slo(
            spec, slo, panel_id_start=next_id, y=next_y,
        )
        panels.extend(slo_panels)
        next_id += len(slo_panels)

    tags = ["slo", spec.service]
    tags.extend(f"{k}:{v}" for k, v in sorted(spec.labels.items()))

    return {
        "title": f"SLO - {spec.service}",
        "uid": f"slo-{spec.service}",
        "tags": tags,
        "schemaVersion": SCHEMA_VERSION,
        "version": 1,
        "editable": True,
        "graphTooltip": 1,
        "time": {"from": "now-30d", "to": "now"},
        "timezone": "",
        "refresh": "1m",
        "panels": panels,
        "templating": {"list": []},
        "annotations": {"list": []},
    }
