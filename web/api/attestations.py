"""
Attestation API routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..common import get_db, get_token

router = APIRouter()


@router.post("/attestation/{drv_hash}")
def record_attestation(
    drv_hash: str,
    output_sha256_map: list[schemas.OutputHashPair],
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    """Record a build attestation for a derivation"""
    user = crud.get_user_with_token(db, token)
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")

    crud.create_attestation(db, drv_hash, output_sha256_map, user)
    return {
        "Attestation accepted"
    }


@router.get("/attestations/by-output/{output_path}")
def attestations_by_out(output_path: str, db: Session = Depends(get_db)):
    """Get all attestations for a specific output path"""
    return db.query(models.Attestation).filter_by(output_path="/nix/store/"+output_path).all()
