Nix Hash Collection
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

## Related projects

* [nix-reproducible-builds-report](https://codeberg.org/raboof/nix-reproducible-builds-report/) aka `r13y`, which generates the reports at [https://reproducible.nixos.org](https://reproducible.nixos.org). Ideally the [reporting](https://github.com/JulienMalka/nix-hash-collection/issues/9) feature can eventually replace the reports there.
* [rebuilderd](https://github.com/kpcyrd/rebuilderd) provides distribution-agnostic container-based rebuild infrastructure. There is some [preliminary Nix support](https://github.com/kpcyrd/rebuilderd/pull/142) but it is geared towards 'packages' rather than 'derivations' and that data model mismatch is somewhat awkward.
* [trustix](https://github.com/nix-community/trustix) has somewhat similar goals, but is more ambitious: `nix-hash-collection` only aims for something simple in the short term, just basically CRUD collection of hashes and some simple scripts around it. `trustix` has a more elaborate design with multiple transparency logs that are self-hosted by the attesters, and aims to support more advanced use cases, such as showing the aggregating system is not 'lying by omission' and perhaps showing that submitters aren't providing contradicting statements.
