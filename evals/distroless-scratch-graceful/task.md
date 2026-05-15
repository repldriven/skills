# Handle distroless and FROM scratch gracefully

## Problem / Feature Description

A platform team is reviewing a chart whose images include two
"no OS layer" cases:

- `gcr.io/distroless/static-debian13:nonroot` — Google's
  distroless static image. Has *some* file content but no
  `/etc/os-release`; the agent's `syft` scan returns no OS
  identification.
- A user-built image `ghcr.io/example/static-binary:1.0` whose
  Dockerfile starts with `FROM scratch` and copies a single
  static binary. The image is essentially a tar of one file.

Both are valid production patterns. The skill must classify
them correctly without crashing. The detection signal is
`distroless-or-scratch`; the license tier is `n/a` (there is no
OS to license); the escape recommendation is `no-escape-needed`.

The skill MUST NOT mark these as `detection-failed` — that's
reserved for true unknowns where the chain ran but couldn't
determine anything.

## Output Specification

Produce two files in the working directory:

- `image-graph.json` — must contain entries for both images.
- `image-graph.md`

## Input Files

=============== FILE: inputs/Chart.yaml ===============
apiVersion: v2
name: tiny-static-app
description: Minimal chart using distroless + FROM scratch images.
type: application
version: 0.1.0
appVersion: "0.1.0"

=============== FILE: inputs/templates/distroless.yaml ===============
apiVersion: apps/v1
kind: Deployment
metadata:
  name: distroless-svc
spec:
  replicas: 1
  selector:
    matchLabels: { app: distroless-svc }
  template:
    metadata:
      labels: { app: distroless-svc }
    spec:
      containers:
        - name: app
          image: "gcr.io/distroless/static-debian13:nonroot"

=============== FILE: inputs/templates/scratch.yaml ===============
apiVersion: apps/v1
kind: Deployment
metadata:
  name: static-svc
spec:
  replicas: 1
  selector:
    matchLabels: { app: static-svc }
  template:
    metadata:
      labels: { app: static-svc }
    spec:
      containers:
        - name: app
          image: "ghcr.io/example/static-binary:1.0"

=============== FILE: inputs/detection-results.json ===============
[
  {
    "image": "gcr.io/distroless/static-debian13:nonroot",
    "cosign_attested": false,
    "oci_labels": {},
    "syft_result": "no /etc/os-release found",
    "filesystem_summary": "minimal: /etc/passwd, /etc/group, CA bundle; no shell, no package manager"
  },
  {
    "image": "ghcr.io/example/static-binary:1.0",
    "cosign_attested": false,
    "oci_labels": {},
    "syft_result": "no /etc/os-release found",
    "filesystem_summary": "single binary, no filesystem layout"
  }
]
