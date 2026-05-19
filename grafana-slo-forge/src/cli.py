"""
CLI entry point.

    python -m src.cli validate examples/checkout-api.yaml
    python -m src.cli generate examples/checkout-api.yaml --out-dir out/

The ``generate`` command writes two files into the output directory:

    <service>.rules.yaml   Prometheus recording + alert rules
    <service>.dashboard.json   Grafana dashboard model
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from .dashboard import render_dashboard
from .loader import SpecError, load_spec
from .promrules import render_rules


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


@main.command("generate")
@click.argument("spec_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out-dir", "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("out"),
    show_default=True,
    help="Directory to write generated artifacts into.",
)
def generate_cmd(spec_path: Path, out_dir: Path) -> None:
    """Generate Prometheus rules and a Grafana dashboard from SPEC_PATH."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    out_dir.mkdir(parents=True, exist_ok=True)

    rules_path = out_dir / f"{spec.service}.rules.yaml"
    dash_path = out_dir / f"{spec.service}.dashboard.json"

    rules_path.write_text(
        yaml.safe_dump(render_rules(spec), sort_keys=False),
        encoding="utf-8",
    )
    dash_path.write_text(
        json.dumps(render_dashboard(spec), indent=2),
        encoding="utf-8",
    )

    click.echo(f"wrote {rules_path}")
    click.echo(f"wrote {dash_path}")


if __name__ == "__main__":
    main()
