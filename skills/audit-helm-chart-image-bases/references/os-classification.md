# Tag-pattern → OS family/version classification (Step 6)

Map each resolved FROM to a `(family, version)` pair using this table.
Tags lacking an obvious OS signal (e.g. plain `golang:1.22`) resolve to
the *runtime image's own current default base* via a small lookup —
flagged in the report so the user knows the classification is one
inference removed.

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

## Ubuntu LTS vs interim — two separate tracks

Ubuntu ships a new release every six months (`24.10`, `25.04`,
`25.10`, …) but only the `.04` of every even year (`20.04`, `22.04`,
`24.04`, `26.04`) is an LTS with 5+ years of standard support. Interim
releases get 9 months of support. The currency table compares to the
latest LTS; interim releases land in their own classification
(`non-lts-interim`) because they're neither "current LTS" nor
"one-behind LTS" in any meaningful sense.

## Distinguish `rolling-stable` from `rolling-dev`

Both are moving targets, but they carry different risk profiles:

- **`rolling-stable`** — distroless, Chainguard, `:latest` on
  vendor-managed runtime images. The vendor is rebuilding for the
  *current stable* OS major. Acceptable baseline; flag only if explicit
  version-pinning is a project policy.
- **`rolling-dev`** — `alpine:edge`, `debian:sid`, `debian:unstable`,
  `ubuntu:devel`. The image is built from the OS's *development*
  branch, not its stable release. A scarier baseline than "one-behind
  stable", because the next rebuild may pick up an unstable change.
  Flag explicitly.

## Language-runtime images

Language-runtime images (`golang`, `python`, `openjdk`, `node`) without
an OS suffix carry an implicit base — record as `base-inferred` with
the inference noted (e.g. `node:22-alpine` currently inherits
Alpine 3.21).
