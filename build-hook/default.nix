{ rustPlatform, pkg-config, openssl, nlohmann_json, boost, nixVersions, libsodium, ... }:

rustPlatform.buildRustPackage rec {
  name = "nix-hash-collection-post-build-hook";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ pkg-config ];

  buildInputs = [ openssl nixVersions.nix_2_19 nlohmann_json libsodium boost ];

  cargoLock = {
    lockFile = ./Cargo.lock;
    outputHashes = {
      "libnixstore-0.4.0" = "sha256-mF2okhT3+ZKNcAHwyRe15eZNxN0rRI6ZyuNpn/fbFK0=";
    };

  };
}
