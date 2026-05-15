# Escape-hatch mapping (Step 4)

For each `free-with-caveats`, `commercial`, or `stale` base,
recommend a per-source-family escape. Pick the **first viable
target for the workload type** — a generic "Docker Official"
pointer is less useful than naming the actual replacement (e.g.
the Postgres replacement for Bitnami Postgres).

## Bitnami family

The single most actionable column post-September-2025.

| Source | Recommended escape (first viable wins) |
| --- | --- |
| `docker.io/bitnami/<x>` (free public, pre-retirement) | **Docker Official Image** (e.g. `postgres:16`, `redis:7`, `mariadb:11`). **Chainguard** (`cgr.dev/chainguard/<x>`) if you want minimal + frequently rebuilt. **Operator-shipped images** (e.g. CloudNativePG for Postgres, MariaDB Operator) if you're moving to operator-managed workloads anyway. **Minimus** for drop-in Bitnami-shaped builds with a free tier. |
| `docker.io/bitnamilegacy/<x>` | **Urgent** — no patches coming. Same target list as above, but flag the urgency in the advice. |
| `docker.io/bitnami/<x>` (versioned but post-retirement-pulled) | Same target list; flag that the versioned tag is in indeterminate state. |

## RHEL family

| Source | Recommended escape |
| --- | --- |
| RHEL UBI (`registry.access.redhat.com/ubi*`) | **Rocky Linux** (`rockylinux:9`) for full RHEL compatibility without a subscription. **AlmaLinux** (`almalinux:9`) for the same. **Wolfi-based** images if you want minimal + frequently rebuilt and don't need RHEL-specific tools. **Distroless-java** if the workload is a stateless JVM service. |
| Full RHEL (paid subscription) | **UBI** if you can live within the supported-software list. **Rocky / Alma** for full freedom. |
| Oracle Linux | **Rocky / Alma** (RHEL-compatible without Oracle's terms). |

## SUSE family

| Source | Recommended escape |
| --- | --- |
| SUSE SLES | **openSUSE Leap** (free SLES-compatible) or **Rocky / Alma** if you don't need zypper-specific tools. |
| SLE-BCI (free SUSE base images) | These are already free; usually no escape needed. Treat as `free-with-caveats` if your workload needs SUSE-paid packages. |

## Canonical family

| Source | Recommended escape |
| --- | --- |
| Ubuntu Pro | **Ubuntu LTS** (free) + your own patching pipeline. **Debian** if you can live without `apt` Pro-tier packages. |

## Oracle family

| Source | Recommended escape |
| --- | --- |
| Oracle JDK images (paid-tier registry) | **Eclipse Temurin** (Adoptium build of OpenJDK, fully free) on a non-Oracle base. **Amazon Corretto** as another OpenJDK build. |

## Chainguard (paid → free)

| Source | Recommended escape |
| --- | --- |
| `cgr.dev/chainguard-private/<x>` (paid) | **`cgr.dev/chainguard/<x>`** (free public images) where available. **Wolfi-based community builds** for the underlying distro. **Distroless** if the workload doesn't need a shell. |

## How to express the escape in the report

For each affected ImageRef, the advice doc records:

- The detected source family (e.g. `docker.io/bitnamilegacy/*`).
- The recommended escape target (e.g. `docker.io/library/postgres:16`).
- A one-line rationale (e.g. *"Docker Official Postgres is the
  upstream that Bitnami packaged; drop-in for most usages, no
  subscription"*).
- An urgency flag for `stale`-tier entries (e.g. *"Urgent: no
  patches coming for bitnamilegacy"*).

Free-tier entries get `no-escape-needed` and don't appear in the
escape-hatch section of the report.
