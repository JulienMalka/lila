"""
Common utilities for the application
Provides: database sessions, authentication, templates
"""
import pathlib
import typing as t
from fastapi import Depends, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud
from .db import SessionLocal

# Database dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication
get_bearer_token = HTTPBearer(auto_error=False)

async def get_token(
    auth: t.Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
) -> str:
    """Extract bearer token from Authorization header"""
    if auth is not None:
        return auth.credentials
    else:
        return ""

async def get_user(
    token: str = Depends(get_token),
    db: Session = Depends(get_db)
) -> int:
    """Get user ID from token, raise 401 if invalid"""
    user_id = crud.get_user_with_token(db, token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user_id

# Templates
thispath = pathlib.Path(__file__).parent.resolve()
templates = Jinja2Templates(directory=str(thispath / "templates"))


def get_matching_links(drv_hash: str, link_patterns) -> list:
    """Find all link patterns that match the derivation hash."""
    import re
    matching = []
    for lp in link_patterns:
        try:
            if re.search(lp.pattern, drv_hash):
                matching.append({"pattern": lp.pattern, "link": lp.link})
        except re.error:
            # Skip invalid regex patterns
            pass
    return matching


def get_derivation_status(attestations):
    """
    Determine reproducibility status for a derivation based on its attestations.

    Groups attestations by output_path and checks if each output is reproducible.
    A derivation is reproducible only if ALL outputs are reproducible.

    Returns: dict with 'status', 'num_outputs', 'attestation_count', 'unique_hashes'
    """
    if not attestations:
        return {
            "status": "pending",
            "num_outputs": 0,
            "attestation_count": 0,
            "unique_hashes": 0
        }

    # Group attestations by output_path
    outputs = {}
    for a in attestations:
        output_path = a.output_path
        if output_path not in outputs:
            outputs[output_path] = set()
        outputs[output_path].add(a.output_hash)

    attestation_count = len(attestations)
    num_outputs = len(outputs)

    # Check each output's reproducibility
    # Need at least 2 attestations per output to determine status
    output_statuses = []
    for output_path, hashes in outputs.items():
        output_attestation_count = sum(1 for a in attestations if a.output_path == output_path)
        if output_attestation_count < 2:
            output_statuses.append("pending")
        elif len(hashes) == 1:
            output_statuses.append("reproducible")
        else:
            output_statuses.append("not_reproducible")

    # Determine overall status
    if all(s == "reproducible" for s in output_statuses):
        status = "reproducible"
    elif all(s == "pending" for s in output_statuses):
        status = "pending"
    elif any(s == "not_reproducible" for s in output_statuses):
        status = "not_reproducible"
    else:
        # Mix of pending and reproducible
        status = "pending"

    # Count unique hashes across all outputs (for display)
    unique_hashes = sum(len(hashes) for hashes in outputs.values())

    return {
        "status": status,
        "num_outputs": num_outputs,
        "attestation_count": attestation_count,
        "unique_hashes": unique_hashes
    }
