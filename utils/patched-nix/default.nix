{ pkgs }:

(pkgs.nixVersions.git.appendPatches [
  ./nix-expose-apis.patch
  ./nix-fix-repl-test.patch
])
