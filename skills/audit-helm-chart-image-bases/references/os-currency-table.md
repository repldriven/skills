# OS-currency table (Step 7)

The skill ships a small lookup of current stable OS releases. **This
table is the source of truth for the run** and is versioned with the
skill — keep it under review.

| Family | Current stable | Previous stable | Notes |
| --- | --- | --- | --- |
| Debian | trixie (13) | bookworm (12) | trixie became stable 2025-08-09 |
| Ubuntu LTS | 24.04 (noble) | 22.04 (jammy) | Next LTS 26.04 spring 2026 |
| Ubuntu interim | 25.10 (questing) | 25.04 (plucky) | 9-month support; not on the LTS comparison track |
| Alpine | 3.23 | 3.22 | New minor ~every 6 months; 3.23 stable since Nov 2025 |
| RHEL-family | 9 | 8 | RHEL 10 in preview |
| NixOS (for Nix-built images) | 25.11 | 25.05 | Twice-yearly stable; tracked here only to classify Nix-built images via `nixpkgs.url` |

## Classification per base

- `current` — matches current stable
- `one-behind` — matches previous stable
- `multi-behind` — older than previous stable
- `non-lts-interim` — Ubuntu interim release (`25.10`, `25.04`,
  `24.10`, etc.). Compared to the latest interim, not the LTS;
  flagged because it's a 9-month-support track, not a 5-year one.
- `rolling-stable` — distroless / `scratch` / Chainguard /
  vendor-`:latest` (rebuilds against current stable). Also covers
  Dockerfile-less images whose build system (`nix-built`, `ko-built`,
  `bazel-built`, `jib-built`) defaults to a vendor-managed minimal
  base.
- `rolling-dev` — `alpine:edge`, `debian:sid`, `debian:unstable`,
  `ubuntu:devel` (rebuilds against the OS's *development* branch, not
  its stable release)
- `unsupported` — past the family's EOL (Debian 10, Ubuntu 18.04,
  Alpine ≤ 3.17, RHEL 7)

## Build-system-built images

For `<build-system>-built` images, the comparison runs against the
build system's pin instead of an OS tag — e.g. a `nix-built` image
with `nixpkgs.url = nixos-25.11` is classified `current` (NixOS 25.11
is the current stable); a `nixpkgs.url = nixos-25.05` pin would be
`one-behind`.

## Staleness warning

If this table itself looks more than ~6 months stale at run time, the
report's header carries a `table-stale` warning.
