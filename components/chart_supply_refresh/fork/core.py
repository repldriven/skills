"""Apply bump decisions to a Dockerfile and write the forked output.

The clone-and-checkout side is a thin wrapper around `git`; the
meaningful logic is the patching of FROM lines, which is unit-tested
against fixture Dockerfiles on disk (no network).

Matching strategy: FROM lines in the source Dockerfile are matched
positionally against the audit finding's `froms` list. AS-clause
stage names are treated as a sanity check, not as the join key —
the audit's stage names sometimes diverge (e.g. "(final)" for
unnamed stages), so position is authoritative.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from chart_supply_refresh.audit.core import Finding, FromEntry
from chart_supply_refresh.bumps.core import BumpDecision


# Matches a Dockerfile FROM line, with optional --platform flag and AS clause.
# Captures the image reference so it can be substituted.
_FROM_RE = re.compile(
    r"^(?P<lead>\s*FROM\s+(?:--platform=\S+\s+)?)"
    r"(?P<image>\S+)"
    r"(?P<tail>(?:\s+AS\s+(?P<stage>\S+))?\s*(?:#.*)?)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ForkResult:
    """What `apply_bumps` produced."""

    dockerfile_path: Path
    source_md_path: Path
    bumps_applied: int
    bumps_skipped: int
    warnings: tuple[str, ...]


def apply_bumps(
    *,
    source_dockerfile: Path,
    output_dir: Path,
    finding: Finding,
    decisions: list[BumpDecision],
) -> ForkResult:
    """Read source_dockerfile, apply bumps positionally, write to output_dir.

    `decisions` is a list aligned with `finding.froms` (one BumpDecision per
    FromEntry, in source order).
    """
    if len(decisions) != len(finding.froms):
        raise ValueError(
            f"decisions count ({len(decisions)}) doesn't match froms count "
            f"({len(finding.froms)}) for image {finding.image!r}"
        )

    source_text = Path(source_dockerfile).read_text()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_lines: list[str] = []
    from_index = 0
    bumps_applied = 0
    bumps_skipped = 0
    warnings: list[str] = []

    for line in source_text.splitlines():
        match = _FROM_RE.match(line)
        if match is None:
            out_lines.append(line)
            continue

        if from_index >= len(finding.froms):
            warnings.append(
                f"Dockerfile has more FROM lines than audit finding "
                f"(line: {line.strip()!r})"
            )
            out_lines.append(line)
            from_index += 1
            continue

        entry = finding.froms[from_index]
        decision = decisions[from_index]

        # Sanity-check stage name; emit a warning but proceed.
        dockerfile_stage = match.group("stage")
        if dockerfile_stage and dockerfile_stage != entry.stage:
            warnings.append(
                f"stage-name mismatch at FROM index {from_index}: "
                f"audit={entry.stage!r}, dockerfile={dockerfile_stage!r}"
            )

        if decision.bumped:
            new_image = decision.new_from
            new_line = (
                line[: match.start("image")]
                + new_image
                + line[match.end("image") :]
            )
            out_lines.append(new_line)
            bumps_applied += 1
        else:
            out_lines.append(line)
            bumps_skipped += 1

        from_index += 1

    # Preserve trailing newline if source had one
    suffix = "\n" if source_text.endswith("\n") else ""
    dockerfile_path = output_dir / "Dockerfile"
    dockerfile_path.write_text("\n".join(out_lines) + suffix)

    source_md_path = output_dir / "SOURCE.md"
    source_md_path.write_text(_render_source_md(finding, decisions))

    return ForkResult(
        dockerfile_path=dockerfile_path,
        source_md_path=source_md_path,
        bumps_applied=bumps_applied,
        bumps_skipped=bumps_skipped,
        warnings=tuple(warnings),
    )


def _render_source_md(finding: Finding, decisions: list[BumpDecision]) -> str:
    """Per-image provenance + diff record."""
    lines = [
        f"# {finding.image}",
        "",
        f"- Source repo: `{finding.source_repo or '(unknown)'}`",
        f"- Tag checked out: `{finding.tag_checkout or '(n/a)'}`",
        f"- Original Dockerfile: `{finding.dockerfile}`",
        f"- Owning chart: `{finding.owning_chart}`",
        f"- Resolution signal: `{finding.resolution_signal}`",
        "",
        "## FROM-line decisions",
        "",
        "| # | Stage | Original FROM | New FROM | Decision |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, (entry, decision) in enumerate(zip(finding.froms, decisions)):
        verdict = "**bumped**" if decision.bumped else "left alone"
        lines.append(
            f"| {i} | {entry.stage} | `{entry.from_}` | "
            f"`{decision.new_from}` | {verdict} — {decision.reason} |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------- Network-side helpers (smoke-tested in e2e, not in units) ----------


def clone_and_checkout(*, source_repo: str, tag: str | None, dest: Path) -> str:
    """Shallow-clone `source_repo` into `dest`. If `tag` is set, check it out.

    Returns the resolved ref (the tag, or 'HEAD' on head-fallback).
    Raises subprocess.CalledProcessError on any git failure.
    """
    dest = Path(dest)
    if dest.exists() and (dest / ".git").exists():
        return _existing_head(dest)

    subprocess.run(
        ["git", "clone", "--depth=1", source_repo, str(dest)],
        check=True,
        capture_output=True,
    )
    if tag is None:
        return "HEAD"

    for candidate in (tag, f"v{tag}" if not tag.startswith("v") else tag.lstrip("v")):
        try:
            subprocess.run(
                ["git", "-C", str(dest), "fetch", "--depth=1", "origin", "tag", candidate],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(dest), "checkout", "--quiet", candidate],
                check=True,
                capture_output=True,
            )
            return candidate
        except subprocess.CalledProcessError:
            continue
    return "HEAD"  # tag-checkout: head-fallback


def _existing_head(repo: Path) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()
