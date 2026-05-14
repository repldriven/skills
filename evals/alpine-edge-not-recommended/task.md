# Classify an alpine:edge finding

## Problem / Feature Description

An audit has flagged a utility image as `rolling-dev` because its
Dockerfile pins `FROM alpine:edge`. The audit's `rolling-dev`
classification distinguishes this from `rolling-stable`
(distroless, Chainguard, vendor-`:latest`) — `alpine:edge` is the
*development* branch of Alpine, not a vendor-managed minimal
base.

The audit didn't suggest a target (it doesn't know what stable
release to pin to). You're asked to advise on what to do.

Apply the rubric. Cite the named indicators. The proposed target
in your advice should be the current Alpine stable per the
audit's currency table.

## Output Specification

Produce one file in the working directory:

- `advice.md` — markdown for this single FROM.

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
      "owning-chart": "queenswood",
      "image": "alpine/k8s:1.30.14",
      "resolution-signal": "slug-heuristic",
      "source-repo": "https://github.com/alpine-docker/k8s",
      "tag-checkout": "head-fallback",
      "dockerfile": "Dockerfile",
      "froms": [
        {"stage": "stage-0", "from": "alpine:edge",
         "os-family": "Alpine", "os-version": "edge", "currency": "rolling-dev"}
      ]
    }
  ]
}

=============== FILE: inputs/currency-table.md ===============
Current Alpine stable: 3.23 (since 2025-11).
Previous Alpine stable: 3.22.
