{ nixVersions }:

(nixVersions.git.appendPatches [
  ./nix-expose-apis.patch
])
