# Worked example: queenswood chart

End-to-end license trace of `infra/helm/queenswood` (Chart.yaml
v0.5.3), captured 2026-05-15. Chosen because queenswood is the
running case study in this tile and produces a clean tracer
result — useful as a sanity check that the skill doesn't
fabricate findings. A "what if" sidebar at the bottom shows how
the rare actionable bases would render if the chart pulled them.

## Step 0 + 1: enumerate ImageRefs

Same image set the audit skill works against. 7 distinct
ImageRefs:

| ImageRef | Owning workload |
| --- | --- |
| `ghcr.io/repldriven/<13 services>:0.0.0` (single shared Dockerfile) | queenswood Deployments + Jobs |
| `ghcr.io/repldriven/bank-app:0.0.0` | queenswood bank-app Deployment |
| `alpine/k8s:1.30.14` (5 occurrences) | queenswood Deployments + Jobs (wait-for-* init containers) |
| `foundationdb/fdb-kubernetes-operator:v2.27.0` | fdbOperator Deployment |
| `foundationdb/fdb-kubernetes-monitor:{7.1.67, 7.3.63, 7.4.1}` | fdbOperator-managed StatefulSets |
| `apachepulsar/pulsar-all:4.0.10` | pulsar StatefulSets |
| `alpine/k8s:1.32.12` | pulsar (kubectl wait-for-* sidecars) |

## Step 2: detection signals applied

| ImageRef | Signal | Detected OS |
| --- | --- | --- |
| `ghcr.io/repldriven/<services>:0.0.0` | `syft-scan` | Ubuntu 24.04 noble (runtime stage; build stage's Debian doesn't ship with the final image) |
| `ghcr.io/repldriven/bank-app:0.0.0` | `syft-scan` | Alpine 3.21 (nginxinc/nginx-unprivileged final stage) |
| `alpine/k8s:1.30.14` | `syft-scan` | Alpine edge (rolling-dev, but free) |
| `foundationdb/fdb-kubernetes-operator:v2.27.0` | `oci-label` | RHEL-family 9.6 (rockylinux runtime) |
| `foundationdb/fdb-kubernetes-monitor:*` | `oci-label` (inherited from base) | RHEL-family 9-minimal (rockylinux) |
| `apachepulsar/pulsar-all:4.0.10` | `syft-scan` | Alpine 3.21 |
| `alpine/k8s:1.32.12` | `syft-scan` | Alpine edge |

Note the symmetry with the audit skill's example: same images,
same resolution; the difference is what we *do* with the
resolution. Audit checks OS currency; this skill checks license
tier.

## Step 3: license-tier classification

| Detected OS | Tier | Why |
| --- | --- | --- |
| Ubuntu 24.04 LTS (noble) | `free` | Community LTS; Ubuntu Pro is optional. |
| Alpine 3.21 / edge | `free` | Community distro. The `edge` rolling-dev concern is the audit skill's; not a license issue. |
| Rocky Linux 9 / 9-minimal | `free` | Free RHEL-compatible rebuild; no subscription. |

Every base in queenswood is `free`. **No escape needed** for any
ImageRef.

## Step 4: escape hatches

`no-escape-needed` for all 7 ImageRefs.

## Step 5: emitted report

```
image-graph: queenswood/charts/queenswood
generated_at: 2026-05-15T...

Summary panel:
  free                7 images (all)
  free-with-caveats   0
  commercial          0
  stale               0

Actionable findings: none.
```

The headline: queenswood is licence-clean. That's a useful result
on its own — confirms that the operator-heavy stack (FDB +
Pulsar) doesn't drag in licensed bases at the OS layer.

## "What if" sidebar — how actionable findings would render

If queenswood had pulled `docker.io/bitnami/postgresql:15.4.0`
(common pre-September-2025 pattern), the same workflow would
produce:

| ImageRef | Tier | Signal | Escape |
| --- | --- | --- | --- |
| `docker.io/bitnami/postgresql:15.4.0` | `stale` | `oci-label` (or `syft-scan` fallback) | Docker Official Postgres (`postgres:15`); CloudNativePG if moving to operator-managed; Chainguard `cgr.dev/chainguard/postgres` for minimal + frequently rebuilt. **Urgent**: no patches coming for the legacy archive. |

And if it had pulled `registry.access.redhat.com/ubi9/openjdk-21:1.20`:

| ImageRef | Tier | Signal | Escape |
| --- | --- | --- | --- |
| `registry.access.redhat.com/ubi9/openjdk-21:1.20` | `free-with-caveats` | `cosign-attestation` (Red Hat ships SBOMs) | Rocky/Alma 9 + Eclipse Temurin 21; or distroless-java if stateless. Caveat: UBI is acceptable for users already inside the Red Hat ecosystem who can live within the supported-software list. |

These render at the **top** of the report (commercial / stale
sorted before free-with-caveats sorted before free), making the
actionable findings the first thing the reviewer sees.

## Composition with the other tile skills

- The audit skill (`audit-helm-chart-image-bases`) would have
  found the same set of images and reported the OS currency
  (Debian 12 in builders, Ubuntu LTS in runtime, etc.). It
  doesn't comment on license.
- The bump-safety advisor (`advise-base-bump-safety`) would have
  classified the queenswood Debian-bookworm builders as
  `safe-mechanical` for a trixie bump. It doesn't comment on
  license either.
- This skill answers the question neither covers: "is anything
  here licensed or stale?".

For queenswood the answer is no. For a chart that pulls Bitnami
or RHEL — the post-September-2025 reality for many production
fleets — the answer is yes, and the escape table tells you what
to do about it.
