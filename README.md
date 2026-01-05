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

### Jobsets and Evaluations

Lila organizes reproducibility tracking using **jobsets** and **evaluations**:

- A **jobset** represents a build configuration or project you want to track (e.g., "nixpkgs-unstable", "my-project")
- An **evaluation** is a specific snapshot of builds within a jobset, defined by a CycloneDX SBOM

This structure allows you to track reproducibility over time and compare different evaluation runs.

#### Creating a jobset

```bash
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ curl -X POST "http://localhost:8000/api/jobsets" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" \
  -d '{
    "name": "nixpkgs-unstable",
    "description": "NixOS unstable channel reproducibility tracking",
    "enabled": true
  }'
```

#### Uploading an evaluation

Once you have a jobset, you can upload evaluations to it. An evaluation contains a CycloneDX SBOM defining which derivations to track.

Run-time reports have the highest signal-to-noise ratio, as they only
include output paths that actually show up in the resulting artefact.
These may however miss artifacts that are copied from a build-time
dependency into the runtime.

Reports of the build-time closure will also include those - but also
derivations that are only 'used' during the build process and whose
output does not appear in the resulting artifact - such as tools only
used during the 'check' phase.

##### Build-time closure evaluation

```bash
$ DRV_PATH=$(nix-instantiate '<nixpkgs>' -A diffoscope)
$ nix run git+https://codeberg.org/raboof/nix-build-sbom --no-write-lock-file -- $DRV_PATH --skip-without-deriver > build-closure-sbom.cdx.json
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ JOBSET_ID=1 # replace with your jobset ID
$ curl -X PUT "http://localhost:8000/api/jobsets/$JOBSET_ID/upload-evaluation/$REV" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" \
  --data @build-closure-sbom.cdx.json
```

##### Runtime evaluation

