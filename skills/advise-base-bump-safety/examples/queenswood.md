# Worked example: queenswood chart

Applies the rubric to the same audit output covered by
[`audit-helm-chart-image-bases/examples/queenswood.md`](../../audit-helm-chart-image-bases/examples/queenswood.md).
Captured 2026-05-14 against Chart.yaml v0.5.3; image tags as
pinned at audit time.

## Audit findings under consideration

Out of the 7 distinct audit entries the audit produced, 4 carry at
least one FROM that's not already `current`:

| Entry | Image | Stale FROMs |
| --- | --- | --- |
| 1 (services) | `ghcr.io/repldriven/<svc>:0.0.0` | build = `clojure:temurin-21-tools-deps-bookworm` (Debian 12, one-behind) |
| 3 | `alpine/k8s:1.30.14` | `alpine:edge` (rolling-dev) |
| 4 | `foundationdb/fdb-kubernetes-operator:v2.27.0` | builder = `golang:1.25.8-bookworm` (Debian 12, one-behind) |
| 7 | `alpine/k8s:1.32.12` | `alpine:edge` (rolling-dev) |

Everything else (`eclipse-temurin:21-jre-noble`,
`rockylinux/rockylinux:9.6-minimal`, the Alpine 3.21 stages in
the pulsar build) was already `current` per the audit — those
become `no-action-needed` rows in the advice doc, not omitted.

## Classification walkthrough

### Entry 1, `build` stage — `clojure:temurin-21-tools-deps-bookworm`

- **Proposed target**: `clojure:temurin-21-tools-deps-trixie`
  (Debian 12 → 13 via the audit's currency table).
- **Indicators checked**:
  - Same OS family (Debian both sides). ✓
  - Workload: this is a **build stage** — the output is a JAR
    that the runtime stage copies out via `COPY --from=build`.
    The JAR doesn't ship glibc-linked code; it's bytecode for
    the JVM runtime stage.
  - JVM / Eclipse Temurin re-resolves system libs at startup.
  - No license boundary. No EOL / dev branch.
- **Classification**: `safe-mechanical`.
- **Specific safe pattern matched**: "Eclipse Temurin / OpenJDK
  moving Debian major".
- **Recommended action**: apply mechanically; the rebuilt build
  stage will compile the same uberjar against trixie's glibc, but
  the artefact crossing the COPY boundary is JVM bytecode +
  resources, unaffected.

### Entry 4, `builder` stage — `golang:1.25.8-bookworm`

- **Proposed target**: `golang:1.25.8-trixie`.
- **Indicators checked**:
  - Same OS family.
  - Workload: Go binary. The fdb-kubernetes-operator binary is
    statically linked unless cgo is enabled. The operator's
    Dockerfile uses `CGO_ENABLED=0` (verifiable from the v2.27.0
    Dockerfile body — out of scope to re-quote here, but visible
    in the audit's evidence).
  - No license. No EOL / dev branch.
- **Classification**: `safe-mechanical`.
- **Specific safe pattern matched**: "Go-built images moving
  Debian / RHEL major".

### Entries 3 + 7 — `alpine:edge` in `alpine-docker/k8s`

- **Proposed target**: `alpine:3.23` (pin to current stable).
- **Indicators checked**:
  - **Rolling-dev source** fires immediately: `before` is
    `alpine:edge`.
- **Classification**: `not-recommended`.
- **Recommended action**: pin to `alpine:3.23`. A mechanical
  rebuild that stayed on `alpine:edge` would put the chart back
  on the same dev branch — `chart-supply-refresh --allow-bumps
  safe` will (correctly) skip this entry. Open an upstream
  issue with `alpine-docker/k8s` or fork their Dockerfile if
  the chart needs this image rebuilt off a stable Alpine.
- **Notes**: the audit also flagged that
  `1.30.14`/`1.32.12` (the kubectl version in the image tag)
  doesn't correspond to a Git tag on `alpine-docker/k8s`, so
  this Dockerfile was read at `head-fallback`. A safer
  resolution is "stop using `alpine/k8s` for the wait-loops and
  pin to a smaller image of your own choosing", but that's a
  base-replacement decision, not a base-version bump.

### `no-action-needed` entries (reported, not silently dropped)

These appear in `advice.md` for completeness:

- Entry 1 `runtime`: `eclipse-temurin:21-jre-noble` (Ubuntu LTS
  24.04, current).
- Entry 2 `build` + `runtime`: `node:22-alpine`,
  `nginxinc/nginx-unprivileged:1.27-alpine` (Alpine 3.21 inferred,
  current).
- Entry 4 `runtime`: `rockylinux/rockylinux:9.6-minimal`
  (RHEL-family 9, current).
- Entry 5: `foundationdb/fdb-kubernetes-monitor:7.4.1` (base
  inferred from labels as `rockylinux:9-minimal`, current).
- Entry 6: all four stages of `pulsar-all:4.0.10` (Alpine 3.21,
  current).

## Headline summary

```
Classification counts (12 FROMs across 7 audit entries):
  safe-mechanical       2   (queenswood-services build + fdb-operator builder)
  not-recommended       2   (alpine:edge ×2 in alpine-docker/k8s)
  no-action-needed      8   (all runtime stages + pulsar stages + already-current bases)
  requires-migration    0
  license-aware         0
  interim-caution       0
```

If `chart-supply-refresh --allow-bumps safe` consumes this
`advice.md`, the two `safe-mechanical` entries are the only ones
it will patch; the two `not-recommended` entries are surfaced for
manual follow-up.
