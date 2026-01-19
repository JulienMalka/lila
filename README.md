lila
===============================
## Introduction

This repository provides a set of tools that can be used to create a hash collection mechanism for Nix.
A hash collection infrastructure is used to collect and compare build outputs from different trusted builders.

This project is composed of three parts:

1) A post-build-hook that publishes a build hash attestation after each local Nix build
2) A server to aggregate these hashes
3) Utilities, for example to trigger rebuilds

## Viewing results

A public instance of the collection service can be found at https://reproducibility.nixos.social/

## Providing rebuild attestations

If you want to contribute rebuild attestations, contact Arnout ([@raboof@merveilles.town](https://merveilles.town/@raboof), `@raboof:matrix.org`, arnout at engelen.eu) with your desired username to receive a token.

Set up your keys with:

    nix key generate-secret --key-name username-hash-collection > /etc/hash-collection-secret.key


Add `lila` as an input in your `flake.nix`:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    lila = {
      url = "git+https://github.com/nix-community/lila";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  }
```

Include the module into your NixOS system:

```
  outputs = { self, nixpkgs, lila }@attrs: {
    nixosConfigurations.mysystem = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      specialArgs = attrs;
      modules = [ 
        ./configuration.nix
        lila.nixosModules.hash-collection
      ];
    };
  };
}
```

And configure the service in your `configuration.nix`:

```nix
  # https://github.com/nix-community/lila/issues/1#issuecomment-1964183075
  systemd.services.async-nix-post-build-hook = {
    environment.HOME = "/var/lib/async-nix-post-build-hook";
  };

  services.hash-collection = {
    enable = true;
    collection-url = "https://reproducibility.nixos.social";
    tokenFile = "/etc/hash-collection.token";
    secretKeyFile = "/etc/hash-collection-secret.key";
  };
```

The next step is to select an 'evaluation' to rebuild and trigger rebuilds of
those packages.

You'll have to make sure all derivations (i.e. the build definitions) are available
for building on your system. This can be done by `nix-instantiate`-ing the build definition. 
For now coordinate [on Matrix](https://matrix.to/#/#reproducible-builds:nixos.org).
Making this easy by including this information in the evaluation definition
will be part of [#45](https://github.com/JulienMalka/lila/issues/45).

```bash
$ nix shell github:nix-community/lila#utils
$ export HASH_COLLECTION_TOKEN=XYX # your token for the cache.nixos.org import
$ export HASH_COLLECTION_SERVER=http://localhost:8000
$ export HASH_COLLECTION_EVALUATION=123 # evaluation ID
$ export MAX_CORES=8
$ rebuilder
```

This will schedule `MAX_CORES` jobs in parallel, to keep the nix daemon
queue saturated. It will not retry failures, and complete once it has
attempted a rebuild for each package in the evaluation.

## Running your own lila server

See [`DEPLOYING.md`](./DEPLOYING.md) and [`OPERATING.md`](./OPERATING.md)

## Contributing to lila

See [`CONTRIBUTING.md`](./CONTRIBUTING.md)

## Related projects

* [nix-reproducible-builds-report](https://codeberg.org/raboof/nix-reproducible-builds-report/) aka `r13y`, used to generate the reports at [https://reproducible.nixos.org](https://reproducible.nixos.org).
* [rebuilderd](https://github.com/kpcyrd/rebuilderd) provides distribution-agnostic container-based rebuild infrastructure. There is some [preliminary Nix support](https://github.com/kpcyrd/rebuilderd/pull/142) but it is geared towards 'packages' rather than 'derivations' and that data model mismatch is somewhat awkward.
* [trustix](https://github.com/nix-community/trustix) has somewhat similar goals, but is more ambitious: `nix-hash-collection` only aims for something simple in the short term, just basically CRUD collection of hashes and some simple scripts around it. `trustix` has a more elaborate design with multiple transparency logs that are self-hosted by the attesters, and aims to support more advanced use cases, such as showing the aggregating system is not 'lying by omission' and perhaps showing that submitters aren't providing contradicting statements.
