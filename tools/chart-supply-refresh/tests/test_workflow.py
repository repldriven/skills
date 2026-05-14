import pytest
import yaml

from chart_supply_refresh.workflow import MatrixEntry, render


def _basic_matrix():
    return [
        MatrixEntry(image="fdb-kubernetes-operator", upstream_tag="v2.27.0"),
        MatrixEntry(image="pulsar-all", upstream_tag="4.0.10"),
    ]


def test_renders_valid_yaml():
    out = render(matrix=_basic_matrix(), target_registry="ghcr.io/repldriven")
    parsed = yaml.safe_load(out)
    assert parsed["name"] == "rebuild-supply-chain"
    # PyYAML parses 'on' as a bool key (True) because it's a YAML 1.1 truthy
    # literal. GH Actions itself is YAML 1.2-ish and reads it as the string.
    trigger_key = True if True in parsed else "on"
    triggers = parsed[trigger_key]
    assert "workflow_dispatch" in triggers
    assert triggers["schedule"][0]["cron"] == "0 3 * * MON"


def test_matrix_includes_every_entry():
    out = render(matrix=_basic_matrix(), target_registry="ghcr.io/repldriven")
    parsed = yaml.safe_load(out)
    matrix = parsed["jobs"]["rebuild"]["strategy"]["matrix"]["include"]
    images = {row["image"] for row in matrix}
    assert images == {"fdb-kubernetes-operator", "pulsar-all"}


def test_dockerfile_path_matches_image():
    out = render(matrix=_basic_matrix(), target_registry="ghcr.io/repldriven")
    parsed = yaml.safe_load(out)
    matrix = parsed["jobs"]["rebuild"]["strategy"]["matrix"]["include"]
    for row in matrix:
        assert row["dockerfile"] == f"dockerfiles/{row['image']}/Dockerfile"


def test_registry_host_extracted():
    out = render(matrix=_basic_matrix(), target_registry="ghcr.io/repldriven")
    assert "registry: ghcr.io" in out
    assert "ghcr.io/repldriven/" in out  # tag prefix


def test_gha_expressions_present_verbatim():
    # Critical: the template must emit literal `${{ ... }}` because
    # GH Actions consumes them as expressions. If Jinja eats them,
    # the workflow becomes a no-op.
    out = render(matrix=_basic_matrix(), target_registry="ghcr.io/repldriven")
    assert "${{ github.actor }}" in out
    assert "${{ secrets.GITHUB_TOKEN }}" in out
    assert "${{ matrix.image }}" in out
    assert "${{ steps.date.outputs.value }}" in out


def test_custom_cron_threaded_through():
    out = render(
        matrix=_basic_matrix(),
        target_registry="ghcr.io/repldriven",
        cron="0 5 * * *",
    )
    parsed = yaml.safe_load(out)
    trigger_key = True if True in parsed else "on"
    assert parsed[trigger_key]["schedule"][0]["cron"] == "0 5 * * *"


def test_empty_matrix_rejected():
    with pytest.raises(ValueError):
        render(matrix=[], target_registry="ghcr.io/repldriven")
