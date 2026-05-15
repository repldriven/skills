# Map a chart pulling a RHEL UBI image

## Problem / Feature Description

A platform team is reviewing a Helm chart that pins a JVM service
to `registry.access.redhat.com/ubi9/openjdk-21:1.20`. UBI is Red
Hat's Universal Base Image — free to redistribute, but tied to
Red Hat's supported-software list. Some packages outside that
list require a Red Hat subscription for updates.

A cosign-attested SBOM is attached to the image (Red Hat ships
SBOMs across UBI). The agent should prefer the cosign signal
over Syft when both are available.

The reviewer needs to know: is this licensed? Free? In between?
And what's the escape path if they want full freedom from Red
Hat's terms?

## Output Specification

Produce two files in the working directory:

- `image-graph.json`
- `image-graph.md` — sorted so non-free-tier entries appear at
  the top.

## Input Files

=============== FILE: inputs/Chart.yaml ===============
apiVersion: v2
name: tiny-jvm-service
description: Minimal chart pulling a UBI-based JVM image.
type: application
version: 0.1.0
appVersion: "0.1.0"

=============== FILE: inputs/templates/deployment.yaml ===============
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jvm-service
spec:
  replicas: 1
  selector:
    matchLabels: { app: jvm-service }
  template:
    metadata:
      labels: { app: jvm-service }
    spec:
      containers:
        - name: jvm
          image: "registry.access.redhat.com/ubi9/openjdk-21:1.20"

=============== FILE: inputs/cosign-attestation.json ===============
{
  "predicateType": "https://spdx.dev/Document",
  "predicate": {
    "SPDXID": "SPDXRef-DOCUMENT",
    "name": "openjdk-21-1.20",
    "packages": [
      {
        "name": "ubi9-minimal",
        "versionInfo": "9.4-1227",
        "supplier": "Organization: Red Hat",
        "licenseDeclared": "Red Hat Enterprise Linux License",
        "downloadLocation": "registry.access.redhat.com/ubi9/ubi-minimal"
      },
      {
        "name": "java-21-openjdk-headless",
        "versionInfo": "21.0.10.0.7-1.el9",
        "supplier": "Organization: Red Hat",
        "licenseDeclared": "GPL-2.0-with-classpath-exception"
      }
    ]
  }
}
