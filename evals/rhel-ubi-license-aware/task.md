# Classify a RHEL UBI major bump

## Problem / Feature Description

An audit has flagged a Java service running on
`redhat/ubi8-minimal:8.10` (RHEL-family 8) as `one-behind`; the
current stable is `redhat/ubi9-minimal:9.x`. The audit's
suggested target is `redhat/ubi9-minimal:9.5`.

You're asked to advise on whether this bump is safe to apply.
The workload is a JVM service using Eclipse Temurin 21.

Use the rubric. Cite the named indicators.

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
      "owning-chart": "payments",
      "image": "registry.example.com/team/payments:2.1.0",
      "resolution-signal": "local",
      "source-repo": null,
      "tag-checkout": null,
      "dockerfile": "infra/docker/payments/Dockerfile",
      "froms": [
        {"stage": "runtime", "from": "redhat/ubi8-minimal:8.10",
         "os-family": "RHEL-family", "os-version": "8", "currency": "one-behind"}
      ]
    }
  ]
}

=============== FILE: inputs/context.md ===============
JVM service (Eclipse Temurin 21). The Dockerfile installs the JRE
from the `eclipse-temurin` apt-equivalent (`microdnf install
java-21-openjdk-headless`), runs a single Spring Boot fat-jar.

The Dockerfile does NOT call `subscription-manager` and does not
rely on Red Hat–specific package repositories beyond what
`ubi-minimal` ships out of the box.

Internal policy: the payments team has a Red Hat Universal Base
Image free-tier acceptance on file. They are not on an OpenShift
subscription.
