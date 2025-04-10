{ stdenv, rustPlatform, pkg-config, openssl, nlohmann_json, boost, patched-nix, libsodium, ... }:

rustPlatform.buildRustPackage rec {
  name = "nix-hash-collection-utils";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ pkg-config ];

  buildInputs = [
    openssl
    patched-nix
    nlohmann_json
    libsodium
    boost
  ];

  cargoLock = {
    lockFile = ./Cargo.lock;
  };
}
