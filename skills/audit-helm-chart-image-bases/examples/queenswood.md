# Worked example: queenswood chart

End-to-end audit of `infra/helm/queenswood` (Chart.yaml v0.5.3),
captured 2026-05-14 against the chart's release-pinned image tags.
Chosen as the worked example because it exercises every
resolution signal the skill supports — including the two that
were added after the first audit run surfaced the gaps:
**`base-inferred-from-labels`** and the **release-tag checkout**
step.

## Step 0 + 1: inventory and group by owning chart

22 image occurrences across the rendered chart, consolidating to
7 distinct `(image, dockerfile)` audit entries:

| Audit entry | Image(s) | Owning chart | Hardcoded? |
| --- | --- | --- | --- |
| 1 | `ghcr.io/kjothen/<13 services>:0.0.0` (single shared Dockerfile) | queenswood | no |
| 2 | `ghcr.io/kjothen/bank-app:0.0.0` | queenswood | no |
| 3 | `alpine/k8s:1.30.14` (5 template occurrences) | queenswood | **yes** |
| 4 | `foundationdb/fdb-kubernetes-operator:v2.27.0` | fdbOperator | no |
| 5 | `foundationdb/fdb-kubernetes-monitor:{7.1.67, 7.3.63, 7.4.1}` | fdbOperator | no |
| 6 | `apachepulsar/pulsar-all:4.0.10` | pulsar | no |
| 7 | `alpine/k8s:1.32.12` (via `pulsar.images.kubectl`) | pulsar | no |

Chart-level `sources:` snapshot:

- `infra/helm/queenswood/Chart.yaml` — no `sources:` field. Main
  chart; this repo *is* the source.
- `charts/fdb-operator/Chart.yaml` — `sources:`
  `[https://github.com/FoundationDB/fdb-kubernetes-operator/tree/main/charts/fdb-operator]`.
- pulsar subchart — `sources:`
  `[https://github.com/apache/pulsar, https://github.com/apache/pulsar-helm-chart]`.
  First URL is the image source; the second is the chart source.

## Step 2: resolution signals applied

| Entry | Signal | Source repo |
| --- | --- | --- |
| 1 (services) | `local` (matches `local-owner-prefixes: [ghcr.io/kjothen]`) | this repo — `infra/docker/service/Dockerfile`, confirmed via the Tiltfile docker_build loop |
| 2 (bank-app) | `local` | this repo — `infra/docker/bank-app/Dockerfile` |
| 3 (`alpine/k8s` hardcoded) | `slug-heuristic` | `github.com/alpine-docker/k8s` |
| 4 (fdb-operator) | `chart-sources` | `github.com/FoundationDB/fdb-kubernetes-operator` (sources[0], stripped of `/tree/main/charts/fdb-operator`) |
| 5 (fdb-monitor ×3) | `chart-sources` initial probe, but no monitor Dockerfile in operator repo; **falls through to `base-inferred-from-labels`** | source repo at `github.com/{foundationdb, apple}/foundationdb-kubernetes-monitor` returns auth prompts on clone |
| 6 (pulsar-all) | `chart-sources` (sources[0]) | `github.com/apache/pulsar` |
| 7 (`alpine/k8s` via pulsar) | `slug-heuristic` | same `github.com/alpine-docker/k8s` (deduplicated with entry 3) |

The OCI-label signal was probed for all four "external" images
and returned no source URL on any of them — confirming the SKILL
text that this is a last-resort signal for source-URL lookup,
not a primary one.

## Step 3 + 3.5: clone unique repos and check out release tags

Three unique upstream clones:

```bash
git clone --depth=1 https://github.com/FoundationDB/fdb-kubernetes-operator
git clone --depth=1 https://github.com/apache/pulsar
git clone --depth=1 https://github.com/alpine-docker/k8s
```

Then check out the tags that match the pinned image versions:

```bash
cd github.com-FoundationDB-fdb-kubernetes-operator
git fetch --depth=1 origin tag v2.27.0
git checkout v2.27.0
# → Dockerfile at v2.27.0 matches the released image

cd github.com-apache-pulsar
git fetch --depth=1 origin tag v4.0.10
git checkout v4.0.10
# → docker/pulsar/Dockerfile at v4.0.10 has ARG ALPINE_VERSION=3.21
#   (HEAD has 3.23 — would have been wrong without checkout)
```

The alpine-docker/k8s tags don't track the kubectl-version tags
the chart pulls (`1.30.14` / `1.32.12` are kubectl versions in
the build args, not Git tags on the repo). Recorded as
`tag-checkout: head-fallback` for entries 3 and 7.

## Steps 4 + 5: parse FROMs (real values, not illustrative)

