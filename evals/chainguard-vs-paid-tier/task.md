# Distinguish Chainguard free vs paid tier

## Problem / Feature Description

A platform team is reviewing a chart that pulls two Chainguard
images:

- `cgr.dev/chainguard/redis:latest` — Chainguard's **free public**
  image. Rebuilt frequently against current stable.
- `cgr.dev/chainguard-private/postgres:16` — Chainguard's **paid**
  enterprise tier (private registry, contract required).

The two images come from the same vendor but sit on opposite
sides of the license boundary. The naive verdict "Chainguard ==
free, low-friction" misses that the second image requires a paid
contract. The skill must not collapse them into a single tier.

## Output Specification

Produce two files in the working directory:

- `image-graph.json`
- `image-graph.md`

## Input Files

=============== FILE: inputs/Chart.yaml ===============
apiVersion: v2
name: tiny-cache-app
description: Minimal chart using Chainguard free + paid images.
type: application
version: 0.1.0
appVersion: "0.1.0"

=============== FILE: inputs/templates/cache.yaml ===============
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-cache
spec:
  replicas: 1
  selector:
    matchLabels: { app: redis-cache }
  template:
    metadata:
      labels: { app: redis-cache }
    spec:
      containers:
        - name: redis
          image: "cgr.dev/chainguard/redis:latest"

=============== FILE: inputs/templates/db.yaml ===============
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-db
spec:
  replicas: 1
  selector:
    matchLabels: { app: app-db }
  template:
    metadata:
      labels: { app: app-db }
    spec:
      containers:
        - name: postgres
          image: "cgr.dev/chainguard-private/postgres:16"

=============== FILE: inputs/detection-context.md ===============
Both images carry cosign-attested SBOMs identifying their base as
Wolfi (Chainguard's underlying free distro).

- `cgr.dev/chainguard/redis:latest` — public registry path, free
  to pull, frequent rebuilds.
- `cgr.dev/chainguard-private/postgres:16` — private registry
  path; requires Chainguard customer credentials.
