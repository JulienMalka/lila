{ stdenv, rustPlatform, pkg-config, openssl, nlohmann_json, boost, nixVersions, libsodium, ... }:

rustPlatform.buildRustPackage rec {
  name = "nix-hash-collection-utils";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [ pkg-config ];

  buildInputs = [
    openssl
    (nixVersions.git.overrideAttrs(a: {
      # Should be generalized, documented, tested and upstreamed
      # similar to https://github.com/NixOS/nix/pull/12044
      patches = a.patches ++ [ ./expose_apis.patch ];
      # tests/functional/repl.sh.test is failing in CI
      doInstallCheck = stdenv.hostPlatform.system == "x86_64-linux";
    }))
    nlohmann_json
    libsodium
    boost
  ];

  cargoLock = {
    lockFile = ./Cargo.lock;
  };
}
