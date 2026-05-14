{
  description = "Skills development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnsupportedSystem = true;
        };

        gcloud = pkgs.google-cloud-sdk.withExtraComponents (
          with pkgs.google-cloud-sdk.components; [ gke-gcloud-auth-plugin ]
        );

        tessl = pkgs.stdenv.mkDerivation rec {
          pname = "tessl";
          version = "0.79.1";
          src = pkgs.fetchurl {
            url = "https://install.tessl.io/binaries/${version}/tessl-${version}-darwin-arm64.tar.gz";
            sha256 = "1d1yqj8j4xbi57j7qpc3s9h4dv8hcyqyjldwvxxl5yhmm8rn66f1";
          };
          sourceRoot = ".";
          installPhase = ''
            mkdir -p $out/bin
            install -m 755 tessl-${version}-darwin-arm64 $out/bin/tessl
          '';
        };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.argocd
            pkgs.colima
            pkgs.crane
            pkgs.crossplane-cli
            pkgs.docker
            pkgs.docker-credential-helpers
            gcloud
            pkgs.just
            pkgs.k6
            pkgs.kind
            pkgs.krew
            pkgs.kubeaudit
            pkgs.kubeconform
            pkgs.kubernetes-helm
            pkgs.openssl
            pkgs.semgrep
            pkgs.skopeo
            tessl
            pkgs.tilt
            pkgs.trivy
            pkgs.uv
            pkgs.yq
            pkgs.yo
          ];

          shellHook = ''
            # Colima/Docker configuration for testcontainers
            export DOCKER_HOST="unix://$HOME/.config/colima/default/docker.sock"
            export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE="/var/run/docker.sock"
            export TESTCONTAINERS_REUSE_ENABLE="TRUE"

            if ! colima status &>/dev/null; then
              echo "Docker not running — use 'just start-docker' to start"
            fi
            echo "Skills environment loaded"
          '';
        };
      }
    );
}
