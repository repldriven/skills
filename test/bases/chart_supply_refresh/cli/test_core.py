"""End-to-end: drive the CLI against the queenswood fixture, in --offline mode.

Asserts the structural shape of the produced fork bundle. Does NOT
exercise the network clone path; that's smoke-tested out-of-band.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# Walk up from test/bases/chart_supply_refresh/cli/test_core.py to test/.
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def _run_cli(output_dir: Path, **overrides) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, "-m", "chart_supply_refresh.cli.core",
        "--chart", str(FIXTURES / "chart"),
        "--audit", str(FIXTURES / "audit-queenswood.json"),
        "--target-registry", overrides.get("target_registry", "ghcr.io/repldriven"),
        "--allow-bumps", overrides.get("allow_bumps", "safe"),
        "--output", str(output_dir),
        "--repo-root", str(FIXTURES / "repo"),
        "--offline",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_e2e_offline_produces_expected_layout(tmp_path):
    out = tmp_path / "fork"
    res = _run_cli(out)
    assert res.returncode == 0, f"CLI failed:\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}"

    # Top-level layout
    assert (out / "chart").is_dir()
    assert (out / "chart" / "Chart.yaml").is_file()
    assert (out / "dockerfiles").is_dir()
    assert (out / ".github" / "workflows" / "rebuild.yml").is_file()
    assert (out / "refresh-plan.json").is_file()


def test_e2e_local_dockerfiles_patched_in_place_correctly(tmp_path):
    out = tmp_path / "fork"
    res = _run_cli(out)
    assert res.returncode == 0, res.stderr

    # Service Dockerfile: build stage was bookworm (one-behind) -> trixie;
    # runtime was noble (current) -> unchanged.
    svc = (out / "dockerfiles" / "bank-api-service" / "Dockerfile").read_text()
    assert "clojure:temurin-21-tools-deps-trixie" in svc
    assert "bookworm" not in svc
    assert "eclipse-temurin:21-jre-noble" in svc

    # Bank-app: both stages are current -> classify as no-bumps-needed,
    # so its Dockerfile is NOT copied to the output (nothing to patch).
    assert not (out / "dockerfiles" / "bank-app").exists()


def test_e2e_workflow_matrix_has_correct_entries(tmp_path):
    out = tmp_path / "fork"
    res = _run_cli(out)
    assert res.returncode == 0, res.stderr

    wf = yaml.safe_load((out / ".github" / "workflows" / "rebuild.yml").read_text())
    matrix = wf["jobs"]["rebuild"]["strategy"]["matrix"]["include"]
    images = {row["image"] for row in matrix}
    # fdb-kubernetes-operator is fork-and-rebuild (offline so no patch happens
    # but it's still in the matrix). bank-api-service is local-patched (NOT in
    # the matrix). bank-app has no bumps. fdb-kubernetes-monitor is stuck.
    # alpine/k8s is rolling-dev so left alone.
    assert "fdb-kubernetes-operator" in images
    assert "bank-api-service" not in images
    assert "bank-app" not in images


def test_e2e_refresh_plan_strategy_breakdown(tmp_path):
    out = tmp_path / "fork"
    res = _run_cli(out)
    assert res.returncode == 0, res.stderr

    plan = json.loads((out / "refresh-plan.json").read_text())
    strategies = {entry["image"]: entry["strategy"] for entry in plan["images"]}
    assert strategies["ghcr.io/repldriven/bank-api-service:0.0.0"] == "local-patched"
    assert strategies["ghcr.io/repldriven/bank-app:0.0.0"] == "no-bumps-needed"
    assert strategies["foundationdb/fdb-kubernetes-operator:v2.27.0"] == "fork-and-rebuild"
    assert strategies["foundationdb/fdb-kubernetes-monitor:7.4.1"] == "stuck-no-source"
    assert strategies["alpine/k8s:1.30.14"] == "no-bumps-needed"


def test_e2e_output_dir_must_not_exist(tmp_path):
    out = tmp_path / "fork"
    out.mkdir()
    res = _run_cli(out)
    assert res.returncode != 0
    assert "already exists" in (res.stderr + res.stdout)


def test_e2e_rebuilt_image_ref_template_present(tmp_path):
    out = tmp_path / "fork"
    res = _run_cli(out)
    assert res.returncode == 0
    plan = json.loads((out / "refresh-plan.json").read_text())
    fdb = next(e for e in plan["images"] if e["image"].startswith("foundationdb/fdb-kubernetes-operator"))
    assert fdb["rebuilt-image-ref"] == \
        "ghcr.io/repldriven/fdb-kubernetes-operator-rebuilt:v2.27.0-rebuilt-<YYYYMMDD>"
