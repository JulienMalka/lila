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
    """
    if not attestations:
        return {
            "status": "pending",
            "num_outputs": 0,
            "attestation_count": 0,
            "unique_hashes": 0
        }

    # Group attestations by output_path, tracking both hashes and users
    outputs = {}
    for a in attestations:
        output_path = a.output_path
        if output_path not in outputs:
            outputs[output_path] = {"hashes": set(), "users": set()}
        outputs[output_path]["hashes"].add(a.output_hash)
        outputs[output_path]["users"].add(a.user_id)

    attestation_count = len(attestations)
    num_outputs = len(outputs)

    # Check each output's reproducibility
    output_statuses = []
    for output_path, data in outputs.items():
        unique_users = len(data["users"])
        unique_hashes = len(data["hashes"])
        if unique_hashes > 1:
            # Different hashes means not reproducible (even from same user)
            output_statuses.append("not_reproducible")
        elif unique_users < 2:
            # Need at least 2 different users to confirm reproducibility
            output_statuses.append("pending")
        else:
            output_statuses.append("reproducible")

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
    total_unique_hashes = sum(len(data["hashes"]) for data in outputs.values())

    return {
        "status": status,
        "num_outputs": num_outputs,
        "attestation_count": attestation_count,
        "unique_hashes": total_unique_hashes
    }


def get_output_path_status(attestations):
    """
    Determine reproducibility status for a single output path based on its attestations.
    """
    if not attestations:
        return {
            "status": "pending",
            "attestation_count": 0,
            "unique_hashes": 0,
            "unique_users": 0
        }

    attestation_count = len(attestations)
    unique_hashes = len(set(a.output_hash for a in attestations))
    unique_users = len(set(a.user_id for a in attestations))

    if unique_hashes > 1:
        # Different hashes means not reproducible (even from same user)
        status = "not_reproducible"
    elif unique_users < 2:
        # Need at least 2 different users to confirm reproducibility
        status = "pending"
    else:
        # Multiple users, all got the same hash
        status = "reproducible"

    return {
        "status": status,
        "attestation_count": attestation_count,
        "unique_hashes": unique_hashes,
        "unique_users": unique_users
    }


def get_evaluation_output_paths(db: Session, evaluation_id: int) -> list[str]:
    """Get list of output path strings for an evaluation."""
    from . import models
    eval_output_paths = (
        db.query(models.EvaluationOutputPath)
        .filter(models.EvaluationOutputPath.evaluation_id == evaluation_id)
        .all()
    )
    return [e.output_path for e in eval_output_paths]


def fetch_attestations_grouped(db: Session, output_paths: list[str], eager_load_derivation: bool = False) -> dict:
    """
    Fetch attestations for output paths and group them by path.

    Returns dict mapping output_path -> list of attestations
    """
    from . import models
    from sqlalchemy.orm import joinedload

    if not output_paths:
        return {}

    query = db.query(models.Attestation).filter(
        models.Attestation.output_path.in_(output_paths)
    )
    if eager_load_derivation:
        query = query.options(joinedload(models.Attestation.derivation))

    all_attestations = query.all()

    attestations_by_path = {}
    for att in all_attestations:
        if att.output_path not in attestations_by_path:
            attestations_by_path[att.output_path] = []
        attestations_by_path[att.output_path].append(att)

    return attestations_by_path


def calculate_output_path_stats(attestations_by_path: dict, output_paths: list[str]) -> dict:
    """
    Calculate reproducibility stats summary for a set of output paths.

    Returns dict with 'reproducible', 'not_reproducible', 'pending' counts.
    """
    stats = {"reproducible": 0, "not_reproducible": 0, "pending": 0}
    for output_path in output_paths:
        attestations = attestations_by_path.get(output_path, [])
        status_info = get_output_path_status(attestations)
        stats[status_info["status"]] += 1
    return stats
