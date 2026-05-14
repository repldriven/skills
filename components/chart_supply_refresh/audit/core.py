"""Schema + reader for the base-audit.json produced by audit-helm-chart-image-bases.

The audit emits one finding per `(image, dockerfile)` pair, with the
image's resolution-signal and a list of FROM entries (one per stage in
multi-stage Dockerfiles). The tool consumes this and decides per-image
which fork strategy to apply.

Special dockerfile sentinels (image cannot be forked normally):
- "dockerfile-ambiguous"          multiple candidates, no clean match
- "base-inferred-from-labels"     final base recovered via crane only
- "source-unknown"                source repo not found
- "<system>-built"                e.g. nix-built / ko-built / bazel-built
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SENTINEL_DOCKERFILES = frozenset(
    {
        "dockerfile-ambiguous",
        "base-inferred-from-labels",
        "source-unknown",
        "nix-built",
        "ko-built",
        "bazel-built",
        "jib-built",
    }
)


@dataclass(frozen=True)
class FromEntry:
    """One FROM line in a Dockerfile."""

    stage: str
    from_: str
    os_family: str
    os_version: str
    currency: str  # current | one-behind | multi-behind | rolling-stable | rolling-dev | non-lts-interim | unsupported


@dataclass(frozen=True)
class Finding:
    """One `(image, dockerfile)` audit entry. May carry multiple FROMs."""

    owning_chart: str
    image: str
    resolution_signal: str
    source_repo: str | None
    tag_checkout: str | None
    dockerfile: str
    froms: tuple[FromEntry, ...] = field(default_factory=tuple)

    @property
    def is_forkable(self) -> bool:
        """Can the tool fork and rebuild this image?"""
        return self.dockerfile not in SENTINEL_DOCKERFILES and self.source_repo is not None

    @property
    def is_local(self) -> bool:
        """Is the Dockerfile in the current repository?"""
        return self.resolution_signal == "local"


@dataclass(frozen=True)
class AuditReport:
    generated_at: str
    os_currency_table_last_edited: str
    table_stale: bool
    findings: tuple[Finding, ...]


def load(path: Path) -> AuditReport:
    """Read a base-audit.json file into an AuditReport."""
    raw = json.loads(Path(path).read_text())
    report = raw.get("report", {})
    findings = tuple(_parse_finding(f) for f in raw.get("findings", []))
    return AuditReport(
        generated_at=report.get("generated-at", ""),
        os_currency_table_last_edited=report.get("os-currency-table-last-edited", ""),
        table_stale=bool(report.get("table-stale", False)),
        findings=findings,
    )


def _parse_finding(raw: dict) -> Finding:
    return Finding(
        owning_chart=raw["owning-chart"],
        image=raw["image"],
        resolution_signal=raw["resolution-signal"],
        source_repo=raw.get("source-repo"),
        tag_checkout=raw.get("tag-checkout"),
        dockerfile=raw["dockerfile"],
        froms=tuple(
            FromEntry(
                stage=f["stage"],
                from_=f["from"],
                os_family=f["os-family"],
                os_version=f["os-version"],
                currency=f["currency"],
            )
            for f in raw.get("froms", [])
        ),
    )
