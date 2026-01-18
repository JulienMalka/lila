# Hacking on and contributing to lila

Contributions are very welcome! You can simply open a PR, but when you're
planning a larger contribution it might be wise to discuss your approach
in an issue to avoid disappointment later.

## Web interface

Enter the development environment with `nix develop`.

### Initializing a development database

Run `alembic upgrade head` in `web` and run `./create_user myusername mytoken` to add a user

### Running

Run the server with `uvicorn web:app --reload`

### Testing

Run `pytest`

## Utilities

Enter the development environment with `nix develop`, `cd utils`, `cargo build`.
