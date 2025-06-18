{
  description = "Nix hash collection";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    flake-compat.url = "github:edolstra/flake-compat";
    queued-build-hook.url = "github:JulienMalka/queued-build-hook/postbuildscript";
  };

  outputs =
    inputs@{
      nixpkgs,
      flake-utils,
      queued-build-hook,
      ...
    }:

    (flake-utils.lib.eachSystem
      [
        "x86_64-linux"
        # https://github.com/NixOS/nix/issues/13045
        #"aarch64-linux"
      ]
      (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          # Should be generalized, documented, tested and upstreamed
          # similar to https://github.com/NixOS/nix/pull/12044
          patched-nix =
            (pkgs.nixVersions.git.appendPatches [
              ./utils/nix-expose-apis.patch
              ./utils/nix-fix-repl-test.patch
            ]).overrideAttrs(a: {
              # tests/functional/repl.sh.test is failing in CI
              doInstallCheck = pkgs.stdenv.hostPlatform.system == "x86_64-linux";
            });
        in
        rec {
          packages = rec {
            utils = pkgs.callPackage ./utils { inherit patched-nix; };
            web = pkgs.python3.pkgs.callPackage ./backend.nix { };
            default = utils;
          };

          checks.packages.utils = packages.utils;

          devShells.default = pkgs.mkShell {
            nativeBuildInputs = with pkgs; [
              rustc
              cargo
              gcc
              pkg-config
            ];
            buildInputs = [
              (pkgs.python3.withPackages (ps: [
                ps.fastapi
                ps.uvicorn
                ps.sqlalchemy
                ps.pydantic
              ]))
              pkgs.jq
              pkgs.rust-analyzer
              pkgs.openssl
              patched-nix
              pkgs.nlohmann_json
              pkgs.libsodium
              pkgs.boost
              pkgs.rustfmt
            ];

            RUST_SRC_PATH = "${pkgs.rust.packages.stable.rustPlatform.rustLibSrc}";
          };
          nixosModules.hash-collection = import ./utils/nixos/module.nix queued-build-hook.nixosModules.queued-build-hook;
          nixosModules.hash-collection-server = import ./web/nixos/module.nix;
        }
      )
    );
    #// {

    #};
}
