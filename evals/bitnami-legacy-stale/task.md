# Map a chart pulling from Bitnami's legacy archive

## Problem / Feature Description

A platform team is reviewing a small Helm chart that pins a
Postgres image to `docker.io/bitnamilegacy/postgresql:15.4.0`.
This image lives in Bitnami's *legacy* archive — a frozen
collection that received no patches after Bitnami's free public
catalog was retired in late September 2025. Production-grade
Bitnami images now require a Bitnami Secure Images subscription
($50K-$72K/year).

The reviewer wants a license-tier map of this chart with an
explicit escape recommendation for the Postgres image. They are
*not* asking about CVEs; they are asking about license-tier and
support state.

## Output Specification

Produce two files in the working directory:

- `image-graph.json` — full structured graph (nodes, edges,
  detection_signals, license_tiers, escape_hatches).
- `image-graph.md` — human report sorted so any `stale` or
  `commercial` entries appear at the top.

## Input Files

=============== FILE: inputs/Chart.yaml ===============
apiVersion: v2
name: tiny-postgres-app
description: Minimal chart with a Bitnami legacy Postgres dependency.
type: application
version: 0.1.0
appVersion: "0.1.0"

=============== FILE: inputs/templates/deployment.yaml ===============
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
          image: "docker.io/bitnamilegacy/postgresql:15.4.0"

=============== FILE: inputs/detection-result.json ===============
{
  "image": "docker.io/bitnamilegacy/postgresql:15.4.0",
  "signal": "syft-scan",
  "os": { "id": "debian", "version": "12" },
  "notes": "Bitnami Postgres 15.4.0 in the legacy archive; underlying base is Debian 12. Image last pushed 2025-07."
}
