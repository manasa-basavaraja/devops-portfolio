"""
Pydantic models for the SLO spec file.

The spec is intentionally small. One YAML file describes one service and
its SLOs. Everything else - recording rules, alert rules, the dashboard -
is derived from this. If you find yourself wanting to copy fields between
services, that probably belongs in a wrapper / templating layer above this,
not in the model.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Windows used by the multi-window multi-burn-rate alerts (Google SRE workbook).
# Order matters for rendering: short -> long. Anything not in this list is
# rejected by the validator so the generator stays simple.
ALLOWED_WINDOWS = ("5m", "30m", "1h", "2h", "6h", "1d", "3d")

# Compliance windows the user may pick for the SLO objective itself.
ALLOWED_COMPLIANCE_WINDOWS = ("7d", "28d", "30d")

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")


def _check_name(value: str, field: str) -> str:
    if not _NAME_RE.match(value):
        raise ValueError(
            f"{field!r} must match {_NAME_RE.pattern} (got {value!r})"
        )
    return value


class SLI(BaseModel):
    """
    A ratio SLI defined by two PromQL fragments.

    Each fragment must contain the literal token ``{window}`` exactly once.
    The generator substitutes that with each rate window when emitting
    recording rules. Keeping the substitution token explicit (rather than
    parsing PromQL) keeps the model dumb and obvious.
    """

    model_config = ConfigDict(extra="forbid")

    good_events: str = Field(
        ...,
        description="PromQL for good events. Must contain the {window} token.",
    )
    total_events: str = Field(
        ...,
        description="PromQL for total events. Must contain the {window} token.",
    )

    @field_validator("good_events", "total_events")
    @classmethod
    def _has_window_token(cls, value: str) -> str:
        if value.count("{window}") != 1:
            raise ValueError(
                "SLI query must contain the literal token '{window}' exactly once"
            )
        return value


class AlertSpec(BaseModel):
    """One alert variant (page or ticket). All fields are optional."""

    model_config = ConfigDict(extra="forbid")

    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class Alerting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: AlertSpec = Field(default_factory=AlertSpec)
    ticket: AlertSpec = Field(default_factory=AlertSpec)


class SLO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: Optional[str] = None
    objective: float = Field(..., gt=0, lt=100)
    window: str = Field(default="30d")
    sli: SLI
    alerting: Alerting = Field(default_factory=Alerting)
    labels: Dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_format(cls, v: str) -> str:
        return _check_name(v, "slo.name")

    @field_validator("window")
    @classmethod
    def _window_allowed(cls, v: str) -> str:
        if v not in ALLOWED_COMPLIANCE_WINDOWS:
            raise ValueError(
                f"slo.window must be one of {ALLOWED_COMPLIANCE_WINDOWS} (got {v!r})"
            )
        return v

    @property
    def error_budget(self) -> float:
        """Budget as a fraction, e.g. 99.9 -> 0.001."""
        return 1.0 - self.objective / 100.0


class Spec(BaseModel):
    """Top-level SLO spec for a single service."""

    model_config = ConfigDict(extra="forbid")

    service: str
    labels: Dict[str, str] = Field(default_factory=dict)
    slos: List[SLO]

    @field_validator("service")
    @classmethod
    def _service_format(cls, v: str) -> str:
        return _check_name(v, "service")

    @model_validator(mode="after")
    def _unique_slo_names(self) -> "Spec":
        seen: set[str] = set()
        for slo in self.slos:
            if slo.name in seen:
                raise ValueError(f"duplicate slo name: {slo.name!r}")
            seen.add(slo.name)
        if not self.slos:
            raise ValueError("at least one SLO is required")
        return self
