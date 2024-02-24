{
  description = "Nix hash collection";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    flake-compat.url = "github:edolstra/flake-compat";
    queued-build-hook.url = "github:nix-community/queued-build-hook";
  };

  outputs = { self, nixpkgs, flake-utils, queued-build-hook, ... }:

    (flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" ] (system:
      let pkgs = nixpkgs.legacyPackages.${system}; in
      rec {
        packages = rec {
          default = build-hook;
          build-hook = pkgs.callPackage ./build-hook {};
        };


        checks.packages.build-hook = packages.build-hook;

        devShells.default = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [ rustc cargo gcc pkg-config ];
          buildInputs = [
            (pkgs.python3.withPackages (
              ps: [
                ps.fastapi
                ps.uvicorn
                ps.sqlalchemy
                ps.pydantic
              ]
            ))
            pkgs.jq
            pkgs.rust-analyzer
            pkgs.openssl
            pkgs.nixVersions.nix_2_19
            pkgs.nlohmann_json
            pkgs.libsodium
            pkgs.boost
            pkgs.rustfmt

          ];

          RUST_SRC_PATH = "${pkgs.rust.packages.stable.rustPlatform.rustLibSrc}";

        };
      })) // {

        nixosModules.hash-collection = import ./build-hook/nixos/module.nix { inherit inputs;};
      };


}
