"""
Evaluation API routes
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..common import get_db

router = APIRouter()


@router.get("/{evaluation_id}", response_model=schemas.EvaluationDetail)
def get_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
):
    """Get evaluation details"""
    evaluation = crud.get_evaluation(db, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluation


@router.get("", response_model=list[schemas.EvaluationResponse])
def list_all_evaluations(db: Session = Depends(get_db)):
    """List all evaluations across all jobsets"""
    return crud.list_evaluations(db)


@router.get("/{evaluation_id}/derivations")
def get_evaluation_derivations(
    evaluation_id: int,
    db: Session = Depends(get_db),
):
    """Get all derivations for an evaluation with their metadata"""
    evaluation = crud.get_evaluation(db, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # Get all evaluation_derivations for this evaluation
    eval_drvs = db.query(models.EvaluationDerivation)\
        .filter_by(evaluation_id=evaluation_id)\
        .all()

    result = []
    for eval_drv in eval_drvs:
        derivation = eval_drv.derivation
        result.append({
            "derivation_id": derivation.id,
            "drv_hash": derivation.drv_hash,
            "attribute_path": eval_drv.attribute_path,
            "output_paths": json.loads(eval_drv.output_paths) if eval_drv.output_paths else {},
        })

    return result
