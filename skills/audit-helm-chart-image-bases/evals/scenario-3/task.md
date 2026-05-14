# Audit an image whose upstream source repo is unreachable

## Problem / Feature Description

A platform team is auditing the base OS of every image in a
production Helm chart, and one of the images is published by a
vendor whose source repository is private. The chart's
`Chart.yaml` doesn't list `sources:` for this subchart, and probes
of the obvious GitHub URLs (workspace name + repo name in
several conventional shapes) all return either 404 or a
GitHub authentication prompt. The OCI image itself has no
`org.opencontainers.image.source` label either.

This image is genuinely **source-unknown** in the strict sense
that the auditor can't recover its Dockerfile. But the team would
still like to know what OS the image *runs on* at runtime, even
without the build-stage detail. Modern vendor images inherit
labels from their base image during their build, so the final
image often carries `name`, `version`, and
`org.opencontainers.image.vendor` labels that point back to the
base — without the image author having set those labels
themselves.

The team has already pulled the image config (via `crane config`)
and saved it for you. Your job: produce a single audit entry that
records *how* you reached your conclusion (which resolution
signals were tried, in what order, with what outcome), so a
reviewer can re-trace the logic.

## Output Specification

Produce one file in the working directory:

- `audit-entry.json` — a single JSON object with at least:
  - `ref`: the image reference being audited
  - `resolution_signal`: which signal ended up succeeding (or
    `source-unknown` if none did)
  - `signals_tried`: an ordered list of signals that were
    attempted, each with `signal` and `outcome` keys
  - `base_inferred`: the base image identified from inherited
    labels, or `null` if not derivable
  - `base_os_family` and `base_os_version`: the OS classification
    of `base_inferred`

If no base is derivable from the provided inputs, set the
base fields to `null` and explain in a `notes` field — do not
guess.

## Input Files

The agent already attempted the following resolution probes and
recorded the outcomes:

=============== FILE: inputs/probes.txt ===============
Image: foundationdb/fdb-kubernetes-monitor:7.4.1
Owning chart: fdb-operator (vendored)

Probes performed (in order):

1. local Dockerfile match: NOT APPLICABLE
   (image owner foundationdb is not in local-owner-prefixes)

2. Chart.yaml sources: NO USABLE URL
   (the owning chart's Chart.yaml sources field points at the
    fdb-operator repo, which contains the operator Dockerfile
    but NOT a monitor Dockerfile)

3. slug-heuristic: FAILED
   git ls-remote https://github.com/foundationdb/fdb-kubernetes-monitor
     → auth prompt (private/404)
   git ls-remote https://github.com/FoundationDB/fdb-kubernetes-monitor
     → auth prompt (private/404)
   git ls-remote https://github.com/apple/foundationdb-kubernetes-monitor
     → auth prompt (private/404)

4. oci-label (org.opencontainers.image.source): NOT PRESENT
   (see crane-config.json — the image has no source-URL label)

=============== FILE: inputs/crane-config.json ===============
{
  "architecture": "amd64",
  "os": "linux",
  "created": "2026-04-15T10:32:11.000Z",
  "config": {
    "Entrypoint": ["/usr/bin/fdb-kubernetes-monitor"],
    "Labels": {
      "io.buildah.version": "1.37.6",
      "license": "BSD-3-Clause",
      "name": "rockylinux",
      "org.opencontainers.image.authors": "Magauer Lukas, Neil Hanlon, Louis Abel",
      "org.opencontainers.image.license": "BSD-3-Clause",
      "org.opencontainers.image.name": "rockylinux",
      "org.opencontainers.image.url": "https://github.com/rocky-linux/rocky-toolbox-images",
      "org.opencontainers.image.vendor": "Rocky Enterprise Software Foundation",
      "org.opencontainers.image.version": "9-minimal",
      "vendor": "Rocky Enterprise Software Foundation",
      "version": "9-minimal"
    }
  }
}
