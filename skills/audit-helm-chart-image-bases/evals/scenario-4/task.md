# Classify a batch of Dockerfile FROM lines against an OS-currency table

## Problem / Feature Description

A platform security review has assembled a batch of FROM lines
pulled from various Dockerfiles in the dependency tree of a single
Helm chart. The reviewer wants a single classification report
that distinguishes:

- bases on the **current stable** of their OS family
- bases on the **previous stable** (one-behind)
- bases on the OS family's **development branch** (alpine:edge,
  debian:sid, ubuntu:devel) — which are riskier than "one-behind"
  because the next rebuild may pick up an unreleased change
- bases that are **vendor-managed rolling** images (distroless,
  Chainguard) which rebuild *against the current stable* and are
  acceptable as a rolling baseline
- bases on Ubuntu's **interim releases** (`24.10`, `25.04`,
  `25.10`), which are neither LTS-current nor LTS-one-behind but
  a separate 9-month-support track

The reviewer is explicit that lumping all moving-target tags into
a single "rolling" bucket would mask the difference between a
distroless image (low risk, vendor-managed) and an `alpine:edge`
image (genuinely tracking unstable Alpine).

## Output Specification

Produce one file in the working directory:

- `classifications.json` — JSON array; one object per FROM line
  in the input, in the same order they appear. Each object must
  carry:
  - `from`: the FROM line verbatim
  - `os_family`: one of `debian`, `ubuntu-lts`, `ubuntu-interim`,
    `alpine`, `rhel-family`, `distroless`, `none` (for scratch),
    or `unknown`
  - `os_version`: the specific version (e.g. `12`, `24.04`, `3.23`,
    `9`, `edge`) or `null` for scratch/unknown
  - `status`: one of `current`, `one-behind`, `multi-behind`,
    `non-lts-interim`, `rolling-stable`, `rolling-dev`,
    `unsupported`

Use the following currency lookup (authoritative for this run):

```
debian:        current trixie (13), previous bookworm (12)
ubuntu-lts:    current 24.04 noble, previous 22.04 jammy
ubuntu-interim: latest 25.10 questing
alpine:        current 3.23, previous 3.22
rhel-family:   current 9, previous 8
```

## Input Files

=============== FILE: inputs/froms.txt ===============
FROM alpine:edge
FROM gcr.io/distroless/static-debian13:nonroot
FROM cgr.dev/chainguard/static:latest
FROM ubuntu:25.10
FROM ubuntu:22.04
FROM debian:bookworm-slim
FROM debian:trixie-slim
FROM alpine:3.22
FROM debian:sid
FROM rockylinux:9
FROM scratch
FROM ubuntu:24.04