You define an evaluation of a derivations' runtime dependencies by uploading a JSON CycloneDX SBOM as produced by
[nix-runtime-tree-to-sbom](https://codeberg.org/raboof/nix-runtime-tree-to-sbom).

Creating reports like this relies on Nix's built-in mechanism for
[determining runtime references](https://nix.dev/manual/nix/2.32/store/building.html#processing-outputs).
This may under-count the builds that are 'interesting' to rebuild, as it
will not rebuild derivations whose output is copied into a runtime
dependency. This means it gives good signal-to-noise ratio, but it remains
important to do 'actual' clean-room rebuilds to gain additional confidence.

###### Runtime evaluation of an arbitrary derivation

```bash
$ DRV_PATH=$(nix-instantiate '<nixpkgs>' -A diffoscope)
$ nix run git+https://codeberg.org/raboof/nix-build-sbom --no-write-lock-file -- $DRV_PATH --skip-without-deriver --include-outputs all > /tmp/build-closure-sbom.cdx.json
$ nix-store -q --tree $(nix-build '<nixpkgs>' -A diffoscope) > /tmp/tree.txt
$ cat /tmp/tree.txt | nix run git+https://codeberg.org/raboof/nix-runtime-tree-to-sbom --no-write-lock-file -- --skip-without-deriver --include-drv-paths-from /tmp/build-closure-sbom.cdx.json > /tmp/sbom.cdx.json
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ JOBSET_ID=1 # replace with your jobset ID
$ curl -X PUT "http://localhost:8000/api/jobsets/$JOBSET_ID/upload-evaluation/$REV" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" \
  --data @/tmp/sbom.cdx.json
```

###### Runtime evaluation of an installation ISO

Because the derivations that are part of the ISO are copied into the
ISO, they [no longer](https://github.com/NixOS/nixpkgs/pull/425700) show
up as runtime dependencies. To get an evaluation for the derivations that go into
a given installation ISO:

Check out a 'clean' checkout of nixpkgs:

```
$ cd /path/to/nixpkgs
$ git status --ignored --short | tr -d \! | xargs rm
$ find . -type d -empty -delete
```

Then:

```
$ REV=$(git log -1 --pretty=format:%h)
$ DRV_PATH=$(nix-instantiate /path/to/lila/installation-iso-store-contents.nix --argstr nixpkgs-under-test $(pwd) --argstr version $(cat lib/.version) --argstr revCount $(git rev-list $(git log -1 --pretty=format:%h) | wc -l) --argstr shortRev $(git log -1 --pretty=format:%h) --argstr rev $(git rev-parse HEAD))
$ nix run git+https://codeberg.org/raboof/nix-build-sbom --no-write-lock-file -- $DRV_PATH --skip-without-deriver --include-outputs all > /tmp/build-closure-sbom.cdx.json
$ OUT_PATH=$(nix-build $DRV_PATH)
$ nix-store -q --tree $OUT_PATH > /tmp/tree.txt
$ cat /tmp/tree.txt | nix run git+https://codeberg.org/raboof/nix-runtime-tree-to-sbom --no-write-lock-file -- --skip-without-deriver --include-drv-paths-from /tmp/build-closure-sbom.cdx.json > /tmp/sbom.cdx.json
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ export JOBSET_ID=XYX # the jobset this is part of
$ curl -X PUT "http://localhost:8000/api/jobsets/$JOBSET_ID/upload-evaluation/$REV" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HASH_COLLECTION_TOKEN" \
  --data @/tmp/sbom.cdx.json
```

#### Populating an evaluation

If you want to populate an evaluation with hashes from different builders (e.g. from
cache.nixos.org and from your own rebuilds), use separate tokens for the different
sources.

##### With hashes from cache.nixos.org

```bash
$ nix shell .#utils
$ export HASH_COLLECTION_SERVER=XYX # your token for the cache.nixos.org import
$ export HASH_COLLECTION_TOKEN=XYX # your token for the cache.nixos.org import
$ export HASH_COLLECTION_EVALUATION=XXX
$ copy-from-cache
```

This script is still very much WIP, and will enter an infinite loop retrying failed fetches.

##### By rebuilding

Make sure you have the post-build hook and diff hook configured as documented above.

You have to make sure all derivations are available for building on your system.
This can be done by `nix-instantiate`-ing the build definition. Making this easy
by including this information in the evaluation definition will be part of [#45](https://github.com/JulienMalka/lila/issues/45).

```bash
$ nix shell github:JulienMalka/lila#utils
$ export HASH_COLLECTION_TOKEN=XYX # your token for the cache.nixos.org import
$ export HASH_COLLECTION_SERVER=http://localhost:8000
$ export HASH_COLLECTION_EVALUATION=123 # evaluation ID
$ export MAX_CORES=8
$ rebuilder
```

This will schedule `MAX_CORES` jobs in parallel, to keep the nix daemon
queue saturated. It will not retry failures, and complete once it has
attempted a rebuild for each package in the evaluation.

#### Defining links

```
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ curl -X POST -G http://127.0.0.1:8000/api/link_patterns --data-urlencode 'pattern=samba.*' --data-urlencode 'link=https://github.com/NixOS/nixpkgs/issues/303436' -H "Authorization: Bearer $HASH_COLLECTION_TOKEN"
```

## Related projects

* [nix-reproducible-builds-report](https://codeberg.org/raboof/nix-reproducible-builds-report/) aka `r13y`, which generates the reports at [https://reproducible.nixos.org](https://reproducible.nixos.org). Ideally the [reporting](https://github.com/JulienMalka/nix-hash-collection/issues/9) feature can eventually replace the reports there.
* [rebuilderd](https://github.com/kpcyrd/rebuilderd) provides distribution-agnostic container-based rebuild infrastructure. There is some [preliminary Nix support](https://github.com/kpcyrd/rebuilderd/pull/142) but it is geared towards 'packages' rather than 'derivations' and that data model mismatch is somewhat awkward.
* [trustix](https://github.com/nix-community/trustix) has somewhat similar goals, but is more ambitious: `nix-hash-collection` only aims for something simple in the short term, just basically CRUD collection of hashes and some simple scripts around it. `trustix` has a more elaborate design with multiple transparency logs that are self-hosted by the attesters, and aims to support more advanced use cases, such as showing the aggregating system is not 'lying by omission' and perhaps showing that submitters aren't providing contradicting statements.
