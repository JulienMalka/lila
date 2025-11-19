"""
Jobset API routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, evaluation_runner
from ..common import get_db, get_user

router = APIRouter()


@router.post("", response_model=schemas.JobsetResponse)
def create_jobset(
    jobset: schemas.JobsetCreate,
    user_id: int = Depends(get_user),
    db: Session = Depends(get_db),
):
    """Create a new jobset"""
    # Check if jobset with this name already exists
    existing = crud.get_jobset_by_name(db, jobset.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Jobset '{jobset.name}' already exists")

    new_jobset = crud.create_jobset(
        db,
        name=jobset.name,
        flakeref=jobset.flakeref,
        description=jobset.description,
        enabled=jobset.enabled
    )
    return new_jobset


@router.get("", response_model=list[schemas.JobsetResponse])
def list_jobsets(db: Session = Depends(get_db)):
    """List all jobsets"""
    return crud.list_jobsets(db)


@router.get("/{jobset_id}", response_model=schemas.JobsetResponse)
def get_jobset(
    jobset_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific jobset"""
    jobset = crud.get_jobset(db, jobset_id)
    if not jobset:
        raise HTTPException(status_code=404, detail="Jobset not found")
    return jobset


@router.put("/{jobset_id}", response_model=schemas.JobsetResponse)
def update_jobset(
    jobset_id: int,
    jobset_update: schemas.JobsetUpdate,
    user_id: int = Depends(get_user),
    db: Session = Depends(get_db),
):
    """Update a jobset"""
    updated = crud.update_jobset(
        db,
        jobset_id,
        name=jobset_update.name,
        flakeref=jobset_update.flakeref,
        description=jobset_update.description,
        enabled=jobset_update.enabled
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Jobset not found")
    return updated


@router.delete("/{jobset_id}")
def delete_jobset(
    jobset_id: int,
    user_id: int = Depends(get_user),
    db: Session = Depends(get_db),
):
    """Delete a jobset"""
    success = crud.delete_jobset(db, jobset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Jobset not found")
    return {"message": "Jobset deleted"}


@router.post("/{jobset_id}/evaluate", response_model=schemas.EvaluationResponse)
def trigger_evaluation(
    jobset_id: int,
    user_id: int = Depends(get_user),
    db: Session = Depends(get_db),
):
    """Trigger a new evaluation for a jobset"""
    try:
        evaluation = evaluation_runner.trigger_evaluation(db, jobset_id)
        return evaluation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/{jobset_id}/evaluations", response_model=list[schemas.EvaluationResponse])
def list_jobset_evaluations(
    jobset_id: int,
    db: Session = Depends(get_db),
):
    """List all evaluations for a jobset"""
    jobset = crud.get_jobset(db, jobset_id)
    if not jobset:
        raise HTTPException(status_code=404, detail="Jobset not found")

    return crud.list_evaluations(db, jobset_id=jobset_id)


@router.post("/{jobset_id}/enable")
def enable_jobset(
    jobset_id: int,
    user_id: int = Depends(get_user),
    db: Session = Depends(get_db),
):
    """Enable a jobset"""
    from .. import models
    jobset = db.query(models.Jobset).filter_by(id=jobset_id).first()
    if not jobset:
        raise HTTPException(status_code=404, detail="Jobset not found")

    jobset.enabled = True
    db.commit()
    return {"message": "Jobset enabled"}


@router.post("/{jobset_id}/disable")
def disable_jobset(
    jobset_id: int,
    user_id: int = Depends(get_user),
    db: Session = Depends(get_db),
):
    """Disable a jobset"""
    from .. import models
    jobset = db.query(models.Jobset).filter_by(id=jobset_id).first()
    if not jobset:
        raise HTTPException(status_code=404, detail="Jobset not found")

    jobset.enabled = False
    db.commit()
    return {"message": "Jobset disabled"}
