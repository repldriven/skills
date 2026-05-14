"""Decide which FROM lines to bump, and what to bump them to.

Pure functions, no I/O. Given a `FromEntry` from the audit and an
`--allow-bumps` policy, return a `BumpDecision` saying whether to
rewrite the line (and to what), or skip it (and why).

The currency table here is intentionally narrower than the audit
skill's full table — the tool only knows mappings that are
*safe-mechanical*. Anything riskier is left for the advisor skill to
classify, or for the user to apply manually with `--allow-bumps all`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from chart_supply_refresh.audit.core import FromEntry


# Currency table: (os-family, current-version) -> latest tag fragment to bump to.
# Used only when the source FROM is `one-behind` and the family/version
# matches a row here. Conservative on purpose.
SAFE_BUMP_TABLE: dict[tuple[str, str], str] = {
    ("Debian", "12"): "trixie",   # bookworm 12 -> trixie 13
    ("Debian", "11"): "trixie",   # bullseye 11 -> trixie 13 (skip bookworm; both EOL-bound)
    ("Ubuntu LTS", "22.04"): "24.04",
    ("Alpine", "3.22"): "3.23",
    ("Alpine", "3.21"): "3.23",
    ("RHEL-family", "8"): "9",
}


# Tag-fragment patterns -> replacement. Used to rewrite the FROM text.
# Pattern is a regex on the *codename or numeric* portion of the tag;
# the replacement is a literal substitution for that fragment.
# Example: "clojure:temurin-21-tools-deps-bookworm" -> swap "bookworm" -> "trixie".
TAG_FRAGMENT_REWRITES: dict[str, list[tuple[str, str]]] = {
    "Debian": [
        (r"\bbookworm\b", "trixie"),
        (r"\bbullseye\b", "trixie"),
        (r"(?<!\d)(?<!\.)12(?![\d.])", "13"),
        (r"(?<!\d)(?<!\.)11(?![\d.])", "13"),
    ],
    "Ubuntu LTS": [
        (r"\bjammy\b", "noble"),
        (r"(?<!\d)22\.04(?![\d.])", "24.04"),
    ],
    "Alpine": [
        (r"(?<!\d)3\.(?:21|22)(?![\d.])", "3.23"),
    ],
    "RHEL-family": [
        (r"\bubi8\b", "ubi9"),
        (r"(?<!\d)(?<!\.)8(?![\d.])", "9"),
    ],
}


@dataclass(frozen=True)
class BumpDecision:
    """Result of inspecting a single FROM entry."""

    bumped: bool
    new_from: str           # equals from_entry.from_ when bumped=False
    reason: str             # human-readable rationale
    classification: str     # safe-mechanical | left-alone-current | left-alone-unsafe |
                            # left-alone-rolling | left-alone-unsupported | left-alone-arg-undefined


def decide(entry: FromEntry, policy: str = "safe") -> BumpDecision:
    """Decide what to do with a single FROM line.

    policy:
      - "safe": only apply bumps in SAFE_BUMP_TABLE for `one-behind` findings.
      - "all":  apply bumps for `one-behind` AND `multi-behind` AND `non-lts-interim`.
                Still skips `rolling-*`, `current`, and `unsupported`.
    """
    if entry.currency == "current":
        return BumpDecision(False, entry.from_, "already current", "left-alone-current")

    if entry.currency in {"rolling-stable", "rolling-dev"}:
        return BumpDecision(
            False,
            entry.from_,
            f"moving-target tag ({entry.currency}); rebuilds happen upstream",
            "left-alone-rolling",
        )

    if entry.currency == "unsupported":
        return BumpDecision(
            False,
            entry.from_,
            "EOL release; bumping risks unrelated breakage — handle manually",
            "left-alone-unsupported",
        )

    if entry.from_ == "arg-undefined":
        return BumpDecision(
            False,
            entry.from_,
            "ARG without default; cannot infer current value",
            "left-alone-arg-undefined",
        )

    eligible = (
        entry.currency == "one-behind"
        or (policy == "all" and entry.currency in {"multi-behind", "non-lts-interim"})
    )
    if not eligible:
        return BumpDecision(
            False,
            entry.from_,
            f"currency={entry.currency!r} not eligible under policy={policy!r}",
            "left-alone-unsafe",
        )

    key = (entry.os_family, entry.os_version)
    if policy == "safe" and key not in SAFE_BUMP_TABLE:
        return BumpDecision(
            False,
            entry.from_,
            f"no safe-mechanical mapping for {entry.os_family} {entry.os_version}",
            "left-alone-unsafe",
        )

    new_from = _rewrite(entry.from_, entry.os_family)
    if new_from == entry.from_:
        return BumpDecision(
            False,
            entry.from_,
            f"no tag-fragment rewrite matched for {entry.os_family} (tag={entry.from_!r})",
            "left-alone-unsafe",
        )

    return BumpDecision(
        True,
        new_from,
        f"{entry.os_family} {entry.os_version} -> {SAFE_BUMP_TABLE.get(key, '(via policy=all)')}",
        "safe-mechanical",
    )


def _rewrite(from_text: str, os_family: str) -> str:
    """Apply the first matching tag-fragment rewrite for the family.

    Returns the original text unchanged if no pattern matches.
    """
    patterns = TAG_FRAGMENT_REWRITES.get(os_family, [])
    for pattern, replacement in patterns:
        new = re.sub(pattern, replacement, from_text)
        if new != from_text:
            return new
    return from_text
