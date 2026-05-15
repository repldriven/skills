# Build-system manifests (Dockerfile-less images)

Some upstream projects don't ship a Dockerfile — they build container
images directly via Nix `dockerTools`, Google's `ko`, Bazel
`rules_docker` / `rules_oci`, or Jib (Java). The audit treats these as a
different build paradigm, not a missing Dockerfile.

Probe the cloned repo for these files in order; record
`dockerfile: <build-system>-built` on the first hit:

| File | Build system | Where the base is declared |
| --- | --- | --- |
| `flake.nix`, `nix/build.nix` | Nix `dockerTools` | `nixpkgs.url` input pin + `dockerTools.buildImage` `fromImage` (often omitted → distroless-equivalent) |
| `.ko.yaml`, `KO_DEFAULTS` | ko | `defaultBaseImage:` (typically `cgr.dev/chainguard/static` or `gcr.io/distroless/static`) |
| `BUILD.bazel` referencing `oci_image` / `container_image` | Bazel rules_oci / rules_docker | `base = "..."` attribute on the `oci_image` / `container_image` target |
| `jib-maven-plugin` / `jib-gradle-plugin` config | Jib | `<from><image>` in `pom.xml` or `jib.from.image` in `build.gradle` |

If a build-system manifest is found, record the build-system tag (e.g.
`nix-built`, `ko-built`, `bazel-built`, `jib-built`) and proceed to
Step 5's build-system-aware path. If no Dockerfile *and* no recognised
build-system file is present, the image is genuinely
`dockerfile-unknown` and Step 5 falls back to
`base-inferred-from-labels`.

## Per-build-system base extraction (Step 5)

- **Nix `dockerTools`** — read the `nixpkgs.url` flake input (e.g.
  `nixos-25.11`) and any `fromImage` argument to
  `dockerTools.buildImage`. If `fromImage` is absent, the image is
  assembled from Nix packages with no traditional base; record the
  nixpkgs pin as the closest analog of an OS version and classify
  against the corresponding NixOS release.
- **ko** — read `defaultBaseImage:` from `.ko.yaml`. Common values
  resolve to Chainguard static (rolling-stable) or Google distroless
  (rolling-stable).
- **Bazel** — read the `base = "@some_image//image"` attribute on the
  `oci_image` / `container_image` target; resolve through the
  `WORKSPACE` / `MODULE.bazel` to the registry ref.
- **Jib** — read `<from><image>` (Maven) or `jib.from.image` (Gradle);
  defaults to `gcr.io/distroless/java` if unset.

Record the build-system pin (e.g. `nixpkgs:nixos-25.11`,
`ko:cgr.dev/chainguard/static:latest`,
`jib:gcr.io/distroless/java17:nonroot`) as the FROM-equivalent in the
report. If no explicit base is declared, record `build-system-default`
and classify as `rolling-stable` — these systems default to
vendor-managed minimal bases.
