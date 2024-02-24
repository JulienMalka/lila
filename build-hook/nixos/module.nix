inputs: self:
{ config, lib, pkgs, ... }:
let 
  cfg = config.services.hash-collection;
  queued-build-hook = inputs.queued-build-hook.packages.${pkgs.system}.queued-build-hook;
  build-hook = self.packages.${pkgs.system}.build-hook;
in with lib;
{
  options.services.hash-collection = {

    enable = mkEnableOption "hash-collection";

    retryInterval = mkOption {
      description = mdDoc ''
        The number of seconds between attempts to run the hook for a package after an initial failure.
      '';
      type = types.int;
      default = 1;
    };

    retries = mkOption {
      description = mdDoc ''
        The maximum number of attempts that will be made to run the hook for a package before giving up and dropping the task altogether.
      '';
      type = types.int;
      default = 5;
    };

    concurrency = mkOption {
      description = mdDoc ''
        Sets the maximum number of tasks that can be executed simultaneously.
        By default it is set to 0 which means there is no limit to the number of tasks that can be run concurrently.
      '';
      type = types.int;
      default = 0;
    };

    collection-url = mkOption {
      description = mdDoc ''
        URL of the collection server
      '';
      type = types.str;
    };

    tokenFile = mkOption {
      description = mdDoc ''
        Path to your identification token
        '';
      type = types.path;
  };
};

    config = mkIf cfg.enable {

      nix.settings.post-build-hook =
        let
          enqueueScript = pkgs.writeShellScriptBin "enqueue-package" ''${queued-build-hook}/bin/queued-build-hook queue --socket "/var/lib/nix/async-nix-post-build-hook.sock"'';
        in
        "${enqueueScript}/bin/enqueue-package";


      systemd.sockets = {
        async-nix-post-build-hook = {
          description = "Async nix post build hooks socket";
          wantedBy = [ "sockets.target" ];
          socketConfig = {
            ListenStream = "/var/lib/nix/async-nix-post-build-hook.sock";
            SocketMode = "0660";
            SocketUser = "root";
            SocketGroup = "nixbld";
            Service = "async-nix-post-build-hook.service";
          };
        };
      };

      systemd.services.nix-hash-collection-build-hook = {
        description = "Report build outputs";
        wantedBy = [ "multi-user.target" ];
        requires = [
          "async-nix-post-build-hook.socket"
        ];
        script = ''
          set -euo pipefail
          shopt -u nullglob
          # Load all credentials into env if they are in UPPER_SNAKE form.
          export $HASH_COLLECTION_TOKEN=$(< "$CREDENTIALS_DIRECTORY/token")"
          exec ${cfg.package}/bin/queued-build-hook daemon --hook ${build-hook} --retry-interval ${toString cfg.retryInterval} --retry-interval ${toString cfg.retries} --concurrency ${toString cfg.concurrency} 
        '';
        serviceConfig = {
          Environment = [
            "HASH_COLLECTION_SERVER=${cfg.collection-url}"
          ];
          DynamicUser = true;
          User = "queued-build-hook";
          Group = "queued-build-hook";
          LoadCredential = [
            "token:${toString cfg.tokenFile}"
          ];
          KillMode = "process";
          Restart = "on-failure";
          FileDescriptorStoreMax = 1;
        };
      };
    };

  }
