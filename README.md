# repldriven/skills

Tessl tile of platform skills authored under the
[`repldriven`](https://github.com/repldriven) GitHub org.

One tile, many skills. Skills accumulate under `skills/`; each
ships its own `SKILL.md`, `examples/`, and `evals/` per the
Tessl convention.

## Skills

- **[audit-helm-chart-image-bases](skills/audit-helm-chart-image-bases/SKILL.md)**
  — Audit the transitive Dockerfile base images of every Docker
  image a Helm chart pulls. Resolves each image back to its
  source Dockerfile (Chart.yaml sources, local Dockerfiles,
  slug heuristics, inherited labels, or build-system manifests
  for Dockerfile-less projects) and reports outdated base OS
  releases.

## Companion tools

Deterministic command-line tooling that consumes skill outputs
lives in [`repldriven/tools`](https://github.com/repldriven/tools).
The `chart-supply-refresh` CLI there consumes the JSON output of
`audit-helm-chart-image-bases` and forks stale-base Dockerfiles
onto current OS images.

## Develop

```bash
nix develop           # enters dev shell with tessl, helm, crane, kubectl, ...
```

## Tile evaluation

Per-skill eval scenarios live under each skill's `evals/`. See
the Tessl docs for `tessl eval run <tile>` once the tile is
published to a `git` source.

## License

Apache-2.0 — see [LICENSE](LICENSE).
