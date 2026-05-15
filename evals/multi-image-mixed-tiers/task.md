# Multi-image chart spanning all four license tiers

## Problem / Feature Description

A platform team is reviewing a Helm chart that pulls four images,
one from each license tier:

- `nginxinc/nginx-unprivileged:1.27-alpine` — Alpine-based, free.
- `registry.access.redhat.com/ubi9/openjdk-21:1.20` — RHEL UBI,
  free-with-caveats.
- `docker.io/bitnami/postgresql:16` — Bitnami versioned image
  pulled post-September-2025-retirement. Commercial (the
  versioned tags are the Bitnami Secure Images paid tier now).
- `docker.io/bitnamilegacy/redis:7.2.0` — Bitnami legacy archive,
  stale.

The reviewer wants:
- A full graph emitted.
- A report sorted so the **actionable findings** (commercial +
  stale) appear at the top — they need a procurement decision —
  with free-with-caveats next and free at the bottom.

## Output Specification

Produce two files in the working directory:

- `image-graph.json` — must contain entries for all four images.
- `image-graph.md` — sort order: commercial / stale first,
  free-with-caveats second, free third.

## Input Files

=============== FILE: inputs/Chart.yaml ===============
apiVersion: v2
name: tiny-mixed-app
description: Minimal chart spanning all four license tiers.
type: application
version: 0.1.0
appVersion: "0.1.0"

=============== FILE: inputs/templates/all-four.yaml ===============
apiVersion: v1
kind: List
items:
  - apiVersion: apps/v1
    kind: Deployment
    metadata: { name: web }
    spec:
      replicas: 1
      selector: { matchLabels: { app: web } }
      template:
        metadata: { labels: { app: web } }
        spec:
          containers:
            - name: nginx
              image: "nginxinc/nginx-unprivileged:1.27-alpine"
  - apiVersion: apps/v1
    kind: Deployment
    metadata: { name: jvm }
    spec:
      replicas: 1
      selector: { matchLabels: { app: jvm } }
      template:
        metadata: { labels: { app: jvm } }
        spec:
          containers:
            - name: jvm
              image: "registry.access.redhat.com/ubi9/openjdk-21:1.20"
  - apiVersion: apps/v1
    kind: Deployment
    metadata: { name: db }
    spec:
      replicas: 1
      selector: { matchLabels: { app: db } }
      template:
        metadata: { labels: { app: db } }
        spec:
          containers:
            - name: postgres
              image: "docker.io/bitnami/postgresql:16"
  - apiVersion: apps/v1
    kind: Deployment
    metadata: { name: cache }
    spec:
      replicas: 1
      selector: { matchLabels: { app: cache } }
      template:
        metadata: { labels: { app: cache } }
        spec:
          containers:
            - name: redis
              image: "docker.io/bitnamilegacy/redis:7.2.0"

=============== FILE: inputs/detection-context.md ===============
- `nginxinc/nginx-unprivileged:1.27-alpine` — Syft identifies
  Alpine 3.21 as the base.
- `registry.access.redhat.com/ubi9/openjdk-21:1.20` — cosign
  attestation present; SBOM identifies ubi9-minimal as the base.
- `docker.io/bitnami/postgresql:16` — versioned Bitnami image,
  post-retirement. The versioned tags require a Bitnami Secure
  Images subscription as of late September 2025.
- `docker.io/bitnamilegacy/redis:7.2.0` — Bitnami legacy archive;
  no patches forthcoming.
