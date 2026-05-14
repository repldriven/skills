---
name: audit-helm-chart-image-bases
description: >
  Audit the transitive Dockerfile base images of every Docker image
  a Helm chart pulls. Resolve each image back to its source
  Dockerfile (via Chart.yaml sources, local Dockerfiles, or
  owner/name slug heuristics — OCI labels rarely carry source URLs
  in practice), parse FROM instructions, and report which base
  OS releases are outdated. Use to surface stale Debian / Ubuntu /
  Alpine / UBI bases hidden several layers deep in a chart's image
  tree.
domain: cybersecurity
subdomain: supply-chain-security
tags:
  - supply-chain-security
  - container-security
  - helm
  - kubernetes
  - dockerfile
  - base-image-audit
  - os-currency
version: '0.2'
author: kjothen
license: Apache-2.0
nist_csf:
  - PR.PS-01
  - PR.PS-02
  - ID.RA-01
  - DE.CM-08
---

# Audit Helm Chart Image Bases

Audit a Helm chart's transitive Dockerfile base images. For every
container image the chart pulls, walk the chain back to the
Dockerfile that built it, parse the `FROM` instructions, and
report which base OS releases are stale (e.g. Debian bookworm
when Debian trixie is the current stable, Ubuntu 22.04 when
24.04 LTS is out).

This is the audit half of an eventual upgrade workflow. It is
**read-only**. It does not modify charts, Dockerfiles, or
registry images. Remediation — patching Dockerfiles and
rebuilding the affected images — is a separate, heavier
capability to layer on top.

## When to Use

- When a Helm chart's images need a security-driven OS refresh
  and you need to know *which* of its transitive Dockerfiles are
  still on an old major release.
