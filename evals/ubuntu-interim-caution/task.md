# Classify a bump targeting an Ubuntu interim release

## Problem / Feature Description

An audit has flagged a runtime image on `ubuntu:24.04` as
`current` (LTS), but a developer has *separately* proposed
bumping to `ubuntu:25.04` (the latest interim release) to pick
up a newer GCC available in the interim repos.

You're asked to advise on this **operator-proposed override**.
Note the audit didn't suggest this target — the developer
overrode the obvious one-step path (which would be "stay on
24.04 LTS"). Use the user-provided target.

Apply the rubric. Cite the named indicators.

## Output Specification

Produce one file in the working directory:

- `advice.md` — markdown for this single FROM, classifying the
  proposed (operator-overridden) bump.

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
      "owning-chart": "build-cache",
      "image": "registry.example.com/team/build-cache:0.5.0",
      "resolution-signal": "local",
      "source-repo": null,
      "tag-checkout": null,
      "dockerfile": "infra/docker/build-cache/Dockerfile",
      "froms": [
        {"stage": "runtime", "from": "ubuntu:24.04",
         "os-family": "Ubuntu LTS", "os-version": "24.04", "currency": "current"}
      ]
    }
  ]
}

=============== FILE: inputs/proposed-target.md ===============
Override: bump runtime FROM to `ubuntu:25.04` (plucky, interim).
Reason given by the developer: needs GCC 14 from the interim
repos for a recent C++ workload feature.

=============== FILE: inputs/context.md ===============
The build-cache image is used by an internal CI pool. It runs a
small C++ tool that wraps `g++` invocations.

The team currently rebuilds the image every 2-3 months when
unrelated CI pieces change.
