"""Command-line entry point: orchestrate audit → bumps → fork → plan → workflow.

The clone step (fork.clone_and_checkout) is the one piece that needs network.
Run with --offline to skip cloning (useful for tests and dry-runs); in that
mode, fork-and-rebuild entries still produce a plan + workflow but no actual
Dockerfile patching for upstream images.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from chart_supply_refresh.audit.core import AuditReport, Finding, load as load_audit
from chart_supply_refresh.bumps.core import BumpDecision, decide
from chart_supply_refresh.fork.core import apply_bumps, clone_and_checkout
from chart_supply_refresh.plan.core import classify, emit as emit_plan
from chart_supply_refresh.workflow.core import MatrixEntry, render as render_workflow

# Version pin lives here rather than in a workspace-level __init__ because
# the brick layout has no shared parent __init__.py (PEP 420 namespace).
__version__ = "0.1.0"


@click.command()
@click.option("--chart", "chart_path", type=click.Path(exists=True, file_okay=False, path_type=Path),
              required=True, help="Path to input Helm chart directory.")
@click.option("--audit", "audit_path", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              required=True, help="Path to base-audit.json from audit-helm-chart-image-bases.")
@click.option("--target-registry", required=True,
              help="Registry+owner to push rebuilt images to, e.g. 'ghcr.io/repldriven'.")
@click.option("--allow-bumps", type=click.Choice(["safe", "all"]), default="safe",
              help="Bump policy: safe = only current-stable mechanical bumps; all = any stale bump.")
@click.option("--output", "output_dir", type=click.Path(file_okay=False, path_type=Path),
              required=True, help="Output directory for the forked chart bundle. Must not exist.")
@click.option("--cron", default="0 3 * * MON", show_default=True,
              help="Cron schedule for the rebuild workflow.")
@click.option("--clone-cache", type=click.Path(file_okay=False, path_type=Path),
              default=Path("/tmp/chart-supply-refresh-clones"), show_default=True,
              help="Directory to cache upstream clones across runs.")
@click.option("--offline", is_flag=True,
              help="Skip upstream cloning. Local-patched images still processed; fork-and-rebuild "
                   "entries produce plan + workflow only.")
@click.option("--repo-root", type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=Path.cwd(), show_default=True,
              help="Root of the repository containing local Dockerfiles (for `local` signal).")
def main(
    chart_path: Path,
    audit_path: Path,
    target_registry: str,
    allow_bumps: str,
    output_dir: Path,
    cron: str,
    clone_cache: Path,
    offline: bool,
    repo_root: Path,
) -> None:
    """Fork a chart's transitive Dockerfiles onto current bases."""
    if output_dir.exists():
        raise click.UsageError(f"Output directory {output_dir} already exists; pick a fresh path.")

    audit = load_audit(audit_path)
    click.echo(f"Loaded audit ({len(audit.findings)} findings) from {audit_path}")

    output_dir.mkdir(parents=True)
    dockerfiles_dir = output_dir / "dockerfiles"
    dockerfiles_dir.mkdir()
    workflows_dir = output_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)

    # Copy chart verbatim. Values overrides are a future feature; for now the
    # rebuilt-image refs are documented in refresh-plan.json and the user
    # wires them into chart values manually.
    shutil.copytree(chart_path, output_dir / "chart")
    click.echo(f"Copied chart to {output_dir / 'chart'}")

    items: list[tuple[Finding, list[BumpDecision], str]] = []
    matrix: list[MatrixEntry] = []

    for finding in audit.findings:
        decisions = [decide(f, policy=allow_bumps) for f in finding.froms]
        strategy = classify(finding, decisions)

        if strategy in {"fork-and-rebuild", "local-patched"}:
            try:
                _patch_dockerfile(
                    finding=finding,
                    decisions=decisions,
                    dockerfiles_dir=dockerfiles_dir,
                    repo_root=repo_root,
                    clone_cache=clone_cache,
                    offline=offline,
                )
                if strategy == "fork-and-rebuild":
                    matrix.append(MatrixEntry(
                        image=_short_image_name(finding.image),
                        upstream_tag=_upstream_tag(finding.image),
                    ))
            except Exception as exc:
                click.echo(f"  ! {finding.image}: patch failed ({exc}); leaving in plan as stuck",
                           err=True)
                strategy = "stuck-no-source"

        items.append((finding, decisions, strategy))
        click.echo(f"  {strategy:<22} {finding.image}")

    if matrix:
        workflow_yaml = render_workflow(
            matrix=matrix,
            target_registry=target_registry,
            cron=cron,
            tool_version=__version__,
        )
        (workflows_dir / "rebuild.yml").write_text(workflow_yaml)
        click.echo(f"Wrote {workflows_dir / 'rebuild.yml'} ({len(matrix)} matrix entries)")
    else:
        click.echo("No fork-and-rebuild entries; skipping workflow generation.")

    emit_plan(
        audit=audit,
        items=items,
        target_registry=target_registry,
        output_path=output_dir / "refresh-plan.json",
        tool_version=__version__,
    )
    click.echo(f"Wrote {output_dir / 'refresh-plan.json'}")


def _patch_dockerfile(
    *,
    finding: Finding,
    decisions: list[BumpDecision],
    dockerfiles_dir: Path,
    repo_root: Path,
    clone_cache: Path,
    offline: bool,
) -> None:
    """Patch a single image's Dockerfile, writing to dockerfiles_dir/<image>/."""
    short = _short_image_name(finding.image)
    out = dockerfiles_dir / short

    if finding.is_local:
        source = repo_root / finding.dockerfile
        if not source.exists():
            raise FileNotFoundError(f"local Dockerfile {source} not found")
    else:
        if offline:
            # In offline mode, write a stub so the SOURCE.md still lands but
            # no real bumping happens.
            out.mkdir(parents=True, exist_ok=True)
            (out / "Dockerfile.offline").write_text(
                f"# offline mode: would clone {finding.source_repo} @ {finding.tag_checkout}\n"
            )
            return
        clone_cache.mkdir(parents=True, exist_ok=True)
        dest = clone_cache / _safe_dir_name(finding.source_repo or "unknown")
        clone_and_checkout(
            source_repo=finding.source_repo,
            tag=finding.tag_checkout,
            dest=dest,
        )
        source = dest / finding.dockerfile

    apply_bumps(
        source_dockerfile=source,
        output_dir=out,
        finding=finding,
        decisions=decisions,
    )


def _short_image_name(image: str) -> str:
    """`foundationdb/fdb-kubernetes-operator:v2.27.0` -> `fdb-kubernetes-operator`."""
    return image.split("/")[-1].split(":")[0]


def _upstream_tag(image: str) -> str:
    return image.split(":")[-1] if ":" in image else "latest"


def _safe_dir_name(url: str) -> str:
    return url.replace("https://", "").replace("/", "-")


if __name__ == "__main__":
    main()
