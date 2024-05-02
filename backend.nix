{
  lib,
  buildPythonPackage,
  pydantic,
  fastapi,
  hatchling,
  sqlalchemy,
}:

buildPythonPackage {
  pname = "lila";
  version = "unstable-2024-05-01";
  pyproject = true;

  src = ./.;

  nativeBuildInputs = [ hatchling ];

  propagatedBuildInputs = [
    fastapi
    pydantic
    sqlalchemy
  ];

  meta = with lib; {
    description = "Collect hashes of Nix build to test for reproducibility";
    homepage = "https://github.com/JulienMalka/lila/";
    license = licenses.eupl12;
    maintainers = with maintainers; [
      julienmalka
      raboof
    ];
    mainProgram = "lila";
    platforms = platforms.all;
  };
}
