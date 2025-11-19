{
  description = "Test flake with predictable FOD for Lila tests";

  outputs = { self, nixpkgs }: {
    packages.x86_64-linux = {
      # A simple Fixed Output Derivation - predictable and doesn't need building
      hello-src = nixpkgs.legacyPackages.x86_64-linux.fetchurl {
        url = "https://ftp.gnu.org/gnu/hello/hello-2.12.1.tar.gz";
        sha256 = "sha256-jZkUKv2SV28wsM18tCqNxoCZmLxdYH2Idh9RLibH2yA=";
      };

      # Another FOD
      curl-src = nixpkgs.legacyPackages.x86_64-linux.fetchurl {
        url = "https://curl.se/download/curl-8.4.0.tar.gz";
        sha256 = "sha256-4NEP7NwQ8196U10h2g3WYY7qPc+5Vs72R4SjP/9gWl0=";
      };

      # A trivial derivation that's easy to evaluate
      test-derivation = nixpkgs.legacyPackages.x86_64-linux.writeText "test.txt" "Hello from Lila test!";
    };
  };
}
