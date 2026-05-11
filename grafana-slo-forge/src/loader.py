"""YAML loader for SLO spec files."""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml
from pydantic import ValidationError

from .models import Spec


class SpecError(Exception):
    """Raised on any spec parse / validation failure. Wraps the cause."""


def load_spec(path: Union[str, Path]) -> Spec:
    p = Path(path)
    if not p.is_file():
        raise SpecError(f"spec file not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SpecError(f"invalid YAML in {p}: {exc}") from exc

    if raw is None:
        raise SpecError(f"spec file is empty: {p}")
    if not isinstance(raw, dict):
        raise SpecError(f"spec file must be a YAML mapping, got {type(raw).__name__}")

    try:
        return Spec.model_validate(raw)
    except ValidationError as exc:
        # Re-raise as SpecError so the CLI has one exception type to catch,
        # but keep the original Pydantic message for the human reading the
        # output - it points at the offending field path.
        raise SpecError(str(exc)) from exc
