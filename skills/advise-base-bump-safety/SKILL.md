---
name: advise-base-bump-safety
description: >
  Use when the user has output from audit-helm-chart-image-bases (or
  is otherwise asked to triage Docker base-image upgrades) and needs
  to know which bumps are safe to apply unattended versus which need
  migration work. Triggers on: "upgrade base images", "update Docker
  images", "container image version bumps", "Docker FROM line
  changes", "is it safe to bump bookworm to trixie", "review this
  Renovate base-image PR". Classifies each proposed FROM → FROM bump
  as safe-mechanical, requires-migration, license-aware,
  interim-caution, or not-recommended, and emits a per-image markdown
  advice doc. Pairs with audit-helm-chart-image-bases (this skill's
  input) and the chart-supply-refresh CLI (the tool that applies the
  safe-mechanical subset deterministically).
domain: cybersecurity
subdomain: supply-chain-security
tags:
  - supply-chain-security
  - container-security
  - dockerfile
  - base-image-upgrade
  - os-currency
  - migration-risk
version: '0.2'
author: kjothen
license: Apache-2.0
nist_csf:
  - PR.PS-01
  - PR.PS-02
  - ID.RA-01
  - ID.RA-05
---

# Advise Base-Bump Safety

Classify each proposed Dockerfile base-image bump into one of five
risk-coloured categories so a downstream tool (or a human) knows
which bumps can be applied mechanically and which need migration
work. **Read-only**: this skill produces a markdown advice doc per
bump; it does not modify Dockerfiles, rebuild images, or open PRs.

The audit half (`audit-helm-chart-image-bases`) tells you *what* is
stale. This skill tells you *whether the obvious bump is safe*. The
mechanical-apply half (`chart-supply-refresh` in
`repldriven/tools`) consumes the safe-mechanical subset and forks
the chart accordingly.

## When to Use

Use to triage proposed Docker base-image bumps before applying them
— either from an `audit-helm-chart-image-bases` report, a Renovate /
Dependabot PR, or a CVE-driven OS-major sweep. Cross-family migration
(escape from RHEL UBI, Oracle JDK, paid-Chainguard) *is* in scope
when the in-family bump triggers `license-aware` or `not-recommended`
— the `license-aware` rubric routes there by default.

**Do not use** for: auditing which images are stale
(`audit-helm-chart-image-bases`), rewriting Dockerfiles or forking a
chart (`chart-supply-refresh`), or CVE-specific patch analysis
(pair with a CVE-aware tool).

## Inputs

- **audit** (required): the `base-audit.json` produced by
  `audit-helm-chart-image-bases`. The skill walks every FROM
  entry classified `one-behind`, `multi-behind`, or
  `non-lts-interim` and produces advice for each. FROMs already
  `current` or `rolling-stable` are reported but classified as
  `no-action-needed`; `rolling-dev` and `unsupported` get their
  own advice. The skill does not re-derive the audit; it trusts
  the audit's currency classifications.
