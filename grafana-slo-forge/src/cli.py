"""
CLI entry point.

    python -m src.cli validate examples/checkout-api.yaml

Subcommands are added as the project grows. For now only ``validate`` is
wired up - it parses the spec file and prints a one-line summary, or
exits non-zero on any validation error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .loader import SpecError, load_spec


@click.group()
@click.version_option(package_name="grafana-slo-forge")
def main() -> None:
    """SLO spec -> Prometheus rules + Grafana dashboards."""


@main.command("validate")
@click.argument("spec_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def validate_cmd(spec_path: Path) -> None:
    """Parse SPEC_PATH and exit non-zero if it is invalid."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    names = ", ".join(slo.name for slo in spec.slos)
    click.echo(f"ok: service={spec.service} slos=[{names}]")


if __name__ == "__main__":
    main()
