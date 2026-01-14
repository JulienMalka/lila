# How to deploy your own lila server

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
  services.lila = {
    enable = true;
    nginx = null;
  };
```

For more details, feel free to inspect the source of the module.

To create a new user, see the `create_user` script.

For more information on operating the instance see [`OPERATING.md`](./OPERATING.md)
