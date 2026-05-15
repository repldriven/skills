---
name: map-helm-chart-image-bases
description: >
  Use when the user needs a license-tier map of every base OS a Helm
  chart pulls — typically after the Bitnami catalog retirement, during
  a procurement audit, or when answering "what licensed thing is
  hiding two layers down". Triggers on: "audit my chart for licensed
  bases", "find Bitnami in my chart", "post-Bitnami chart audit",
  "what's commercial in this Helm dependency tree", "build a
  dependency graph of base OSes", "escape paths off RHEL UBI",
  "trace base images for license tier". Walks the chart →
  workload → imageref → base → OS chain, classifies each base into
  free / free-with-caveats / commercial / stale, and recommends a
  per-source-family escape hatch. Complements
  audit-helm-chart-image-bases (currency-focused) by tracking
  licensing instead. Pairs with advise-base-bump-safety when an
  escape doubles as a bump.
domain: cybersecurity
subdomain: supply-chain-security
tags:
  - supply-chain-security
  - container-security
  - helm
  - kubernetes
  - license-compliance
  - base-image-tracing
  - dependency-graph
version: '0.1'
author: kjothen
license: Apache-2.0
nist_csf:
  - PR.PS-01
  - PR.PS-02
  - ID.RA-01
  - ID.RA-05
---

# Map Helm Chart Image Bases

Build a dependency graph of every base OS a Helm chart pulls and
classify each base by license tier (free / free-with-caveats /
commercial / stale). For licensed or stale bases, recommend a
per-source-family escape hatch. **Read-only**: this skill emits a
graph + report; it does not modify charts, images, or registries.

See [references/license-tiers.md](./references/license-tiers.md)
for the four-tier rubric and the Bitnami-retirement context that
motivates urgent `stale`-tier handling.

## When to Use

Use when answering procurement / supplier-risk questions about a
Helm chart's image tree — "which bases are licensed?", "what does a
Bitnami escape look like for our charts?", "is anything pinned to a
deprecated `bitnamilegacy` tag?", or when you need a graph
artefact for a security review.

**Do not use** for: "is the OS *patched*?" (use
`audit-helm-chart-image-bases`), "is this *bump* safe?" (use
`advise-base-bump-safety`), or CVE enumeration (pair with a
CVE-aware scanner — this skill cares about license tier, not
patch state).

## Prerequisites

- `helm` ≥ 3.14 with the chart's dependencies fetched.
- `crane` for OCI labels and (in v0.2) layer-digest correlation.
- `syft` for the OS-detection fallback when labels and SBOMs are
  absent. Optional but improves coverage; the skill degrades
  gracefully when missing.
- `cosign` for verifying / reading attached SBOMs. Optional;
  authoritative when present.
- `python3` + PyYAML for the YAML-aware enumeration step.
- `jq` for JSON consumption.
- Network access to the chart's image registries (private
  registries need auth threaded through `crane`, `syft`, and
  `cosign` separately).

## Inputs

- **chart** (required): chart reference — local path, OCI URL, or
  `repo/name[@version]`.
- **platform** (optional, defaults to `linux/amd64`): the manifest
  to inspect. Multi-arch manifests can produce inconsistent
  results across runs if not pinned.
- **registry-creds** (optional): credentials for private registries
  (`docker login` is the simplest path; `crane auth login` works
  too).

## Graph schema

The output is a graph with five node types and five edge types.
Stable across runs.

**Nodes**:

- `Chart` — top of the tree (one per `helm template` invocation).
- `Workload` — Deployment, StatefulSet, DaemonSet, Job, CronJob.
- `ImageRef` — `registry/repo:tag@sha256:...`. Always include the
  digest if resolvable.
- `BaseImage` — recursive parent of an `ImageRef`. The chain of
  bases up to (and including) `OSDistribution`.
- `OSDistribution` — `{ id: rhel, version: 9.4 }`,
  `{ id: wolfi }`, `{ id: scratch }`, etc.

**Edges**:

- `Chart -[deploys]-> Workload`
- `Workload -[runs]-> ImageRef`
- `ImageRef -[built_from]-> BaseImage` (recursive)
- `ImageRef -[contains]-> OSDistribution`
- `ImageRef -[shares_layer]-> ImageRef` — **deferred to v0.2**.
  Useful for "we have one base problem, not eight" insights but
  requires per-image `crane manifest` calls.

## Workflow

### Step 0: Render the chart + enumerate ImageRefs

