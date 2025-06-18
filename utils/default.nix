{ callPackage, stdenv, rustPlatform, pkg-config, openssl, nlohmann_json, boost, libsodium, ... }:

rustPlatform.buildRustPackage rec {
  name = "nix-hash-collection-utils";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ pkg-config ];

  buildInputs = [
    openssl
    (callPackage ./patched-nix {})
    nlohmann_json
    libsodium
    boost
  ];

  cargoLock = {
    lockFile = ./Cargo.lock;
  };
}
