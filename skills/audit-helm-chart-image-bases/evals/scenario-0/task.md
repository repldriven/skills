# Audit the base images of a tiny vendored Helm chart

## Problem / Feature Description

A platform team has vendored a small Helm chart that wraps a single
upstream subchart. Their security team has just published a memo
saying every Dockerfile in the dependency tree of any production
Helm release needs to be reviewed for stale base-OS releases — not
just the *image tags*, but the underlying OS the Dockerfile builds
on. Pinning a newer image tag isn't enough; if the upstream's
Dockerfile is still on a discontinued OS, the rebuild will fail
or re-introduce the issue.

The chart in this task is a minimal sample, but the workflow needs
to be the same as for production charts: walk from chart → image →
upstream source repo → Dockerfile → FROM lines, then classify each
FROM against current vs previous OS releases. The output must be
checkable by a non-Helm-fluent reader (so a tree-shaped text file
is essential) and also machine-readable for the team's compliance
report (so a JSON output too).

The vendored chart depends on `foundationdb/fdb-kubernetes-operator`
v2.27.0. The chart's `sources:` field points at the upstream Git
repo. The agent will need network access to clone the repo, check
out the release tag corresponding to the pulled image, and read
the Dockerfile at that tag — **not** at HEAD, because the
Dockerfile drifts between releases.

## Output Specification

Produce two files in the working directory:

1. `base-audit-tree.txt` — human-readable ASCII tree showing
   chart → image → Dockerfile → FROMs with status markers.
2. `base-audit.json` — structured findings, machine-readable.

The report header must include the OS-currency table's
last-edited date.

## Input Files

The following files are provided as inputs. Extract them before
beginning.

=============== FILE: inputs/Chart.yaml ===============
apiVersion: v2
name: tiny-fdb
description: Minimal sample chart that wraps fdb-operator as a vendored subchart.
type: application
version: 0.1.0
appVersion: "0.1.0"

dependencies:
  - name: fdb-operator
    version: "0.3.0"
    repository: "file://charts/fdb-operator"

=============== FILE: inputs/charts/fdb-operator/Chart.yaml ===============
apiVersion: v2
name: fdb-operator
description: Vendored copy of FoundationDB's fdb-operator chart.
type: application
version: 0.3.0
appVersion: "v2.27.0"
sources:
  - https://github.com/FoundationDB/fdb-kubernetes-operator/tree/main/charts/fdb-operator

=============== FILE: inputs/charts/fdb-operator/values.yaml ===============
image:
  repository: foundationdb/fdb-kubernetes-operator
  tag: v2.27.0
  pullPolicy: IfNotPresent

=============== FILE: inputs/charts/fdb-operator/templates/deployment.yaml ===============
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fdb-kubernetes-operator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fdb-kubernetes-operator
  template:
    metadata:
      labels:
        app: fdb-kubernetes-operator
    spec:
      containers:
        - name: manager
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"

=============== FILE: inputs/templates/wrapper.yaml ===============
# Minimal main-chart template so `helm template` produces output
# beyond the subchart. Empty Deployment; the actual image comes
# from the fdb-operator subchart.
{}
