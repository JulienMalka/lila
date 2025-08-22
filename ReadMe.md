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

At the time of writing only reports on run-time closures are supported.
Reporting is experimental and still expected to evolve, change, and
grow support for build-time closures as well.

#### Defining a report

You define a report by uploading a JSON CycloneDX SBOM as produced by
[nix-runtime-tree-to-sbom](https://codeberg.org/raboof/nix-runtime-tree-to-sbom):

```
$ nix-store -q --tree $(nix-build '<nixpkgs/nixos/release-combined.nix>' -A nixos.iso_gnome.x86_64-linux) > tree.txt
$ cat tree.txt | ~/dev/nix-runtime-tree-to-sbom/tree-to-cyclonedx.py > sbom.cdx.json
$ export HASH_COLLECTION_TOKEN=XYX # your token
$ curl -X PUT --data @sbom.cdx.json "http://localhost:8000/reports/gnome-iso-runtime" -H "Content-Type: application/json" -H "Authorization: Bearer $HASH_COLLECTION_TOKEN"
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
$ curl -X POST -G http://127.0.0.1:8000/link_patterns --data-urlencode 'pattern=samba.*' --data-urlencode 'link=https://github.com/NixOS/nixpkgs/issues/303436' -H 'Authorization: Bearer $HASH_COLLECTION_TOKEN'
```

## Related projects

* [nix-reproducible-builds-report](https://codeberg.org/raboof/nix-reproducible-builds-report/) aka `r13y`, which generates the reports at [https://reproducible.nixos.org](https://reproducible.nixos.org). Ideally the [reporting](https://github.com/JulienMalka/nix-hash-collection/issues/9) feature can eventually replace the reports there.
* [rebuilderd](https://github.com/kpcyrd/rebuilderd) provides distribution-agnostic container-based rebuild infrastructure. There is some [preliminary Nix support](https://github.com/kpcyrd/rebuilderd/pull/142) but it is geared towards 'packages' rather than 'derivations' and that data model mismatch is somewhat awkward.
* [trustix](https://github.com/nix-community/trustix) has somewhat similar goals, but is more ambitious: `nix-hash-collection` only aims for something simple in the short term, just basically CRUD collection of hashes and some simple scripts around it. `trustix` has a more elaborate design with multiple transparency logs that are self-hosted by the attesters, and aims to support more advanced use cases, such as showing the aggregating system is not 'lying by omission' and perhaps showing that submitters aren't providing contradicting statements.
