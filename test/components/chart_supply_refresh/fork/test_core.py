import textwrap
from pathlib import Path

import pytest

from chart_supply_refresh.audit.core import Finding, FromEntry
from chart_supply_refresh.bumps.core import BumpDecision
from chart_supply_refresh.fork.core import apply_bumps


def _finding(image, froms_data, dockerfile="Dockerfile", source_repo="https://github.com/x/y"):
    """Helper: build a Finding from a list of (stage, from_, family, version, currency) tuples."""
    return Finding(
        owning_chart="test",
        image=image,
        resolution_signal="chart-sources",
        source_repo=source_repo,
        tag_checkout="v1.0.0",
        dockerfile=dockerfile,
        froms=tuple(FromEntry(*row) for row in froms_data),
    )


def _bump(new_from, classification="safe-mechanical", reason="bumped"):
    return BumpDecision(True, new_from, reason, classification)


def _skip(orig_from, classification="left-alone-current", reason="ok"):
    return BumpDecision(False, orig_from, reason, classification)


def test_multistage_bumps_only_marked_stages(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(textwrap.dedent("""\
        FROM golang:1.25.8-bookworm AS builder
        WORKDIR /src
        COPY . .
        RUN go build -o app

        FROM rockylinux/rockylinux:9.6-minimal AS runtime
        COPY --from=builder /src/app /usr/local/bin/app
        ENTRYPOINT ["app"]
    """))
    finding = _finding("foundationdb/fdb-kubernetes-operator:v2.27.0", [
        ("builder", "golang:1.25.8-bookworm", "Debian", "12", "one-behind"),
        ("runtime", "rockylinux/rockylinux:9.6-minimal", "RHEL-family", "9", "current"),
    ])
    decisions = [
        _bump("golang:1.25.8-trixie"),
        _skip("rockylinux/rockylinux:9.6-minimal"),
    ]

    out = apply_bumps(
        source_dockerfile=dockerfile,
        output_dir=tmp_path / "fork",
        finding=finding,
        decisions=decisions,
    )

    patched = out.dockerfile_path.read_text()
    assert "FROM golang:1.25.8-trixie AS builder" in patched
    assert "FROM rockylinux/rockylinux:9.6-minimal AS runtime" in patched
    assert out.bumps_applied == 1
    assert out.bumps_skipped == 1
    assert out.warnings == ()


def test_platform_flag_preserved(tmp_path):
    """--platform=$BUILDPLATFORM should survive a bump intact."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM --platform=$BUILDPLATFORM node:22-alpine AS build\n")
    finding = _finding("ghcr.io/x/bank-app:0.0.0", [
        ("build", "node:22-alpine", "Alpine", "3.21", "one-behind"),
    ])
    decisions = [_bump("node:22-alpine3.23")]

    out = apply_bumps(
        source_dockerfile=dockerfile,
        output_dir=tmp_path / "fork",
        finding=finding,
        decisions=decisions,
    )

    patched = out.dockerfile_path.read_text()
    assert "FROM --platform=$BUILDPLATFORM node:22-alpine3.23 AS build" in patched
    assert out.bumps_applied == 1


def test_comments_and_blank_lines_preserved(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(textwrap.dedent("""\
        # Builder stage
        FROM golang:1.25.8-bookworm AS builder

        # Just a comment

        FROM rockylinux/rockylinux:9.6-minimal AS runtime
    """))
    finding = _finding("x:1", [
        ("builder", "golang:1.25.8-bookworm", "Debian", "12", "one-behind"),
        ("runtime", "rockylinux/rockylinux:9.6-minimal", "RHEL-family", "9", "current"),
    ])
    decisions = [_bump("golang:1.25.8-trixie"), _skip("rockylinux/rockylinux:9.6-minimal")]

    out = apply_bumps(
        source_dockerfile=dockerfile,
        output_dir=tmp_path / "fork",
        finding=finding,
        decisions=decisions,
    )
    patched = out.dockerfile_path.read_text()
    assert "# Builder stage" in patched
    assert "# Just a comment" in patched
    # Two blank lines between sections preserved.
    assert "\n\n# Just a comment" in patched


def test_source_md_written(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM alpine:3.21\n")
    finding = _finding("alpine:3.21", [
        ("stage-0", "alpine:3.21", "Alpine", "3.21", "one-behind"),
    ])
    decisions = [_bump("alpine:3.23", reason="Alpine 3.21 -> 3.23")]

    out = apply_bumps(
        source_dockerfile=dockerfile,
        output_dir=tmp_path / "fork",
        finding=finding,
        decisions=decisions,
    )
    md = out.source_md_path.read_text()
    assert "# alpine:3.21" in md
    assert "Alpine 3.21 -> 3.23" in md
    assert "`alpine:3.21`" in md and "`alpine:3.23`" in md


def test_stage_name_mismatch_warns_but_proceeds(tmp_path):
    """If AS clause says 'foo' but audit says 'bar', still bump but warn."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM alpine:3.21 AS foo\n")
    finding = _finding("alpine:3.21", [
        ("bar", "alpine:3.21", "Alpine", "3.21", "one-behind"),
    ])
    decisions = [_bump("alpine:3.23")]

    out = apply_bumps(
        source_dockerfile=dockerfile,
        output_dir=tmp_path / "fork",
        finding=finding,
        decisions=decisions,
    )
    assert out.bumps_applied == 1
    assert any("stage-name mismatch" in w for w in out.warnings)


def test_decisions_length_mismatch_rejected(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM alpine:3.21\n")
    finding = _finding("alpine:3.21", [
        ("stage-0", "alpine:3.21", "Alpine", "3.21", "one-behind"),
    ])
    with pytest.raises(ValueError):
        apply_bumps(
            source_dockerfile=dockerfile,
            output_dir=tmp_path / "fork",
            finding=finding,
            decisions=[_bump("alpine:3.23"), _bump("alpine:3.23")],  # too many
        )


def test_extra_from_in_dockerfile_warned(tmp_path):
    """Dockerfile has 3 FROMs but audit only tracks 2 — warn on the orphan."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(textwrap.dedent("""\
        FROM alpine:3.21 AS one
        FROM alpine:3.21 AS two
        FROM alpine:3.21 AS three
    """))
    finding = _finding("x:1", [
        ("one", "alpine:3.21", "Alpine", "3.21", "one-behind"),
        ("two", "alpine:3.21", "Alpine", "3.21", "one-behind"),
    ])
    decisions = [_bump("alpine:3.23"), _bump("alpine:3.23")]
    out = apply_bumps(
        source_dockerfile=dockerfile,
        output_dir=tmp_path / "fork",
        finding=finding,
        decisions=decisions,
    )
    assert out.bumps_applied == 2
    assert any("more FROM lines than audit" in w for w in out.warnings)
