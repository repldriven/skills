# Detection chain (Step 2)

For each ImageRef, walk these signals in strict order and stop at
the first authoritative hit. Record which signal produced the
result.

| # | Signal | Tool | When it works | When it doesn't |
| --- | --- | --- | --- | --- |
| 1 | **Cosign attestation / SBOM** | `cosign download attestation`, parse SPDX or CycloneDX | Upstream pushed an attached SBOM (Chainguard, Wolfi, modern Bitnami, increasingly common) | No SBOM attached |
| 2 | **OCI labels** | `crane config <image>` → read `org.opencontainers.image.base.name` and `.base.digest` | Upstream sets the base-name label (Red Hat UBI does, vendor JDKs often do) | Labels missing — common in non-vendor images |
| 3 | **Syft scan** | `syft <image>` → reads `/etc/os-release` and package-manager state | Image has a real OS layer with package metadata | Distroless / scratch images strip these files |
| 4 | **Distroless / scratch detector** | Check if `/etc/os-release` is absent in the image filesystem | Always works as a fallback for FROM scratch / distroless | n/a — this is the terminal branch |

If **all** of (1), (2), (3) fail and (4) also doesn't apply (the
image has no OS layer but also isn't clearly distroless/scratch),
record `detection-failed`. This is rare in practice — Syft's
fallback heuristics catch most images that have any filesystem
content.

## Recorded signal values

Always record exactly one of these values per ImageRef in the
emitted graph (`detection_signals` field):

- `cosign-attestation` — authoritative; SBOM specifies the base
  explicitly.
- `oci-label` — authoritative; upstream declared the base via
  OCI image labels.
- `syft-scan` — Syft identified the OS distribution from
  filesystem inspection.
- `distroless-or-scratch` — no OS layer; image is built `FROM
  scratch` or from a distroless variant. Classification proceeds
  with `OSDistribution: { id: scratch }` or
  `{ id: distroless, family: <best-guess from image name> }`.
- `detection-failed` — true unknown. The graph entry is present
  but tier classification can't proceed; the report flags it for
  manual review.

## Why strict order matters

SBOMs are authoritative because the upstream is asserting *what
the image contains*. OCI labels are authoritative because the
upstream is asserting *what the base was*. Syft is heuristic
because it reverse-engineers from artefacts in the filesystem
(which can be wrong if the image is mid-build, multi-stage with
overlapping layers, or deliberately stripped). The order
prioritises upstream assertions over our inference.

When two signals disagree (e.g. SBOM says Alpine, Syft says
Debian), trust the SBOM and note the conflict in the report. This
is unusual but happens when an SBOM is stale relative to the
image rebuild.