| Entry | Dockerfile | Stage | FROM | Inferred OS |
| --- | --- | --- | --- | --- |
| 1 | `infra/docker/service/Dockerfile` | build | `clojure:temurin-21-tools-deps-bookworm` | Debian 12 (bookworm) |
| 1 | (same) | runtime | `eclipse-temurin:21-jre-noble` | Ubuntu LTS 24.04 (noble) |
| 2 | `infra/docker/bank-app/Dockerfile` | build | `node:22-alpine` | Alpine inferred (3.21) |
| 2 | (same) | runtime | `nginxinc/nginx-unprivileged:1.27-alpine` | Alpine inferred (3.21) |
| 3 | `alpine-docker/k8s/Dockerfile` @ HEAD | — | `alpine:edge` | Alpine edge (rolling-dev branch) |
| 4 | `fdb-kubernetes-operator/Dockerfile` @ v2.27.0 | builder | `golang:1.25.8-bookworm` | Debian 12 (bookworm) |
| 4 | (same) | runtime | `rockylinux/rockylinux:9.6-minimal` | RHEL-family 9 |
| 5 | dockerfile-ambiguous (monitor repo auth-gated) | runtime only (via labels) | inherited: `rockylinux:9-minimal` | RHEL-family 9 |
| 6 | `apache/pulsar/docker/pulsar/Dockerfile` @ v4.0.10 | pulsar | `alpine:3.21` (ARG ALPINE_VERSION=3.21) | Alpine 3.21 |
| 6 | (same) | jvm | `amazoncorretto:21-alpine3.21` | Alpine 3.21 |
| 6 | (same) | snappy-java | `alpine:3.21` | Alpine 3.21 |
| 6 | (same) | (final) | `alpine:3.21` | Alpine 3.21 |
| 7 | `alpine-docker/k8s/Dockerfile` @ HEAD (same Dockerfile as entry 3) | — | `alpine:edge` | Alpine edge |

## Step 7: status classification

| Family / version | Status |
| --- | --- |
| Debian 12 (bookworm) — entries 1 build, 4 builder | `one-behind` (trixie 13 stable since 2025-08-09) |
| Ubuntu LTS 24.04 — entry 1 runtime | `current` |
| Alpine inferred 3.21 — entry 2 build + runtime | `current` (with `base-inferred` note: tracking moving target) |
| Alpine edge — entries 3, 7 | **`rolling-dev`** (not the same as distroless rolling-stable) |
| RHEL-family 9 — entries 4 runtime, 5 | `current` |
| Alpine 3.21 — entry 6 all four stages | `current` |

## Step 8: tree-report shape (from the real run)

See `/tmp/base-audit-tree.txt` for the full output. Summary
panel:

```
Resolution signals used:
  local                      14 images (queenswood services + bank-app)
  chart-sources               4 images (FDB operator + Pulsar pulsar-all)
  slug-heuristic              2 images (alpine/k8s ×2)
  base-inferred-from-labels   3 images (FDB monitor ×3)

Status counts at the FROM level:
  current          9 FROMs
  one-behind       2 FROMs   (bookworm build stages: queenswood + fdb-operator)
  rolling-stable   2 FROMs   (bank-app node/nginx alpine inferred)
  rolling-dev      2 FROMs   (alpine:edge ×2)
  dockerfile-ambiguous 1 image   (fdb-monitor; final base recovered via labels)
```

Headline finding: two Dockerfile **build stages** still use
Debian bookworm (12) for their Clojure/Go toolchains, while
trixie (13) became stable 2025-08-09. Every runtime stage is
current. The `alpine:edge` use in alpine-docker/k8s is the only
`rolling-dev` finding — worth flagging because edge is Alpine's
*development* branch, not a stable release.

## Tessl eval hooks (post-real-run)

The skill run passes evaluation when **all** of the following
hold:

1. Every image in the rendered chart is represented in the
   tree report, attributed to its owning chart. Images
   sharing a Dockerfile may be consolidated to a single audit
   entry as long as the full image list is recorded.
2. Every audit entry carries a `resolution-signal` from the
   closed set: `local`, `chart-sources`, `slug-heuristic`,
   `oci-label`, `base-inferred-from-labels`, `source-unknown`.
3. The 13 `ghcr.io/kjothen/<svc>` services + `bank-app` all
   resolve via the `local` signal and reference at least one
   Dockerfile under `infra/docker/`.
4. The fdb-operator subchart's operator image resolves via
   `chart-sources` to
   `github.com/FoundationDB/fdb-kubernetes-operator`,
   confirming the `sources:` field was read from
   `charts/fdb-operator/Chart.yaml`.
5. The pulsar subchart's `apachepulsar/pulsar-all` image
   resolves via `chart-sources` to
   `github.com/apache/pulsar` (the **first** URL in `sources:`),
   not the second `pulsar-helm-chart` URL.
6. The `foundationdb/fdb-kubernetes-monitor:*` images land in
   `dockerfile-ambiguous` for the Dockerfile, AND carry a
   `base-inferred-from-labels` entry identifying
   `rockylinux:9-minimal` as the runtime base.
7. The operator Dockerfile is read from the `v2.27.0` tag, and
   the Pulsar Dockerfile is read from the `v4.0.10` tag — not
   HEAD. The report records `tag-checkout: <tag-name>` for each
   cloned repo, or `tag-checkout: head-fallback` (with reason)
   where no matching tag was found.
8. Every multi-stage Dockerfile contributes one row per `FROM`
   instruction — not just the runtime stage. The Pulsar entry
   reports 4 FROMs; the FDB-operator entry reports 2; the
   queenswood services entry reports 2.
9. `alpine:edge` (and `debian:sid`, `debian:unstable`,
   `ubuntu:devel`) FROMs are classified as **`rolling-dev`**, a
   class distinct from `rolling-stable` (distroless, Chainguard,
   `:latest`). The two should not be conflated.
10. The OS-currency table's `last-edited` date is present in the
    report header. If older than ~6 months at run time, the
    header carries a `table-stale` warning.
11. Any `dockerfile-ambiguous` image is reported with the full
    set of candidates considered (URLs probed, Dockerfiles
    searched, base-via-labels result) so the user can manually
    resolve it.

A run that reports success while violating any of (1)–(11) is an
evaluation failure even if the report file was produced.
