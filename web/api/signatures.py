"""
Signature/NAR info API routes
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models
from ..common import get_db

router = APIRouter()


@router.get("/{user_name}/{output_digest}.narinfo")
def nix_cache_info(
    user_name: str,
    output_digest: str,
    db: Session = Depends(get_db),
):
    """Nix cache info endpoint"""
    user = db.query(models.User).filter_by(name=user_name).one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    attestations = db.query(models.Attestation).filter_by(
        output_digest=output_digest,
        user_id=user.id
    ).all()

    if len(attestations) == 0:
        raise HTTPException(status_code=404, detail="Not found")

    attestation = attestations[0]
    derivation = db.query(models.Derivation).filter_by(id=attestation.drv_id).one_or_none()

    if derivation is None:
        deriver = ""
    else:
        deriver = f"Deriver: {derivation.drv_hash}.drv\n"

    return Response(
        content=f"""StorePath: /nix/store/{attestation.output_digest}-{attestation.output_name}
URL: no
NarHash: {attestation.output_hash}
NarSize: 1
{deriver}Sig: {attestation.output_sig}
""",
        media_type="text/x-nix-narinfo"
    )
