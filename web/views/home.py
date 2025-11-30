"""
Home page view route
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import models
from ..common import get_db, templates

router = APIRouter()


@router.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    """Home page"""
    stats = {
        "jobsets": db.query(models.Jobset).count(),
        "evaluations": db.query(models.Evaluation).count(),
        "derivations": db.query(models.Derivation).count(),
        "attestations": db.query(models.Attestation).count(),
    }

    # Get active jobsets (limit to 5 for homepage)
    active_jobsets = db.query(models.Jobset)\
        .filter_by(enabled=True)\
        .order_by(models.Jobset.updated_at.desc())\
        .limit(5)\
        .all()

    # Add latest evaluation to each jobset
    for jobset in active_jobsets:
        jobset.latest_eval = (
            db.query(models.Evaluation)
            .filter_by(jobset_id=jobset.id)
            .order_by(models.Evaluation.id.desc())
            .first()
        )

    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "active_jobsets": active_jobsets
    })
