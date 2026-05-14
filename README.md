# repldriven/skills

Tessl tile of platform skills authored under the
[`repldriven`](https://github.com/repldriven) GitHub org, plus
companion deterministic tools.

## Skills

- **[audit-helm-chart-image-bases](skills/audit-helm-chart-image-bases/SKILL.md)**
  — Audit the transitive Dockerfile base images of every Docker
  image a Helm chart pulls. Resolves each image back to its
  source Dockerfile (Chart.yaml sources, local Dockerfiles,
  slug heuristics, inherited labels, or build-system manifests
  for Dockerfile-less projects) and reports outdated base OS
  releases.

## Tools

- **chart-supply-refresh** — given an `audit-helm-chart-image-bases`
  report, fork the chart's stale-base Dockerfiles onto current OS
  images and emit a GitHub Actions cron workflow that rebuilds
  them. Pure deterministic CLI; no LLM in the loop. Organised as
  a Polylith workspace under `components/` + `bases/` (Poetry).

## Layout

```
components/chart_supply_refresh/<brick>/core.py    chart-supply-refresh components
bases/chart_supply_refresh/cli/core.py             CLI base composing the components
test/components/...  test/bases/...                tests mirroring brick layout
skills/<skill-name>/                               Tessl skills (markdown-driven)
pyproject.toml                                     Poetry workspace + Polylith bricks
workspace.toml                                     Polylith workspace config
flake.nix                                          Nix dev shell (helm/crane/tessl/poetry/...)
```

## Develop

```bash
nix develop           # enters dev shell with poetry, helm, crane, tessl, ...
poetry install        # install deps + register components
poetry run pytest     # 36 tests
poetry run chart-supply-refresh --help
```

## Tile evaluation

Per-skill eval scenarios live under each skill's `evals/`. See
the Tessl docs for `tessl eval run <tile>` once the tile is
published to a `git` source.

## License

Apache-2.0 — see [LICENSE](LICENSE).
