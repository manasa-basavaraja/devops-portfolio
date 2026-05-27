"""
CLI entry point.

    python -m src.cli validate examples/checkout-api.yaml
    python -m src.cli generate examples/checkout-api.yaml --out-dir out/
    python -m src.cli apply    examples/checkout-api.yaml \
        --grafana-url http://localhost:3000 \
        --grafana-token $GRAFANA_TOKEN

``generate`` writes two files into the output directory:

    <service>.rules.yaml       Prometheus recording + alert rules
    <service>.dashboard.json   Grafana dashboard model

``apply`` does what ``generate`` does for the dashboard half, then POSTs
it to the configured Grafana instance. Recording rules are still written
to disk - they belong in your Prometheus deployment, not in Grafana.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
import yaml

from .dashboard import render_dashboard
from .grafana import Grafana, GrafanaError
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


@main.command("apply")
@click.argument("spec_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--grafana-url", "grafana_url",
    default=lambda: os.environ.get("GRAFANA_URL", ""),
    help="Grafana base URL, e.g. http://localhost:3000. Falls back to $GRAFANA_URL.",
)
@click.option(
    "--grafana-token", "grafana_token",
    default=lambda: os.environ.get("GRAFANA_TOKEN", ""),
    help="Grafana API token. Falls back to $GRAFANA_TOKEN. Optional for unauthenticated OSS.",
)
@click.option(
    "--folder-uid", "folder_uid", default=None,
    help="Optional Grafana folder UID to upsert the dashboard into.",
)
@click.option(
    "--rules-out", "rules_out",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to write the Prometheus rule file. Skipped if not provided.",
)
@click.option(
    "--dry-run", "dry_run", is_flag=True,
    help="Print the dashboard envelope and exit. No HTTP call is made.",
)
def apply_cmd(
    spec_path: Path,
    grafana_url: str,
    grafana_token: str,
    folder_uid: str | None,
    rules_out: Path | None,
    dry_run: bool,
) -> None:
    """Push the dashboard from SPEC_PATH to a Grafana instance."""
    try:
        spec = load_spec(spec_path)
    except SpecError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    dashboard = render_dashboard(spec)

    if rules_out is not None:
        rules_out.parent.mkdir(parents=True, exist_ok=True)
        rules_out.write_text(
            yaml.safe_dump(render_rules(spec), sort_keys=False),
            encoding="utf-8",
        )
        click.echo(f"wrote {rules_out}")

    if dry_run:
        click.echo(json.dumps({"dashboard": dashboard, "overwrite": True}, indent=2))
        return

    if not grafana_url:
        click.echo(
            "error: --grafana-url (or $GRAFANA_URL) is required unless --dry-run",
            err=True,
        )
        sys.exit(2)

    client = Grafana(url=grafana_url, token=grafana_token or None, folder_uid=folder_uid)
    try:
        health = client.health()
        if health.get("database") not in (None, "ok"):
            click.echo(f"warning: grafana health: {health}", err=True)
        result = client.upsert_dashboard(dashboard)
    except GrafanaError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    click.echo(
        f"applied dashboard uid={result.get('uid', '?')} "
        f"version={result.get('version', '?')} "
        f"url={grafana_url.rstrip('/')}{result.get('url', '')}"
    )


if __name__ == "__main__":
    main()
