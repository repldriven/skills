# License-tier classification (Step 3)

Each detected base falls into one of four tiers. The tiers
distinguish *what the user is on the hook for* — not just whether
something is "open source".

## Background: why this skill exists

The motivating event is the late-September-2025 retirement of
Bitnami's free public catalog. Production-grade Bitnami images
moved behind a Bitnami Secure Images subscription (publicly
reported at $50K-$72K/year), and older versioned tags now sit in
a frozen `bitnamilegacy/*` archive that receives no patches.
Charts that previously pulled `docker.io/bitnami/<x>` silently
now pull either a paid subscription or an abandoned legacy tag —
neither acceptable for production. The four-tier rubric below is
what surfaces this state across a fleet.

## Tier 1: `free`

No subscription, no procurement obligation, no licensing caveat
that affects production use.

| Family | Notes |
| --- | --- |
| Alpine | Community-maintained, fully free. |
| Debian | Community-maintained, fully free. |
| Ubuntu (community LTS / interim) | Free; commercial support optional via Ubuntu Pro (see `commercial`). |
| Rocky Linux | Free RHEL-compatible rebuild. |
| AlmaLinux | Free RHEL-compatible rebuild. |
| Wolfi | Chainguard's underlying free distro. |
| Chainguard public images (`cgr.dev/chainguard/*`) | Free; rebuilt frequently against current stable. |
| Google distroless (`gcr.io/distroless/*`) | Free; minimal runtime. |
| Amazon Linux | Free on or off AWS; AWS provides support to AWS customers. |
| BusyBox | Free; embedded systems lineage. |
| `scratch` / no OS | Not technically a "tier" — record as `n/a`. No licensing exposure. |

## Tier 2: `free-with-caveats`

Free to use, but with a documented constraint that affects
production policy.

| Family | The caveat |
| --- | --- |
| RHEL UBI (`registry.access.redhat.com/ubi*`) | Free to redistribute, but UBI is tied to Red Hat's supported-software list. Some packages are gated behind a subscription if you want patches outside the UBI core. |
| Oracle Linux | Free distro, but support requires a paid Oracle contract; some kernel modules (UEK) have separate terms. |
| Bitnami Secure Images free tier | Latest-only; no version pinning, no LTS branches. Production-grade pinning requires the paid tier (see `commercial`). |

## Tier 3: `commercial`

Requires a paid subscription, contract, or vendor agreement to
use in production.

| Family | The cost |
| --- | --- |
| RHEL (full subscription, not UBI) | Per-socket / per-VM subscription. |
| SUSE SLES | Per-instance subscription. |
| Ubuntu Pro | Canonical's commercial support tier; required for some long-tail patches. |
| Bitnami Secure Images / Bitnami Premium | $50K-$72K/year as of late-2025 catalogue retirement. Production-grade images for the post-Bitnami-free era. |
| `cgr.dev/chainguard-private/*` | Paid Chainguard tier; distinct from the free public images. |
| Oracle JDK images (paid-tier registry) | Bound to Oracle's BCL / OTN. |

## Tier 4: `stale`

Past EOL, in a frozen archive, or otherwise no longer receiving
patches.

| Family | Why it's stale |
| --- | --- |
| `docker.io/bitnamilegacy/*` | Frozen archive after Bitnami's free catalogue retirement (late September 2025). No patches forthcoming. |
| CentOS Linux 7 | EOL 2024-06-30. |
| CentOS Linux 8 | EOL 2021-12-31 (early). |
| Anything past distro EOL | Debian 10, Ubuntu 18.04 LTS (standard support ended), Alpine ≤ 3.17, RHEL 7, etc. |

## Tie-breakers

- **Family ambiguity** (e.g. Chainguard free vs paid tier): the
  source registry path is authoritative. `cgr.dev/chainguard/x`
  is free; `cgr.dev/chainguard-private/x` is commercial.
- **Bitnami ambiguity**: `docker.io/bitnami/*` versioned tags
  pulled *before* the retirement are now in an indeterminate
  state — the underlying image still exists but is no longer the
  recommended upstream. Treat as `stale` unless the image is
  obviously the latest tag with a recent push date.
- **Distro version + EOL**: if the detected base is a recognised
  free family but past EOL, the tier is `stale`, not `free`.
