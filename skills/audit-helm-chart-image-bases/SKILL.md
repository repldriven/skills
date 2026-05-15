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

Use when you need to know *which* transitive Dockerfiles in a Helm
chart's image tree are still on a stale base OS — security-driven OS
refreshes, vendored-chart drift checks, CVE-impact enumeration, or
baselining before a fresh-base refactor.

**Do not use** for: bumping image tags on already-published hardened
images (use Renovate / Dependabot), switching to Chainguard /
distroless bases (that's base *replacement*, not currency), or
emitting values overrides without rebuilding (this skill is
read-only).

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
  the current repository (e.g. `ghcr.io/repldriven` for queenswood).
  When matched, resolution skips upstream lookup and reads the
  local Dockerfile directly.
- **org-translations** (optional): map of Docker Hub org names to
  GitHub org names, for the slug-heuristic resolver. Ships with
  built-in defaults for common cases (`apachepulsar` →
  `apache`/`pulsar`, `foundationdb` → `FoundationDB`).

## Workflow

### Step 0: Render and inventory

Render the chart and extract every image reference. Use a YAML-aware
parse (not a regex sweep), discriminating by `kind` + `apiVersion`,
so Crossplane packages (`.spec.package` on `pkg.crossplane.io`
resources) are caught alongside `image:` keys without false positives
from unrelated `package:` strings (e.g. an npm `package.json` in a
ConfigMap).

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

**No Dockerfile at all?** Probe for a build-system manifest
(`flake.nix`, `.ko.yaml`, `BUILD.bazel`, Jib config) before declaring
the image source-unknown. Record `dockerfile: <system>-built` (e.g.
`nix-built`) on a hit, then continue to Step 5's build-system-aware
path. See [references/build-systems.md](./references/build-systems.md)
for the manifest table and per-system base-extraction details.

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

**Build-system-aware path** (Dockerfile-less images). When Step 4
returned `<build-system>-built`, extract the base from the build
manifest instead — see
[references/build-systems.md](./references/build-systems.md) for
per-system instructions. Record the build-system pin (e.g.
`nixpkgs:nixos-25.11`, `ko:cgr.dev/chainguard/static:latest`) as the
FROM-equivalent. If no explicit base is declared, record
`build-system-default` and classify as `rolling-stable`.

### Step 6: Classify each base by OS family and version

Map each FROM to `(family, version)` using the tag-pattern table in
[references/os-classification.md](./references/os-classification.md).
Key load-bearing distinctions the reference enforces:

- **Ubuntu LTS vs interim** are separate tracks. Interim releases
  (`24.10`, `25.04`, `25.10`) classify as `non-lts-interim`, **not**
  `one-behind` — the support windows are 9 months vs 5+ years.
- **`rolling-stable` vs `rolling-dev`** are separate buckets.
  Distroless / Chainguard / vendor-`:latest` are stable-rolling;
  `alpine:edge` / `debian:sid` / `ubuntu:devel` are dev-rolling and
  riskier. Never collapse them to a single `rolling` bucket.
- **Language-runtime images** (`golang`, `python`, `node`) without an
  OS suffix carry an implicit base — record as `base-inferred` with
  the inference noted.

### Step 7: Compare against the OS-currency table

Each base is compared against the skill's versioned currency lookup
in
[references/os-currency-table.md](./references/os-currency-table.md).
The classification labels are: `current`, `one-behind`,
`multi-behind`, `non-lts-interim`, `rolling-stable`, `rolling-dev`,
`unsupported`. For `<build-system>-built` images, comparison runs
against the build system's pin (e.g. `nixpkgs.url`) rather than an OS
tag. If the table itself looks more than ~6 months stale at run time,
the report header carries a `table-stale` warning.

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

## Tools and Systems

- **helm** — render the chart.
- **git** — shallow-clone upstream source repos.
- **crane** — inspect OCI image labels when present (rarely
  useful for source-URL lookup; very useful for the
  `base-inferred-from-labels` fallback).
- **python3 + PyYAML** — parse rendered YAML, Dockerfiles, ARG
  resolution.
- **jq** — emit and consume the structured report.

See [examples/queenswood.md](./examples/queenswood.md) for an
end-to-end worked example covering vendored-chart auditing,
local-Dockerfile resolution, and the `base-inferred-from-labels`
fallback.

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
- **Always record the resolution signal.** Every image carries a
  signal from the closed set defined in Step 2. No silent guesses.
- **Always check out the release tag** before reading a cloned
  Dockerfile (see Step 3.5); record `tag-checkout: head-fallback`
  rather than silently reading HEAD.
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
