Nix Hash Collection
===============================

## Introduction

This repository aims to give a set of tools that can be used to create a hash collection mechanism for Nix. 
A hash collection infrastructure is used to collect and compare build outputs from different trusted builders.

This project is composed of two parts: 

1) A post-build-hook, that his a software running after each of Nix builds and in charge to report the hashes of the outputs
2) A server to aggregate the results

## Howto's

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
  };
```

