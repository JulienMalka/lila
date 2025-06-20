{
  config,
  pkgs,
  lib,
  modulesPath,
  ...
}:

let
  inherit (lib)
    literalExpression
    mkDefault
    mkEnableOption
    mkIf
    mkOption
    optional
    ;

  inherit (lib.types)
    attrsOf
    nullOr
    package
    port
    str
    submodule
    ;

  cfg = config.services.lila;
in

{
  options.services.lila = {
    enable = mkEnableOption "Lila";

    pythonEnv = mkOption {
      internal = true;
      visible = false;
      type = package;
      default = pkgs.python3.withPackages (ps: [
        ps.lila
        ps.uvicorn
        ps.psycopg2
      ]);

      example = literalExpression ''
        pkgs.python3.withPackages (ps: [
          ps.lila
          ps.uvicorn
          ps.psycopg2
        ]);
      '';
    };

    port = mkOption {
      type = nullOr port;
      default = 8007;
      description = "Port of the server (will be passed using --bind flag)";
    };

    settings = mkOption {
      type =

        submodule {
          freeformType = attrsOf str;
          options.SQLALCHEMY_DATABASE_URL = mkOption { description = "Database url"; };
        };
      description = "Settings to pass as environment variables";
    };

    domain = mkOption {
      type = str;
      description = "Hostname for reverse proxy config. To configure";
    };

    nginx = mkOption {
      type = nullOr (
        submodule (
          import (modulesPath + "/services/web-servers/nginx/vhost-options.nix") { inherit config lib; }
        )
      );
      example = literalExpression ''
        {
          serverAliases = [
            "lila.''${config.networking.domain}"
          ];
          # To enable encryption and let let's encrypt take care of certificate
          forceSSL = true;
          enableACME = true;
        }
      '';
      description = ''
        With this option, you can customize an nginx virtual host which already
        has sensible defaults for lila. If enabled, then by default, the
        serverName is ''${domain}, If this is set to null, no nginx virtualHost
        will be configured.
      '';
    };
  };

  config = mkIf cfg.enable {

    nixpkgs.overlays = [
      (self: super: {
        python3 = super.python3.override {
          packageOverrides = python-self: python-super: {
            lila = python-self.callPackage ../../backend.nix { };
          };
        };
      })
    ];

    services = {
      postgresql = mkIf (lib.hasPrefix "postgresql" cfg.settings.SQLALCHEMY_DATABASE_URL) {
        enable = true;
        ensureUsers = [
          {
            name = "lila";
            ensureDBOwnership = true;
          }
        ];
        ensureDatabases = [ "lila" ];
      };

      lila.settings.SQLALCHEMY_DATABASE_URL = mkDefault "postgresql+psycopg2:///lila?host=/run/postgresql";

      nginx = mkIf (cfg.nginx != null) {
        enable = true;
        virtualHosts.${cfg.domain} = cfg.nginx;
      };
    };

    systemd.services.lila = {
      environment = cfg.settings;
      path = [ cfg.pythonEnv ];
      script = "uvicorn lila:app --host 127.0.0.1 --port ${builtins.toString cfg.port}";
      serviceConfig = {
        User = "lila";
        DynamicUser = true;
      };
      wantedBy = [ "multi-user.target" ];
      wants = [ "postgresql.target" ];
      after = [
        "network.target"
        "postgresql.service"
      ];
    };
  };
}
