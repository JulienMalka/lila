{ 
  pkgs ? import <nixpkgs> {},
  # path of the nixpkgs tree you want to inspect
  nixpkgs-under-test,
  version,
  revCount,
  rev,
  shortRev,
  type ? "graphical",
  system ? "x86_64-linux",
  stableBranch ? false,
}:

let
  configuration = {};
  versionModule =
    { config, ...}:
    {
      system.nixos.versionSuffix =
        (if stableBranch then "." else "pre") + "${revCount}.${shortRev}";
        system.nixos.revision = rev;
        system.stateVersion = config.system.nixos.release;
    };
  module = "${nixpkgs-under-test}/nixos/modules/installer/cd-dvd/installation-cd-${type}-combined.nix";
  rest = {};
  nixos-config = import "${nixpkgs-under-test}/nixos/lib/eval-config.nix" {
    inherit system;
    modules = [
      configuration
      versionModule
      module
      rest
    ];
  };
in
pkgs.stdenv.mkDerivation {
  name = "iso-contents-nixos-${type}-${version}pre${revCount}.${shortRev}-${system}.iso";
  propagatedBuildInputs = [
    nixos-config.config.isoImage.storeContents
  ];
  # We just want to propagate the inputs which happens during fixup
  phases = [ "fixupPhase" ];
}
