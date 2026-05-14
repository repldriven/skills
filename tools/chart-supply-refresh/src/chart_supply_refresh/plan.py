"""Aggregate per-image work into the refresh-plan.json manifest.

One entry per audit finding. Strategy is one of:
- "fork-and-rebuild"  — Dockerfile was patched; image will be rebuilt by the workflow.
- "local-patched"     — Dockerfile in this repo was patched; rebuild via existing CI.
- "no-bumps-needed"   — All FROMs current or rolling-stable; nothing to do.
- "stuck-no-source"   — Source repo unknown / auth-gated / Dockerfile ambiguous.
- "stuck-build-system" — Image built via Nix/ko/Bazel/Jib; out of scope for FROM-bump.
- "skipped-unsafe"    — FROMs are stale but no safe-mechanical mapping available.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from chart_supply_refresh.audit import AuditReport, Finding, SENTINEL_DOCKERFILES
from chart_supply_refresh.bumps import BumpDecision


def classify(finding: Finding, decisions: list[BumpDecision]) -> str:
    """Pick a strategy string from the table above."""
    if finding.dockerfile in {"nix-built", "ko-built", "bazel-built", "jib-built"}:
        return "stuck-build-system"
    if finding.dockerfile in SENTINEL_DOCKERFILES:
        return "stuck-no-source"

    any_bumped = any(d.bumped for d in decisions)
    any_stale = any(d.classification == "left-alone-unsafe" for d in decisions)

    if any_bumped:
        return "local-patched" if finding.is_local else "fork-and-rebuild"
    if any_stale:
        return "skipped-unsafe"
    return "no-bumps-needed"


def emit(
    *,
    audit: AuditReport,
    items: list[tuple[Finding, list[BumpDecision], str]],
    target_registry: str,
    output_path: Path,
    tool_version: str,
) -> Path:
    """Write refresh-plan.json. Returns the path written."""
    plan = {
        "generated-at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool-version": tool_version,
        "target-registry": target_registry,
        "input-audit": {
            "generated-at": audit.generated_at,
            "os-currency-table-last-edited": audit.os_currency_table_last_edited,
            "table-stale": audit.table_stale,
        },
        "images": [_render_image(f, decisions, strategy, target_registry) for f, decisions, strategy in items],
    }
    output_path = Path(output_path)
    output_path.write_text(json.dumps(plan, indent=2) + "\n")
    return output_path


def _render_image(
    finding: Finding,
    decisions: list[BumpDecision],
    strategy: str,
    target_registry: str,
) -> dict:
    fork_image_name = finding.image.split("/")[-1].split(":")[0]
    upstream_tag = finding.image.split(":")[-1] if ":" in finding.image else "latest"

    entry = {
        "image": finding.image,
        "owning-chart": finding.owning_chart,
        "strategy": strategy,
        "source-repo": finding.source_repo,
        "tag-checkout": finding.tag_checkout,
        "from-decisions": [
            {
                "stage": e.stage,
                "before": e.from_,
                "after": d.new_from,
                "bumped": d.bumped,
                "reason": d.reason,
                "classification": d.classification,
            }
            for e, d in zip(finding.froms, decisions)
        ],
    }
    if strategy in {"fork-and-rebuild", "local-patched"}:
        entry["rebuilt-image-ref"] = (
            f"{target_registry}/{fork_image_name}-rebuilt:{upstream_tag}-rebuilt-<YYYYMMDD>"
        )
    return entry
