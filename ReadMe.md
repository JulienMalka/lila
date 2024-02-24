Nix Hash Collection
===============================

(WIP)

Software to centralize build-output hashes from several builders.

Composed of 2 parts:
1) A post-build-hook
2) A server to aggregate the results


TODO:
- [ ] derivation/hash endpoint should answer the hashes of all reports in an aggregated way
- [ ] provide post-build-hook
- [ ] have token passed in post
- [ ] method to ingest hydra's results
- [ ] catch all sort of errors