- **target-base** (optional, per-FROM): if the audit's suggested
  target is missing or you want to override it (e.g. "skip
  bookworm, go straight from bullseye to trixie"), supply
  `(image, stage, suggested-target)` tuples. Otherwise the skill
  uses the audit's currency table to derive the obvious one-step
  bump.
- **context** (optional): free-text notes about the workload (e.g.
  "this is a Go service that statically links everything" or
  "this Python service installs binary wheels via pip"). When
  present, the skill cites them as evidence for its
  classification — strictly *additional* signal, never a
  substitute for the indicators below.

## Workflow

### Step 0: Read the audit

Load `base-audit.json`. For each finding's `froms` list, identify
the entries whose `currency` is one of `one-behind`,
`multi-behind`, `non-lts-interim`, `rolling-dev`, or
`unsupported`. Ignore `current` and `rolling-stable` entries
beyond noting them in the report as `no-action-needed`.

### Step 1: Derive the proposed target

For each in-scope entry, derive the obvious one-step bump:

| Current family + version | Proposed target |
| --- | --- |
| `Debian 11` (bullseye) | `Debian 13` (trixie) — skip bookworm |
| `Debian 12` (bookworm) | `Debian 13` (trixie) |
| `Ubuntu LTS 22.04` (jammy) | `Ubuntu LTS 24.04` (noble) |
| `Ubuntu interim 24.10` / `25.04` | `Ubuntu LTS 24.04` (recommend LTS, not next interim) |
| `Alpine 3.20–3.22` | `Alpine 3.23` |
| `Alpine edge` | pin to current stable (e.g. `Alpine 3.23`) |
| `RHEL-family 8` | `RHEL-family 9` |
| `unsupported` (EOL) | current stable of family; flag retired packages |

If `--target-base` overrides are supplied, prefer those over the
table.

### Step 2: Apply the classification rubric

Match each `(before, after, image-context)` tuple against the
rubric below. Stop at the **first** category that fires; do not
double-classify. The categories are ordered roughly by
specificity, not severity.

#### `not-recommended`

The proposed bump is into a riskier or dead-end state. Indicators
(any one suffices):

1. **Rolling-dev source.** `before` is `alpine:edge`, `debian:sid`,
   `debian:unstable`, or `ubuntu:devel`. The "safe" advice is to
   pin to the current stable instead of staying on dev — but a
   mechanical apply would put you back on the same dev branch.
2. **Backwards.** `after` has a lower OS version than `before`
   (`alpine:3.23 → alpine:3.22`).
3. **EOL target.** `after` is past its standard-support EOL date
   (Debian 10, Ubuntu 18.04, Alpine ≤ 3.17, RHEL 7).

Recommended action: pin to the current stable of the family;
flag for the user to confirm before any rebuild.

#### `license-aware`

The bump crosses a licensing or subscription boundary. Indicators:

1. **RHEL UBI major bump.** `redhat/ubi8 → redhat/ubi9` or any
   ubi-family transition. Free `ubi` images redistribute but
   *base subscription entitlements* differ across majors;
   downstream rebuild costs (especially if the workload uses
   `subscription-manager`) need verification.
2. **Oracle JDK / vendor-JDK majors.** `eclipse-temurin` is fine;
   `oraclelinux`, `oracle/database`, `oracle/jdk` bumps cross
   Oracle's licensing terms. Confirm BCL / OTN acceptance for
   the new major.
3. **Chainguard free → paid tier.** Some Chainguard images move
   from free to paid editions on major version transitions
   (`cgr.dev/chainguard/<x>` → `cgr.dev/chainguard-private/<x>`).

**Recommended action — lead with family-escape, not sign-off.** The
legalistic answer ("get sign-off, then bump") accepts friction the
user usually doesn't need to accept. Default to a license-free
alternative; fall back to in-family + sign-off only when the user has
a hard constraint. See
[references/family-escape.md](./references/family-escape.md) for the
per-source-family escape table and how to record the escape in the
advice doc.

#### `requires-migration`

The bump is mechanically possible but introduces a runtime ABI,
package-availability, or behavioural change that's likely to
break the workload. Indicators (any one suffices):

1. **System Python major shift.** `python:3.11-slim-bullseye →
   python:3.11-slim-bookworm` keeps Python 3.11, but the *system*
   Python under `/usr/bin/python3` changes (bullseye's system
   Python is 3.9, bookworm's is 3.11). Wheels compiled against
   the old `libc` may not load.
2. **glibc/musl boundary or glibc symbol-version jump.** `alpine →
   debian` is a glibc/musl boundary (refuses to run musl-linked
   binaries). Within Debian, `bullseye (glibc 2.31) → trixie
   (glibc 2.41)` may require recompiling C extensions linked
   against older symbol versions.
3. **OpenSSL major bump.** Debian 11 ships OpenSSL 1.1; Debian 12+
   ships OpenSSL 3.x. Workloads with custom-compiled bindings
   (Python `cryptography`, Go `cgo`, Ruby `openssl` gem) need
   rebuilding or wheel-upgrade.
4. **Embedded database / stateful binary change.** Images that
   bundle MySQL, Postgres, or SQLite of a specific version
   (`mysql:8.0`, `postgres:14`) often change their on-disk format
   across OS majors due to system package bumps.

Recommended action: classify as needing a code/config change;
the tool should NOT apply this bump mechanically. Note the
specific indicator in the advice so a human can scope the
migration work.

#### `interim-caution`

The bump lands on a short-support OS track. Indicators:

1. **Ubuntu interim.** `after` matches `ubuntu:24.10`,
   `ubuntu:25.04`, `ubuntu:25.10` (any `.10` / `.04` of an odd
   year). 9-month support window vs LTS's 5+ years.
2. **Fedora.** `after` matches `fedora:N` where `N` is any
   Fedora release (13-month support).

Recommended action: recommend the **LTS alternative** (`ubuntu:24.04`
in place of `ubuntu:25.04`). If the user genuinely wants the
interim, document the 9-month renewal cadence in the advice.

#### `safe-mechanical`

The bump is a pure version-tag swap with no runtime ABI change
expected. **All** of the following must hold:

1. Same OS family on both sides (no glibc/musl crossing).
2. The workload in the image is **statically linked** OR uses a
   language runtime that re-resolves system libraries at startup
   (Go, Rust, Java/JVM, .NET, static-linked C/C++).
3. No vendor license boundary crossed (covered by
   `license-aware`).
4. No EOL or development-branch target (covered by
   `not-recommended`).
5. Within-family version-major bump matches the audit's currency
   table (no skipping multiple majors for a stateful workload).

Specific safe patterns:

- **Go-built images** moving Debian / RHEL major (the Go binary
  doesn't link to system libc beyond cgo trivia).
- **Distroless `-static`** moving Debian major (no glibc at all).
- **Eclipse Temurin / OpenJDK** moving Debian major (JVM
  re-resolves system libs).
- **Statically-linked Rust / C++ binaries** in scratch /
  distroless-static.

Recommended action: safe to apply mechanically. This is the
subset that `chart-supply-refresh --allow-bumps safe` will pick
up.

### Step 3: Emit the advice doc

Write one section per FROM under its owning chart (matches the
audit's grouping), with a top-of-file summary panel counting
findings per classification. See
[references/output-format.md](./references/output-format.md) for the
exact section template and summary-panel format.

Always emit `advice.md`. If `--json` is passed, additionally emit
`advice.json` (structured findings, one entry per FROM).

## Hard Constraints

- **Read-only.** Never modify Dockerfiles, charts, or audit JSON.
  The output is advice; remediation is the
  `chart-supply-refresh` tool's job.
- **One classification per FROM.** Stop at the first matching
  rubric category; do not stack labels. If two categories
  legitimately apply (e.g. a bump is both `license-aware` and
  `requires-migration`), follow the precedence order:
  `not-recommended` > `license-aware` > `requires-migration` >
  `interim-caution` > `safe-mechanical`. Document the secondary
  category in the **Notes** field.
- **Cite named indicators.** Every classification must reference
  the rubric's indicator names verbatim (`System Python major
  shift`, `RHEL UBI major bump`, etc.). "Looks risky" is not an
  acceptable indicator.
- **No fabricated CVEs.** The advice doc must not name specific
  CVE identifiers unless they appear in the input context. The
  classification is about base-version *risk*, not about specific
  vulnerabilities — pair with a CVE-aware tool for that.
- **Every FROM appears in `advice.md`.** Even already-current ones
  (as `no-action-needed`). Silent omission breaks the user's
  expectation that the advice covers the whole audit.
