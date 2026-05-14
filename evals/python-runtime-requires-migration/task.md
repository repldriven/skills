# Classify a Python-runtime Debian-major bump

## Problem / Feature Description

An audit has flagged a Python runtime stage as `multi-behind`:
the image builds on `python:3.11-slim-bullseye` (Debian 11), two
behind the current Debian stable (trixie / 13). A mechanical
one-step bump would move it to `python:3.11-slim-bookworm`
(Debian 12).

You're asked to advise on whether this bump is safe to apply
mechanically. The workload installs Python packages from
`requirements.txt` via `pip install`, including some packages
that ship binary wheels (e.g. `cryptography`, `numpy`,
`psycopg2-binary`).

Use the rubric from the skill. Cite the named indicators.

## Output Specification

Produce one file in the working directory:

- `advice.md` — markdown with one section for this FROM, matching
  the SKILL's output schema.

## Input Files

=============== FILE: inputs/base-audit.json ===============
{
  "report": {
    "generated-at": "2026-05-14T17:00:00Z",
    "os-currency-table-last-edited": "2026-05-14",
    "table-stale": false
  },
  "findings": [
    {
      "owning-chart": "api",
      "image": "registry.example.com/team/api:1.4.2",
      "resolution-signal": "local",
      "source-repo": null,
      "tag-checkout": null,
      "dockerfile": "infra/docker/api/Dockerfile",
      "froms": [
        {"stage": "runtime", "from": "python:3.11-slim-bullseye",
         "os-family": "Debian", "os-version": "11", "currency": "multi-behind"}
      ]
    }
  ]
}

=============== FILE: inputs/context.md ===============
The runtime image installs Python deps via `pip install -r
requirements.txt`. The requirements include:

  - cryptography (binary wheel; links against system OpenSSL)
  - numpy (binary wheel; links against system glibc, BLAS)
  - psycopg2-binary (binary wheel; links against system libpq)
  - flask, jinja2, requests (pure-Python)

The image runs an async HTTP API; no shell-out to system tools.
The runtime stage's FROM is the only stage (single-stage
Dockerfile).
