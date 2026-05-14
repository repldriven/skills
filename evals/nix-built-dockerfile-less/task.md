# Produce a base-image audit entry for a Dockerfile-less project

## Problem / Feature Description

A platform engineer has cloned the source repository for a
container image their Helm chart depends on, only to discover that
the repo contains **no Dockerfile**. The project builds its
container image directly from source via a different build system
— in this case Nix's `dockerTools.buildImage` driven from a
`flake.nix`. Their existing scanning pipeline, written around `find
. -name Dockerfile`, silently returns nothing for this repo and
the image ends up classified as "source-unknown", obscuring the
fact that the base is actually well-defined and inspectable.

The auditor needs to produce a single structured audit entry for
this image that:

1. Recognises the Dockerfile-less build paradigm rather than
   reporting it as a gap.
2. Reads the relevant pin (here, the `nixpkgs.url` flake input)
   from the build manifest.
3. Classifies the result against an OS-currency lookup, treating
   the Nix-built image's NixOS-flavoured pin as the comparison
   axis instead of a Debian/Ubuntu/Alpine version.

The audit covers a single image and the locally-extracted repo
that builds it.

## Output Specification

Produce one file in the working directory:

- `audit-entry.json` — a single JSON object describing the audit
  finding for this one image. Required fields:
  - `ref`: the image reference being audited
  - `dockerfile`: a value indicating no Dockerfile (e.g.
    `nix-built`)
  - `build_system`: a short string identifying the build
    system + the pin it uses
  - `base_pin`: the specific pin extracted from the build
    manifest (e.g. the value of `nixpkgs.url`)
  - `status`: the currency classification of `base_pin`
    against the audit's currency table
  - `evidence`: a short string explaining how the base_pin was
    derived

The audit's currency table (assume these are authoritative for
this run): NixOS current stable = `25.11`, previous stable =
`25.05`.

## Input Files

The repo for the image is provided inline as a flat set of files.
Treat them as if extracted under `./crossplane-source/`.

The audit target image is `xpkg.crossplane.io/crossplane/crossplane:v2.2.1`.

=============== FILE: inputs/crossplane-source/flake.nix ===============
{
  description = "Crossplane - The cloud native control plane framework";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    gomod2nix = {
      url = "github:nix-community/gomod2nix/75c2866d585a75a1b30c634dbd7c2dcce5a6c3a7";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, nixpkgs-unstable, gomod2nix }: {
    # Crossplane's flake outputs would live here in the real repo.
    # Truncated for this eval — the build entry-point referenced by
    # the build.sh script lives in nix/build.nix.
  };
}

=============== FILE: inputs/crossplane-source/nix/build.nix ===============
# Build OCI image arguments for dockerTools.
# This matches the distroless base image Crossplane previously used.
{ pkgs, version, crossplaneBin, arch, ... }:

let
  passwd = pkgs.writeText "passwd" ''
    root:x:0:0:root:/root:/sbin/nologin
    nobody:x:65534:65534:nobody:/nonexistent:/sbin/nologin
    nonroot:x:65532:65532:nonroot:/home/nonroot:/sbin/nologin
  '';

  imageArgs = {
    name = "xpkg.crossplane.io/crossplane/crossplane";
    tag = version;
    # Note: no `fromImage` argument — the image is assembled from
    # Nix packages directly, producing a distroless-equivalent
    # closure.
    contents = [ crossplaneBin pkgs.cacert ];
    config = {
      Entrypoint = [ "${crossplaneBin}/bin/crossplane" ];
    };
  };
in
  pkgs.dockerTools.buildImage imageArgs

=============== FILE: inputs/crossplane-source/Makefile ===============
.PHONY: all
all:
	nix build .#dockerImage
