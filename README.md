lila
===============================
## Introduction

This repository aims to give a set of tools that can be used to create a hash collection mechanism for Nix.
A hash collection infrastructure is used to collect and compare build outputs from different trusted builders.

This project is composed of two parts:

1) A post-build-hook, that his a software running after each of Nix builds and in charge to report the hashes of the outputs
2) A server to aggregate the results

## Howto's

### Keys

Set up your keys with:

- `nix key generate-secret --key-name username-hash-collection > secret.key`

### Server side

#### Create a user

Hashes reports are only allowed from trusted users, which are identified via a token.
To generate a token run `./create_user "username"`

#### Run the server

Run the server with `uvicorn web:app --reload`

### Client side

```nix
  services.hash-collection = {
    enable = true;
    collection-url = "server url";
    tokenFile = "/token/path";
    secretKeyFile = "/secret/key/path";
  };
```

### Reporting

Below are instructions for defining and populating reports.

Run-time reports have the highest signal-to-noise ratio, as they only
include output paths that actually show up in the resulting artefact.
These may however miss artifacts that are copied from a build-time
dependency into the runtime.

Reports of the build-time closure will also include those - but also
derivations that are only 'used' during the build process and whose
output does not appear in the resulting artifact - such as tools only
used during the 'check' phase.

#### Defining a report

##### Build-time closure reports

```
$ DRV_PATH=$(nix-instantiate '<nixpkgs>' -A diffoscope)
$ nix run git+https://codeberg.org/raboof/nix-build-sbom --no-write-lock-file -- $DRV_PATH --skip-without-deriver > build-closure-sbom.cdx.json
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ curl -X PUT --data @build-closure-sbom.cdx.json "http://localhost:8000/reports/123-some-derivation.drv-build-closure" -H "Content-Type: application/json" -H "Authorization: Bearer $HASH_COLLECTION_TOKEN"
```

##### Runtime reports

You define a report of a derivations' runtime dependencies by uploading a JSON CycloneDX SBOM as produced by
[nix-runtime-tree-to-sbom](https://codeberg.org/raboof/nix-runtime-tree-to-sbom).

Creating reports like this relies on Nix's built-in mechanism for
[determining runtime references](https://nix.dev/manual/nix/2.32/store/building.html#processing-outputs).
This may under-count the builds that are 'interesting' to rebuild, as it
will not rebuild derivations whose output is copied into a runtime
dependency. This means it gives good signal-to-noise ratio, but it remains
important to do 'actual' clean-room rebuilds to gain additional confidence.

###### Runtime report of an arbitrary derivation

```
$ DRV_PATH=$(nix-instantiate '<nixpkgs>' -A diffoscope)
$ nix run git+https://codeberg.org/raboof/nix-build-sbom --no-write-lock-file -- $DRV_PATH --skip-without-deriver --include-outputs all > /tmp/build-closure-sbom.cdx.json
$ nix-store -q --tree $(nix-build '<nixpkgs>' -A diffoscope) > /tmp/tree.txt
$ cat /tmp/tree.txt | nix run git+https://codeberg.org/raboof/nix-runtime-tree-to-sbom --no-write-lock-file -- --skip-without-deriver --include-drv-paths-from /tmp/build-closure-sbom.cdx.json > /tmp/sbom.cdx.json
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ curl -X PUT --data @/tmp/sbom.cdx.json "http://localhost:8000/reports/diffoscope-runtime" -H "Content-Type: application/json" -H "Authorization: Bearer $HASH_COLLECTION_TOKEN"
```

###### Runtime report of an installation ISO

Because the derivations that are part of the ISO are copied into the
ISO, they [no longer](https://github.com/NixOS/nixpkgs/pull/425700) show
up as runtime dependencies. To get a report for the derivations that go into
a given installation ISO:

Check out a 'clean' checkout of nixpkgs, notably not containing any files that would be ignored by git (you can check with `git status --ignored`) or empty directories (you can check with `find . -type d -empty`).

```
$ cd /path/to/nixpkgs
$ DRV_PATH=$(nix-instantiate /path/to/lila/installation-iso-store-contents.nix --argstr nixpkgs-under-test $(pwd) --argstr version $(cat lib/.version) --argstr revCount $(git rev-list $(git log -1 --pretty=format:%h) | wc -l) --argstr shortRev $(git log -1 --pretty=format:%h) --argstr rev $(git rev-parse HEAD))
$ nix run git+https://codeberg.org/raboof/nix-build-sbom --no-write-lock-file -- $DRV_PATH --skip-without-deriver --include-outputs all > /tmp/build-closure-sbom.cdx.json
$ OUT_PATH=$(nix-build $DRV_PATH)
$ nix-store -q --tree $OUT_PATH > /tmp/tree.txt
$ cat /tmp/tree.txt | nix run git+https://codeberg.org/raboof/nix-runtime-tree-to-sbom --no-write-lock-file -- --skip-without-deriver --include-drv-paths-from /tmp/build-closure-sbom.cdx.json > /tmp/sbom.cdx.json
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ curl -X PUT --data @/tmp/sbom.cdx.json "http://localhost:8000/reports/nixos-graphical-25.11pre873798.c9b6fb798541-x86_64-linux.iso-runtime" -H "Content-Type: application/json" -H "Authorization: Bearer $HASH_COLLECTION_TOKEN"
```

#### Populating the report

If you want to populate the report with hashes from different builders (e.g. from
cache.nixos.org and from your own rebuilds), use separate tokens for the different
sources.

##### With hashes from cache.nixos.org

```
$ nix shell .#utils
$ export HASH_COLLECTION_TOKEN=XYX # your token for the cache.nixos.org import
$ ./fetch-from-cache.sh
```

This script is still very much WIP, and will enter an infinite loop retrying failed fetches.

##### By rebuilding

Make sure you have the post-build hook and diff hook configured as documented above.

TODO you have to make sure all derivations are available for building on your system -
is there a smart way to do that?

```
$ export HASH_COLLECTION_TOKEN=XYX # your token for the cache.nixos.org import
$ ./rebuilder.sh
```

This script is still very much WIP, and will enter an infinite loop retrying failed fetches.
You can run multiple rebuilders in parallel.

#### Defining links

```
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ curl -X POST -G http://127.0.0.1:8000/link_patterns --data-urlencode 'pattern=samba.*' --data-urlencode 'link=https://github.com/NixOS/nixpkgs/issues/303436' -H "Authorization: Bearer $HASH_COLLECTION_TOKEN"
```

## Related projects

* [nix-reproducible-builds-report](https://codeberg.org/raboof/nix-reproducible-builds-report/) aka `r13y`, which generates the reports at [https://reproducible.nixos.org](https://reproducible.nixos.org). Ideally the [reporting](https://github.com/JulienMalka/nix-hash-collection/issues/9) feature can eventually replace the reports there.
* [rebuilderd](https://github.com/kpcyrd/rebuilderd) provides distribution-agnostic container-based rebuild infrastructure. There is some [preliminary Nix support](https://github.com/kpcyrd/rebuilderd/pull/142) but it is geared towards 'packages' rather than 'derivations' and that data model mismatch is somewhat awkward.
* [trustix](https://github.com/nix-community/trustix) has somewhat similar goals, but is more ambitious: `nix-hash-collection` only aims for something simple in the short term, just basically CRUD collection of hashes and some simple scripts around it. `trustix` has a more elaborate design with multiple transparency logs that are self-hosted by the attesters, and aims to support more advanced use cases, such as showing the aggregating system is not 'lying by omission' and perhaps showing that submitters aren't providing contradicting statements.
