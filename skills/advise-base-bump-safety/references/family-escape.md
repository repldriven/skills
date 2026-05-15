# Family-escape targets for `license-aware` bumps

When the `license-aware` rubric fires, the **default Recommended
action is to escape the licensed family**, not stay in it and obtain
sign-off. The legalistic in-family path is the *secondary* option,
documented in Notes for users with a hard constraint (existing
OpenShift subscription, contractual UBI obligation, internal
compliance gate mandating Red Hat).

## Per-source-family escape options

| Source family | Family-escape options (in rough order of cultural-fit) |
| --- | --- |
| `redhat/ubi*` | **Fedora** (upstream of RHEL; same `dnf` / RPM ecosystem; current stable as of 2026 is Fedora 42; 13-month support window — note `interim-caution` applies to the support cadence). **Rocky Linux** / **AlmaLinux** (downstream RHEL rebuilds; LTS-style 10-year support; no Red Hat subscription needed). **`gcr.io/distroless/java*`** for stateless JVM workloads. **Wolfi** / **Chainguard** for clean-room minimal bases. |
| `oraclelinux` / `oracle/jdk*` | **Eclipse Temurin** (Adoptium build of OpenJDK, fully free) on a non-Oracle base. **Rocky** / **Alma** for the OS layer if you need a RHEL-compatible distro. **Distroless-java** for stateless workloads. |
| `cgr.dev/chainguard/<x>` (free → paid tier) | Stay on the pinned free image until a paid contract is in place, or pivot to **Wolfi-based community images** (Chainguard's underlying distro, fully free), or **distroless** if the workload doesn't need a shell. |

## How to record the escape in the advice doc

- **Recommended action** field — names the family-escape target and a
  one-line rationale (e.g. *"Switch to `rockylinux:9-minimal`: same
  RPM ecosystem, no Red Hat subscription needed"*).
- **Notes** field — records the original in-family bump (e.g.
  `ubi8 → ubi9`) as a secondary path, flagged with the licensing
  requirement, for hard-constraint users who can't escape the family.
