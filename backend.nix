{
  lib,
  buildPythonPackage,
  jinja2,
  pydantic,
  fastapi,
  hatchling,
  sqlalchemy,
  alembic,
  pytest,
  httpx,
}:

buildPythonPackage {
  pname = "lila";
  version = "unstable-2024-05-01";
  pyproject = true;

  src = ./.;

  nativeBuildInputs = [ hatchling ];

  checkPhase = ''
    python -m pytest web/test_api.py
  '';

  checkInputs = [
    pytest
    httpx
  ];
  
  propagatedBuildInputs = [
    fastapi
    pydantic
    sqlalchemy
    jinja2
    alembic
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
