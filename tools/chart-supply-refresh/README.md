# chart-supply-refresh

Fork a Helm chart's transitive Dockerfiles onto current base OS
images and emit a CI workflow that rebuilds them on a cron, so the
chart's image supply chain stays current without waiting for
upstream maintainer cycles.

Companion to the `audit-helm-chart-image-bases` skill: this tool
consumes that skill's `base-audit.json` output.

## Install

In the repo's Nix dev shell:

```bash
nix develop
chart-supply-refresh --help
```

## Usage

```bash
chart-supply-refresh \
  --chart ./infra/helm/queenswood \
  --audit ./base-audit.json \
  --target-registry ghcr.io/repldriven \
  --allow-bumps safe \
  --output ./fork
```

Produces `./fork/` with:

- `chart/` — copy of the input chart, with `values.yaml` rewritten
  to point at the rebuilt-image registry for every image whose
  Dockerfile was patched.
- `dockerfiles/<image>/Dockerfile` — patched Dockerfiles with
  bumped FROM lines.
- `.github/workflows/rebuild.yml` — cron-triggered rebuild
  workflow.
- `refresh-plan.json` — machine-readable manifest of what was
  changed and why.

## `--allow-bumps`

- `safe` (default) — only apply bumps the audit classifies as
  current-stable, mechanical replacements (e.g. `bookworm` →
  `trixie` for a Go builder). Stale-but-unsafe images are left
  alone with an inline note.
- `all` — apply every bump the audit identifies. Use only when
  you've separately verified that the bumps don't break the
  build.

## License

Apache-2.0.
