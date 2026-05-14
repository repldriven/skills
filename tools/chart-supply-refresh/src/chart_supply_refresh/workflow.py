"""Render the GitHub Actions cron-rebuild workflow.

The trickiest bit is escaping: GH Actions uses `${{ ... }}` expression
syntax which collides with Jinja2. We sidestep the collision by
passing the GH expressions in as plain string variables, so the
template never has to emit literal `${{`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files

from jinja2 import Environment, FileSystemLoader, StrictUndefined

DEFAULT_CRON = "0 3 * * MON"


@dataclass(frozen=True)
class MatrixEntry:
    image: str            # e.g. "fdb-kubernetes-operator"
    upstream_tag: str     # e.g. "v2.27.0"


# GH Actions expressions, kept here so the template never needs ${{
_GHA = {
    "actor": "${{ github.actor }}",
    "token": "${{ secrets.GITHUB_TOKEN }}",
    "matrix_image": "${{ matrix.image }}",
    "matrix_dockerfile": "${{ matrix.dockerfile }}",
    "matrix_upstream_tag": "${{ matrix.upstream-tag }}",
    "date_value": "${{ steps.date.outputs.value }}",
}


def render(
    *,
    matrix: list[MatrixEntry],
    target_registry: str,
    cron: str = DEFAULT_CRON,
    tool_version: str = "0.1.0",
) -> str:
    """Render the rebuild workflow as a YAML string.

    `target_registry` is expected as e.g. "ghcr.io/repldriven";
    `registry_host` is derived as the leading host portion.
    """
    if not matrix:
        raise ValueError("matrix must contain at least one entry")

    registry_host = target_registry.split("/", 1)[0]

    env = Environment(
        loader=FileSystemLoader(str(files("chart_supply_refresh").joinpath("templates"))),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    tmpl = env.get_template("rebuild-workflow.yml.j2")
    return tmpl.render(
        matrix=matrix,
        target_registry=target_registry,
        registry_host=registry_host,
        cron=cron,
        tool_version=tool_version,
        gha=_GHA,
    )
