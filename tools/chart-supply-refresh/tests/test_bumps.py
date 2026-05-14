from chart_supply_refresh.audit import FromEntry
from chart_supply_refresh.bumps import decide


def _fe(from_, family, version, currency="one-behind", stage="build"):
    return FromEntry(
        stage=stage, from_=from_, os_family=family, os_version=version, currency=currency
    )


# --- safe-mechanical bumps ---------------------------------------------------

def test_debian_bookworm_codename_bumps_to_trixie():
    d = decide(_fe("clojure:temurin-21-tools-deps-bookworm", "Debian", "12"))
    assert d.bumped is True
    assert d.new_from == "clojure:temurin-21-tools-deps-trixie"
    assert d.classification == "safe-mechanical"


def test_debian_numeric_12_bumps_to_13():
    d = decide(_fe("golang:1.25.8-12", "Debian", "12"))
    assert d.bumped is True
    assert d.new_from == "golang:1.25.8-13"


def test_ubuntu_lts_jammy_bumps_to_noble():
    d = decide(_fe("eclipse-temurin:21-jre-jammy", "Ubuntu LTS", "22.04"))
    assert d.bumped is True
    assert d.new_from == "eclipse-temurin:21-jre-noble"


def test_alpine_322_bumps_to_323():
    d = decide(_fe("alpine:3.22", "Alpine", "3.22"))
    assert d.bumped is True
    assert d.new_from == "alpine:3.23"


def test_rhel_ubi8_bumps_to_ubi9():
    d = decide(_fe("redhat/ubi8:latest", "RHEL-family", "8"))
    assert d.bumped is True
    assert d.new_from == "redhat/ubi9:latest"


# --- left alone (current / rolling / etc.) -----------------------------------

def test_current_is_left_alone():
    d = decide(_fe("debian:trixie-slim", "Debian", "13", currency="current"))
    assert d.bumped is False
    assert d.classification == "left-alone-current"


def test_rolling_dev_is_left_alone():
    d = decide(_fe("alpine:edge", "Alpine", "edge", currency="rolling-dev"))
    assert d.bumped is False
    assert d.classification == "left-alone-rolling"


def test_rolling_stable_is_left_alone():
    d = decide(_fe("gcr.io/distroless/static:nonroot", "distroless", "rolling", currency="rolling-stable"))
    assert d.bumped is False
    assert d.classification == "left-alone-rolling"


def test_unsupported_is_left_alone():
    d = decide(_fe("debian:buster", "Debian", "10", currency="unsupported"))
    assert d.bumped is False
    assert d.classification == "left-alone-unsupported"


def test_arg_undefined_is_left_alone():
    d = decide(_fe("arg-undefined", "Debian", "?", currency="one-behind"))
    assert d.bumped is False
    assert d.classification == "left-alone-arg-undefined"


# --- policy gating -----------------------------------------------------------

def test_non_lts_interim_skipped_under_safe_policy():
    d = decide(_fe("ubuntu:24.10", "Ubuntu interim", "24.10", currency="non-lts-interim"), policy="safe")
    assert d.bumped is False
    assert d.classification == "left-alone-unsafe"


def test_multi_behind_skipped_under_safe_policy():
    d = decide(_fe("alpine:3.18", "Alpine", "3.18", currency="multi-behind"), policy="safe")
    assert d.bumped is False
    assert d.classification == "left-alone-unsafe"


def test_multi_behind_bumps_under_all_policy_when_table_has_entry():
    # 3.18 isn't in SAFE_BUMP_TABLE, but the alpine rewrite pattern
    # only matches 3.21|3.22, so this still falls through.
    d = decide(_fe("alpine:3.18", "Alpine", "3.18", currency="multi-behind"), policy="all")
    assert d.bumped is False  # rewrite pattern doesn't match 3.18; honest skip


def test_safe_policy_skips_families_outside_table():
    # An unknown family with currency=one-behind shouldn't be bumped under safe.
    d = decide(_fe("imaginary:1.0", "ImaginaryOS", "5", currency="one-behind"), policy="safe")
    assert d.bumped is False
    assert d.classification == "left-alone-unsafe"


# --- edge cases in tag-fragment rewriting ------------------------------------

def test_no_double_substitution_when_pattern_misses():
    # Family says Debian 12, but the FROM is "node:22-alpine" (no debian
    # tag fragment present). Tool should NOT invent one.
    d = decide(_fe("node:22-alpine", "Debian", "12"))
    assert d.bumped is False
    assert "no tag-fragment rewrite matched" in d.reason


def test_amazoncorretto_alpine_321_bumps():
    # Real pulsar-all multi-stage example.
    d = decide(_fe("amazoncorretto:21-alpine3.21", "Alpine", "3.21"))
    assert d.bumped is True
    assert d.new_from == "amazoncorretto:21-alpine3.23"
