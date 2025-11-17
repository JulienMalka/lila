"""
Derivation API routes
"""
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..common import get_db

router = APIRouter()


def get_drv_recap_or_404(session, drv_hash, full) -> schemas.DerivationAttestation:
    """Get derivation attestation summary or full details"""
    drv = session.query(models.Derivation).filter_by(drv_hash=drv_hash).one_or_none()
    if drv is None:
        raise HTTPException(status_code=404, detail="Not found")

    attestations = drv.attestations
    if (full):
        return attestations

    attestation_outputs = defaultdict(dict)
    for attestation in attestations:
        if attestation.output_hash not in attestation_outputs[attestation.output_path].keys():
            attestation_outputs[attestation.output_path][attestation.output_hash] = 1
        else:
            attestation_outputs[attestation.output_path][attestation.output_hash] += 1

    return attestation_outputs


@router.get("/")
def get_derivations(db: Session = Depends(get_db)) -> schemas.DerivationList:
    """List all derivations"""
    return db.query(models.Derivation).all()


@router.get("/{drv_hash}")
def get_drv(drv_hash: str,
            full: bool = False,
            db: Session = Depends(get_db),
):
    """Get a specific derivation with its attestation summary"""
    return get_drv_recap_or_404(db, drv_hash, full)
