{ rustPlatform, pkg-config, openssl, nlohmann_json, boost, nixVersions, libsodium, ... }:

rustPlatform.buildRustPackage rec {
  name = "nix-hash-collection-utils";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ pkg-config ];

  buildInputs = [ openssl nixVersions.nix_2_19 nlohmann_json libsodium boost ];

  cargoLock = {
    lockFile = ./Cargo.lock;
    outputHashes = {
      "libnixstore-0.4.0" = "sha256-bP75IcVWkXlFoKT4NyRTnpW+nzad++QY1Nq7eRUbFI4=";
    };

  };
}
