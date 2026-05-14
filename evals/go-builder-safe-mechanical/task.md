# Classify a Go-builder Debian-major bump

## Problem / Feature Description

An `audit-helm-chart-image-bases` run has flagged a Go builder
stage as `one-behind`: it builds on `golang:1.25.8-bookworm`
(Debian 12), and the current stable is Debian 13 (trixie). The
audit's suggested target is `golang:1.25.8-trixie`.

You're asked to advise on whether this bump is safe to apply
mechanically (i.e. a downstream tool can rewrite the Dockerfile's
FROM line and rebuild without human review) or whether it needs
migration work.

Use the rubric from the skill. Cite the named indicators that
justify your classification. Do **not** invent CVE references.

## Output Specification

Produce one file in the working directory:

- `advice.md` — markdown with one section for this single FROM,
  matching the SKILL's output schema (Classification, Before,
  After, Indicators, Recommended action, Notes).

## Input Files

The following files are provided as inputs. Extract them before
beginning.

=============== FILE: inputs/base-audit.json ===============
{
  "report": {
    "generated-at": "2026-05-14T17:00:00Z",
    "os-currency-table-last-edited": "2026-05-14",
    "table-stale": false
  },
  "findings": [
    {
      "owning-chart": "fdbOperator",
      "image": "foundationdb/fdb-kubernetes-operator:v2.27.0",
      "resolution-signal": "chart-sources",
      "source-repo": "https://github.com/FoundationDB/fdb-kubernetes-operator",
      "tag-checkout": "v2.27.0",
      "dockerfile": "Dockerfile",
      "froms": [
        {"stage": "builder", "from": "golang:1.25.8-bookworm",
         "os-family": "Debian", "os-version": "12", "currency": "one-behind"}
      ]
    }
  ]
}

=============== FILE: inputs/context.md ===============
The fdb-kubernetes-operator builder stage compiles the operator
binary with `CGO_ENABLED=0`. The result is a statically linked
Go binary that the runtime stage copies via `COPY --from=builder`.
The runtime stage's FROM is separate (not in scope for this
scenario) and is already on current.