- When auditing a chart you vendored locally (the upstream
  doesn't publish a Helm repo) and you want to verify the
  upstream Dockerfiles haven't drifted onto a stale base since
  you vendored.
- When investigating a CVE that affects a specific OS major and
  you need to enumerate the Dockerfiles across the chart's
  image set that still build on the affected major.
- When establishing a baseline before a refactor that will
  rebuild every image off a fresh base.

**Do not use** for:

- Bumping image *tags* on already-published hardened images
  (Renovate / Dependabot handle that pattern).
- Rewriting Dockerfiles to switch to Chainguard / distroless
  bases (that is base-replacement, not base-version-currency).
- Producing a values override that swaps image refs without
  rebuilding (this skill does not emit values overrides).

## Prerequisites

- `helm` ≥ 3.14 with the chart's dependencies fetched
  (`helm dependency update`).
- `git` for shallow-cloning upstream source repositories.
- `crane` for inspecting registry image configs (the OCI label
  signal). Optional in practice — most images do not carry
  `org.opencontainers.image.source`.
- `python3` with PyYAML installed for YAML-aware parsing of the
  rendered chart (multi-document YAML, Crossplane `package:`
  extraction).
- `jq` for emitting the structured report.
- Network access to GitHub and the chart's image registries.

## Inputs

- **chart** (required): chart reference — local filesystem path,
  OCI URL, or `repo/name[@version]`.
- **local-owner-prefixes** (optional): image registry/owner
  prefixes that indicate an image is built from a Dockerfile in
  the current repository (e.g. `ghcr.io/kjothen` for queenswood).
  When matched, resolution skips upstream lookup and reads the
  local Dockerfile directly.
- **org-translations** (optional): map of Docker Hub org names to
  GitHub org names, for the slug-heuristic resolver. Ships with
  built-in defaults for common cases (`apachepulsar` →
  `apache`/`pulsar`, `foundationdb` → `FoundationDB`).

## Workflow

### Step 0: Render and inventory

Render the chart with defaults and extract every image reference,
including Crossplane package references (which use `package:`
keys on `pkg.crossplane.io` resources, not `image:`).

Use a YAML-aware parse, not a regex sweep. `helm template` emits
multi-document YAML; `yaml.safe_load_all` walks it cleanly and
lets you discriminate by `kind` / `apiVersion` so Crossplane
packages don't get confused with unrelated `package:` keys
elsewhere (npm `package.json` embedded in a ConfigMap, etc.).

```bash
helm dependency update "$CHART"
helm template eval-run "$CHART" --set <required-values> \
  > /tmp/render-default.yaml

python3 - <<'PY'
import yaml, pathlib

text = pathlib.Path('/tmp/render-default.yaml').read_text()

src_by_doc = []
current = None
for chunk in text.split('\n---\n'):
    first = next((l for l in chunk.splitlines() if l.startswith('# Source: ')), None)
    src_by_doc.append(first[len('# Source: '):] if first else current)
    if first: current = first[len('# Source: '):]

CROSSPLANE_PACKAGE_KINDS = {'Provider', 'Function', 'Configuration'}

def walk_images(node, sink):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == 'image' and isinstance(v, str):
                sink.append(('container-image', v))
            else:
                walk_images(v, sink)
    elif isinstance(node, list):
        for item in node:
            walk_images(item, sink)

hits = []
for i, doc in enumerate(yaml.safe_load_all(text)):
    if not doc:
        continue
    src = src_by_doc[i] if i < len(src_by_doc) else None
    images = []
    walk_images(doc, images)
    for kind, ref in images:
        hits.append((kind, ref, src))
    api = (doc.get('apiVersion') or '')
    kind = doc.get('kind') or ''
    if api.startswith('pkg.crossplane.io/') and kind in CROSSPLANE_PACKAGE_KINDS:
        pkg = (doc.get('spec') or {}).get('package')
        if isinstance(pkg, str):
            hits.append(('crossplane-package', pkg, src))

seen = {}
for kind, ref, src in hits:
    seen.setdefault((kind, ref), src)
for (kind, ref), src in sorted(seen.items()):
    print(f"{kind}\t{ref}\t{src}")
PY
```

The output has three columns: the kind (`container-image` or
`crossplane-package`), the image/package reference, and the
source template. Crossplane packages are audited identically to
container images from step 2 onward — they're OCI artifacts in
disguise — but the kind column lets the report distinguish them.

### Step 1: Group images by owning chart

For each unique image, the owning chart is the one whose
`# Source:` comment includes it. Map every image to:

- the chart name (main chart or subchart alias),
- the chart's `Chart.yaml` location on disk,
- the chart's `sources:` field (read from `Chart.yaml`).

This is the input to step 2's resolver.

### Step 2: Resolve each image to its source repository

Try resolution signals in this order — stop at the first hit:

1. **Local Dockerfile match.** If the image owner is in
   `local-owner-prefixes`, look for a Dockerfile inside the
   current repository whose path or naming aligns with the image
   name. Convention here: image `ghcr.io/<owner>/<service>:<tag>`
   typically builds from `infra/docker/<service>/Dockerfile` or a
   shared `infra/docker/service/Dockerfile` parameterised by
   build args. The skill must record which Dockerfile it matched
   and why.

2. **Chart.yaml `sources:`** of the owning chart. First URL is
   typically the image repo. Strip any
   `/tree/<branch>/<subpath>` suffix to get the repo root that
   can be cloned. If the field lists multiple URLs, the first
   pointing at a known code-hosting host (github.com, gitlab.com,
   bitbucket.org) wins; subsequent URLs are recorded as
   alternates.

3. **Slug heuristic with canonical-org translation.** Split the
   image into `<owner>/<name>`. Apply known translations from
   the `org-translations` map (Docker Hub orgs often diverge
   from their GitHub orgs, e.g. `apachepulsar` →
   `apache/pulsar`; `foundationdb` → `FoundationDB`; case
   matters on GitHub). Probe candidate URLs with
   `git ls-remote --exit-code`:
   - `https://github.com/<gh-owner>/<name>`
   - `https://github.com/<gh-owner>/docker-<name>`
   - `https://github.com/<gh-owner>/<name>-docker`

4. **OCI image labels** (`org.opencontainers.image.source`,
   `org.label-schema.vcs-url`). Pull the image's config via
   `crane config <image>` and inspect labels.
   - Real-world note: large families like `foundationdb/*`,
     `apachepulsar/*`, `alpine/k8s` do **not** publish this
     label, so this signal is a last resort for source-URL
     lookup. Listed for completeness; do not rely on it.

If none of the four signals above resolves a Dockerfile, the
image's *source repo* is `source-unknown` — but step 5 has a
fallback that can still identify the **final-stage base** via
inherited labels (see below).

Record the signal used (`local`, `chart-sources`,
`slug-heuristic`, `oci-label`, `base-inferred-from-labels`,
`source-unknown`) for every image in the report.

**Fallback for `source-unknown` / `dockerfile-ambiguous`:
inherited base labels.** `crane config <image>` surfaces the
*final* image's labels, which often inherit identifying labels
from the base image — `name`, `version`, `vendor`,
`org.opencontainers.image.vendor` — without the image setting
those labels itself. Example real-world chain:

```bash
$ crane config foundationdb/fdb-kubernetes-monitor:7.4.1 \
    | jq '.config.Labels | {name, version, vendor: ."org.opencontainers.image.vendor"}'
{
  "name": "rockylinux",
  "version": "9-minimal",
  "vendor": "Rocky Enterprise Software Foundation"
}
```

The monitor image carries no source-URL label of its own, but
Rocky Linux's own image-config labels are inherited intact —
sufficient to identify the *final* base layer as
`rockylinux:9-minimal`. Record this as
`base-inferred-from-labels`. Two caveats: it identifies only
the runtime/final stage, not any build stages; and it cannot
substitute for reading the Dockerfile when the latter is
available.

### Step 3: Shallow-clone each unique source repository

```bash
mkdir -p /tmp/chart-base-audit
for url in $UNIQUE_REPO_URLS; do
  dir=$(echo "$url" | sed 's|https://||; s|/|-|g')
  test -d "/tmp/chart-base-audit/$dir" \
    || git clone --depth=1 "$url" "/tmp/chart-base-audit/$dir"
done
```

Deduplicate by repo URL so a chart with 10 images from the same
repo only clones once.

### Step 3.5: Check out the release tag matching the image version

**HEAD ≠ release.** A clone's HEAD tracks the upstream's `main`
branch; the Dockerfile there may differ substantively from the
one used to build the *specific* image tag the chart pulls.
Real-world example: `apachepulsar/pulsar-all:4.0.10` was built
when `ARG ALPINE_VERSION=3.21` was the default; HEAD at audit
time has `ARG ALPINE_VERSION=3.23`. Reading HEAD would report
the wrong base.

For each cloned repo, fetch and check out the tag corresponding
to the image's version. Common tag conventions:

```bash
for tag in "$IMAGE_VERSION" "v$IMAGE_VERSION"; do
  git -C "$REPO_DIR" fetch --depth=1 origin "tag" "$tag" 2>/dev/null \
    && git -C "$REPO_DIR" checkout "$tag" --quiet \
    && break
done
```

If no tag matches (e.g. the image version doesn't track a Git
tag — common for vendor images whose tags are
`build-<sha>`-shaped), stay on HEAD and record
`tag-checkout: head-fallback` in the report so the user knows
the FROMs may not match the released image.

### Step 4: Locate the Dockerfile(s) for each image

Within each repo (cloned at the appropriate tag, or local),
find files named `Dockerfile`, `*.Dockerfile`, `Dockerfile.*`.
Pick the one that builds the specific image:

- **Path match.** Look for a directory whose name matches the
  image name component (e.g. image
  `foundationdb/fdb-kubernetes-monitor` → search for
  `**/fdb-kubernetes-monitor*/Dockerfile`).
- **Single-Dockerfile repo.** If exactly one Dockerfile exists at
  the repo root or a conventional location (`Dockerfile`,
  `images/Dockerfile`, `docker/Dockerfile`), use it.
- **Multiple candidates with no clean match.** Report all
  candidates and flag the image as `dockerfile-ambiguous`. Do
  not pick one arbitrarily.

**No Dockerfile at all? Look for a build-system manifest
instead.** Some upstream projects don't ship a Dockerfile —
they build container images directly via Nix `dockerTools`,
Google's `ko`, Bazel `rules_docker` / `rules_oci`, or Jib
(Java). The audit recognises this is not a gap but a different
build paradigm. Probe the cloned repo for build-system files
in this order:

| File | Build system | Where the base is declared |
| --- | --- | --- |
| `flake.nix`, `nix/build.nix` | Nix `dockerTools` | `nixpkgs.url` input pin + `dockerTools.buildImage` `fromImage` (often omitted → distroless-equivalent) |
| `.ko.yaml`, `KO_DEFAULTS` | ko | `defaultBaseImage:` (typically `cgr.dev/chainguard/static` or `gcr.io/distroless/static`) |
| `BUILD.bazel` referencing `oci_image` / `container_image` | Bazel rules_oci / rules_docker | `base = "..."` attribute on the `oci_image` / `container_image` target |
| `jib-maven-plugin` / `jib-gradle-plugin` config | Jib | `<from><image>` in pom.xml or `jib.from.image` in build.gradle |

If a build-system manifest is found, record
`dockerfile: <build-system>-built` (e.g. `nix-built`,
`ko-built`, `bazel-built`, `jib-built`) and proceed to step 5's
build-system-aware path. If no Dockerfile *and* no recognised
build-system file is present, the image is genuinely
`dockerfile-unknown` and step 5 falls back to
`base-inferred-from-labels`.

### Step 5: Parse FROM instructions

For each Dockerfile, extract every `FROM <image>[:tag] [AS …]`.
Multi-stage builds have several — collect them all, not just the
runtime stage.

Resolve `ARG`-based bases. A Dockerfile of the form:

```dockerfile
ARG GO_VERSION=1.22
ARG BASE_IMAGE=debian:bookworm-slim
FROM golang:${GO_VERSION} AS build
FROM ${BASE_IMAGE} AS runtime
```

should resolve to two concrete bases: `golang:1.22` and
`debian:bookworm-slim`. Use the in-file `ARG ... = <default>`
declarations as the source of truth — do not invent values for
ARGs with no default.

**Build-system-aware path** (Dockerfile-less images). When step
4 returned `<build-system>-built` instead of a Dockerfile path,
extract the base from the build manifest:

- **Nix `dockerTools`** — read the `nixpkgs.url` flake input
  (e.g. `nixos-25.11`) and any `fromImage` argument to
  `dockerTools.buildImage`. If `fromImage` is absent, the image
  is assembled from Nix packages with no traditional base; record
  the nixpkgs pin as the closest analog of an OS version and
  classify against the corresponding NixOS release.
- **ko** — read `defaultBaseImage:` from `.ko.yaml`. Common
  values resolve to Chainguard static (rolling-stable) or
  Google distroless (rolling-stable).
- **Bazel** — read the `base = "@some_image//image"` attribute
  on the `oci_image` / `container_image` target; resolve through
  the `WORKSPACE` / `MODULE.bazel` to the registry ref.
- **Jib** — read `<from><image>` (Maven) or `jib.from.image`
  (Gradle); defaults to `gcr.io/distroless/java` if unset.

Record the build-system pin (e.g. `nixpkgs:nixos-25.11`,
`ko:cgr.dev/chainguard/static:latest`,
`jib:gcr.io/distroless/java17:nonroot`) as the FROM-equivalent
in the report. If no explicit base is declared, record
`build-system-default` and classify as `rolling-stable` —
these systems default to vendor-managed minimal bases.

### Step 6: Classify each base by OS family and version

Map each resolved FROM to a `(family, version)` pair using the
table below. Tags lacking an obvious OS signal (e.g. plain
`golang:1.22`) resolve to the *runtime image's own current
default base* via a small lookup — flagged in the report so the
user knows the classification is one inference removed.

| Tag pattern | Family | Version |
| --- | --- | --- |
| `debian:bookworm*`, `debian:12*` | Debian | 12 |
| `debian:trixie*`, `debian:13*` | Debian | 13 |
| `debian:bullseye*`, `debian:11*` | Debian | 11 |
| `debian:sid*`, `debian:unstable*` | Debian | **rolling-dev** |
| `ubuntu:24.04`, `ubuntu:noble` | Ubuntu LTS | 24.04 |
| `ubuntu:22.04`, `ubuntu:jammy` | Ubuntu LTS | 22.04 |
| `ubuntu:20.04`, `ubuntu:focal` | Ubuntu LTS | 20.04 |
| `ubuntu:25.10`, `ubuntu:questing` | Ubuntu interim | 25.10 |
| `ubuntu:25.04`, `ubuntu:plucky` | Ubuntu interim | 25.04 |
| `ubuntu:24.10`, `ubuntu:oracular` | Ubuntu interim | 24.10 |
| `ubuntu:devel*`, `ubuntu:rolling*` | Ubuntu | **rolling-dev** |
| `alpine:3.23*` | Alpine | 3.23 |
| `alpine:3.22*` | Alpine | 3.22 |
| `alpine:3.21*` | Alpine | 3.21 |
| `alpine:3.<N>*` (3.18–3.20) | Alpine | 3.N |
| `alpine:edge*` | Alpine | **rolling-dev** |
| `redhat/ubi9*`, `rockylinux:9*` | RHEL-family | 9 |
| `redhat/ubi8*`, `rockylinux:8*` | RHEL-family | 8 |
| `gcr.io/distroless/*` | distroless | rolling-stable |
| `scratch` | (none) | n/a |

**Ubuntu LTS vs interim — two separate tracks.** Ubuntu ships a
new release every six months (`24.10`, `25.04`, `25.10`, …) but
only the `.04` of every even year (`20.04`, `22.04`, `24.04`,
`26.04`) is an LTS with 5+ years of standard support. Interim
releases get 9 months of support. The currency table compares
to the latest LTS; interim releases land in their own
classification (`non-lts-interim`) because they're neither
"current LTS" nor "one-behind LTS" in any meaningful sense.

**Distinguish `rolling-stable` from `rolling-dev`.** Both are
moving targets, but they carry different risk profiles:

- *rolling-stable* — distroless, Chainguard, `:latest` on
  vendor-managed runtime images. The vendor is rebuilding for
  the *current stable* OS major. Acceptable baseline; flag
  only if explicit version-pinning is a project policy.
- *rolling-dev* — `alpine:edge`, `debian:sid`,
  `debian:unstable`, `ubuntu:devel`. The image is built from
  the OS's *development* branch, not its stable release. A
  scarier baseline than "one-behind stable", because the next
  rebuild may pick up an unstable change. Flag explicitly.

Language-runtime images (`golang`, `python`, `openjdk`, `node`)
without an OS suffix carry an implicit base — record as
`base-inferred` with the inference noted (e.g. `node:22-alpine`
currently inherits Alpine 3.21).

### Step 7: Compare against the OS-currency table

The skill ships a small lookup of current stable OS releases.
**This table is the source of truth for the run** and is
versioned with the skill — keep it under review.

| Family | Current stable | Previous stable | Notes |
| --- | --- | --- | --- |
| Debian | trixie (13) | bookworm (12) | trixie became stable 2025-08-09 |
| Ubuntu LTS | 24.04 (noble) | 22.04 (jammy) | Next LTS 26.04 spring 2026 |
| Ubuntu interim | 25.10 (questing) | 25.04 (plucky) | 9-month support; not on the LTS comparison track |
| Alpine | 3.23 | 3.22 | New minor ~every 6 months; 3.23 stable since Nov 2025 |
| RHEL-family | 9 | 8 | RHEL 10 in preview |
| NixOS (for Nix-built images) | 25.11 | 25.05 | Twice-yearly stable; tracked here only to classify Nix-built images via `nixpkgs.url` |

Classification per base:

- `current` — matches current stable
- `one-behind` — matches previous stable
- `multi-behind` — older than previous stable
- `non-lts-interim` — Ubuntu interim release (`25.10`, `25.04`,
  `24.10`, etc.). Compared to the latest interim, not the LTS;
  flagged because it's a 9-month-support track, not a 5-year one.
- `rolling-stable` — distroless / `scratch` / Chainguard /
  vendor-`:latest` (rebuilds against current stable). Also
  covers Dockerfile-less images whose build system
  (`nix-built`, `ko-built`, `bazel-built`, `jib-built`)
  defaults to a vendor-managed minimal base.
- `rolling-dev` — `alpine:edge`, `debian:sid`,
  `debian:unstable`, `ubuntu:devel` (rebuilds against the
  OS's *development* branch, not its stable release)
- `unsupported` — past the family's EOL (Debian 10, Ubuntu 18.04,
  Alpine ≤ 3.17, RHEL 7)

For `<build-system>-built` images, the comparison runs against
the build system's pin instead of an OS tag — e.g. a
`nix-built` image with `nixpkgs.url = nixos-25.11` is
classified `current` (NixOS 25.11 is the current stable); a
`nixpkgs.url = nixos-25.05` pin would be `one-behind`.

If the table itself looks more than ~6 months stale at run time,
the report's header carries a `table-stale` warning.

### Step 8: Emit the tree report

The report has two views over the same data:

- **ASCII tree** for humans, grouped by owning chart → image →
  Dockerfile → FROM, with status markers (`✅ ⚠️ ❌ ⚪`).
- **JSON** for machines, same data, with the resolution-signal
  trail for each image.

A run terminates 0 only when the inventory parsed cleanly and
every image landed in one of the resolution buckets. Findings
themselves (stale bases, unsupported releases) do not fail the
run — they are the output.

## Key Concepts

| Term | Meaning |
| --- | --- |
| Transitive base | The `FROM` image of an image referenced by a chart; one layer below the chart's image-pin. |
| Owning chart | The chart whose template renders a given image (main chart or subchart alias). |
| Resolution signal | The mechanism used to map an image to its source Dockerfile: `local`, `chart-sources`, `slug-heuristic`, `oci-label`, `base-inferred-from-labels`, `source-unknown`. |
| OS-currency table | The skill's static lookup of current stable OS releases. Authoritative for a given skill version; updated as new majors land. |
| `base-inferred` | A language-runtime image (`golang:1.22`) whose underlying OS base is recorded by inference rather than read directly from a `FROM debian:...` line. |
| `base-inferred-from-labels` | Fallback when the Dockerfile is unfindable: the final-stage base identified from labels inherited via `crane config`. Reliable for the runtime layer only; cannot recover build-stage bases. |
| `dockerfile-ambiguous` | An image whose source repo contains multiple Dockerfile candidates with no clean path-name match, or whose source repo is unreachable. |
| Crossplane package | An OCI artifact installed via a `Provider`, `Function`, or `Configuration` resource under `pkg.crossplane.io`. Carried as `.spec.package` rather than `image:`; resolves to a controller image typically built in a separate `github.com/<vendor>/provider-*` repo. |
| `<build-system>-built` | An image produced without a Dockerfile, via Nix `dockerTools`, ko, Bazel rules_oci, or Jib. The "base" is read from the build manifest (`flake.nix`, `.ko.yaml`, `BUILD.bazel`, Jib config) instead of a `FROM` line. Common in vendor-Go projects like Crossplane core. |
| Ubuntu LTS vs interim | LTS releases (`.04` of even years, e.g. 22.04 / 24.04 / 26.04) get 5+ years of standard support; interim releases (`24.10` / `25.04` / `25.10`) get 9 months. The two tracks are compared separately; an image on an interim release is `non-lts-interim`, not `one-behind`. |
| `rolling-stable` vs `rolling-dev` | Two flavours of moving-target tag. Stable rebuilds against the current stable OS release (distroless, Chainguard, vendor-`:latest`); dev rebuilds against the OS's development branch (`alpine:edge`, `debian:sid`, `ubuntu:devel`). The latter is riskier. |
| `tag-checkout: head-fallback` | The skill couldn't find a Git tag matching the image's version, so the Dockerfile was read from HEAD. FROMs may not match the released image. |

## Tools and Systems

- **helm** — render the chart.
- **git** — shallow-clone upstream source repos.
- **crane** — inspect OCI image labels when present (rarely
  useful for source-URL lookup; very useful for the
  `base-inferred-from-labels` fallback).
- **python3 + PyYAML** — parse rendered YAML, Dockerfiles, ARG
  resolution.
- **jq** — emit and consume the structured report.

## Common Scenarios

**Auditing a vendored chart whose upstream is moving.** You
vendored a chart six months ago because the upstream doesn't
publish a Helm repo. You want to know which of the images its
Dockerfiles build are now on an old major OS release. The
chart's `Chart.yaml` carries a `sources:` URL pointing at the
upstream Git repo, so step 2 resolves cleanly; the audit
surfaces a Dockerfile that's still on Debian bookworm when
trixie is current. The report's "follow-up" hint suggests
bumping that specific Dockerfile when you next sync the vendored
chart. See [examples/queenswood.md](./examples/queenswood.md)
for the queenswood-chart walkthrough.

**Locally-built service images on a stale base.** Your chart's
own services build off `infra/docker/service/Dockerfile`; that
Dockerfile is two years old and still on `debian:bullseye-slim`.
The skill resolves these via the local-Dockerfile signal (no
clone needed), parses `bullseye`, classifies as `unsupported`
(Debian 11's standard support ended 2024-08-14), and the report
foregrounds it as a high-priority finding.

## Output Format

The skill emits two artifacts in the working directory:

1. `base-audit-tree.txt` — ASCII tree, suitable for paste into
   a PR description or a SECURITY.md follow-up.
2. `base-audit.json` — structured findings, one entry per
   `(image, dockerfile, from-line)` triple, with the resolution
   signal and OS classification.

## Hard Constraints

- **Read-only.** Never modify charts, Dockerfiles, or upstream
  repos. The skill is an audit, not a remediation.
- **Always record the resolution signal.** Every image in the
  report carries `resolution-signal: local | chart-sources |
  slug-heuristic | oci-label | base-inferred-from-labels |
  source-unknown`. No silent guesses.
- **Always check out the release tag** matching the image's
  version before reading a cloned Dockerfile. Reading HEAD will
  silently report the *current dev* base, not the base that
  built the image the chart pulls. If no matching tag exists,
  record `tag-checkout: head-fallback` in the report — do not
  hide the discrepancy.
- **Multi-stage Dockerfiles report all FROMs**, not just the
  final stage. A build stage on a stale base is still a stale
  base in the dependency graph.
- **ARGs without defaults are not invented.** If
  `ARG BASE_IMAGE` appears without `= <default>`, the FROM
  resolves to `arg-undefined` and that entry is flagged in the
  report — the skill does not pick a value.
- **`dockerfile-ambiguous` images are not reduced.** Multiple
  Dockerfile candidates with no clean match are all listed; the
  skill does not arbitrarily pick one.
- **OS-currency table is authoritative for the run.** It ships
  with the skill version and is the source of truth for
  current/previous/EOL classifications. The table's last-edited
  date is included in the report header.
