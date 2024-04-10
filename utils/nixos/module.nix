queued-build-hook-module:
{ config, lib, pkgs, ... }:
let
  cfg = config.services.hash-collection;
  build-hook = pkgs.callPackage ../. { };
in
with lib;
{

  imports = [ queued-build-hook-module ];

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

    secretKeyFile = mkOption {
      description = mdDoc ''
        Path to your secret key for signing builds
      '';
      type = types.path;
    };
  };

  config = mkIf cfg.enable {

    queued-build-hook = {
      inherit (cfg) retries concurrency retryInterval;
      enable = true;
      postBuildScript = "${build-hook}/bin/build-hook";
      credentials = {
        HASH_COLLECTION_TOKEN = toString cfg.tokenFile;
        HASH_COLLECTION_SECRET_KEY = toString cfg.secretKeyFile;
      };

    };

    systemd.services.async-nix-post-build-hook.serviceConfig.Environment = [ "HASH_COLLECTION_SERVER=${cfg.collection-url}" ];

  };

}