Same YAML-aware parse as `audit-helm-chart-image-bases` (handles
Crossplane `.spec.package` on `pkg.crossplane.io` resources).
**Critically**: resolve subchart values overrides explicitly.
Bitnami charts in particular pin images via subchart values, not
templates — a naive template scan misses them.

```bash
helm dependency update "$CHART"
helm template eval-run "$CHART" --set <required-values> \
  > /tmp/render-default.yaml
```

Then walk the rendered YAML for every `image:` key and every
`.spec.package` on Crossplane CRDs (same Python walker as the
audit skill). Record each ImageRef once, with its `(workload,
image-ref)` provenance.

### Step 1: Build the graph skeleton

For each unique ImageRef from Step 0, create the Chart → Workload
→ ImageRef chain. One node per unique entity; one edge per
relationship. The graph is small at this point (no bases yet) —
it's the scaffold that Step 2's resolution fills in.

### Step 2: Resolve base for each ImageRef (detection chain)

Walk the detection chain in strict order; stop at the first
authoritative hit; record the signal. See
[references/detection-chain.md](./references/detection-chain.md)
for the full ordering, but the concrete invocations are:

```bash
# 1. cosign attestation (authoritative when present)
cosign download attestation "$IMAGE" --platform linux/amd64 \
  | jq -r '.payload | @base64d | fromjson | .predicate'

# 2. OCI labels (authoritative when set)
crane config "$IMAGE" --platform linux/amd64 \
  | jq -r '.config.Labels | {
      base: ."org.opencontainers.image.base.name",
      digest: ."org.opencontainers.image.base.digest"
    }'

# 3. Syft scan (heuristic but usually works)
syft "$IMAGE" --platform linux/amd64 -o json \
  | jq '.distro'   # { id: "alpine", version: "3.21" } etc.

# 4. Distroless / scratch fallback: empty distro → "no OS"
```

Record one of: `cosign-attestation`, `oci-label`, `syft-scan`,
`distroless-or-scratch`, `detection-failed`. Only the last is a
true unknown.

### Step 3: Classify each base by license tier

Match each `(detected-OS, image-source-family)` against the rubric
in [references/license-tiers.md](./references/license-tiers.md).
The four tiers are: `free`, `free-with-caveats`, `commercial`,
`stale`. **Distinguish them**: a free Chainguard public image and
a paid `cgr.dev/chainguard-private/*` image must not be lumped
into a single "Chainguard" verdict. The license tier is the load-
bearing teaching of this skill.

### Step 4: Look up the escape hatch

For each base classified as `free-with-caveats`, `commercial`, or
`stale`, look up the recommended escape in
[references/escape-hatches.md](./references/escape-hatches.md).
Mark `no-escape-needed` for `free` bases. The escape table is per
source-family; pick the first viable target for the workload type
(e.g. Postgres replacement for Bitnami Postgres, not a generic
"Docker Official" pointer).

### Step 5: Emit the graph

Two artifacts:

- `image-graph.json` — full structured graph: `{ chart_uri,
  generated_at, nodes: [...], edges: [...], detection_signals:
  {...}, license_tiers: {...}, escape_hatches: {...} }`.
- `image-graph.md` — human report. Top: summary panel (counts per
  tier). Body: per-image table sorted with `commercial` and
  `stale` at the top — those are the actionable findings.

## Gotchas

- **Multi-arch manifests**: always specify `--platform`. A chart
  whose `linux/amd64` manifest uses one base and `linux/arm64`
  uses another produces inconsistent runs if not pinned.
- **Private registries**: `crane`, `syft`, and `cosign` each
  authenticate separately. A user-shell `docker login` does not
  thread to all three; use registry-specific credential helpers.
- **Free distro + non-free packages**: the base OS may be free
  but the workload's packages aren't. OS classification is
  **necessary but not sufficient** — when a cosign SBOM is
  present and the packages contradict the OS tier, surface the
  conflict as a note. Don't silently upgrade the tier; the user
  owns the call.

## Hard Constraints

- **Read-only.** Never modify charts, images, or registries.
- **Always record the detection signal.** Every ImageRef carries
  one of the five signals from Step 2. No silent guesses.
- **Tier classification is non-collapsible.** Free Chainguard
  public images and paid `chainguard-private` images are
  separate tiers; do not collapse to a vendor verdict.
- **Distroless / scratch is not a failure.** Detection signal
  `distroless-or-scratch`, tier `n/a`, escape `no-escape-needed`.
- **No invented CVE / vendor claims.** This skill classifies
  license tier, not vulnerability state. Pair with a CVE-aware
  tool if that's what you need.
