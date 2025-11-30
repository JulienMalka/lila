"""
Evaluation API routes
"""
import json
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..common import get_db, get_token

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
    output_paths = [op.output_path for op in evaluation.output_paths]
    return {
        "id": evaluation.id,
        "uploaded_at": evaluation.uploaded_at,
        "git_revision": evaluation.git_revision,
        "output_paths": output_paths
    }


@router.get("", response_model=list[schemas.EvaluationResponse])
def list_all_evaluations(db: Session = Depends(get_db)):
    """List all evaluations across all jobsets"""
    return crud.list_evaluations(db)





def report_elements(report):
    """Extract report elements with their properties"""
    paths = {}
    for component in report['components']:
        item = {}
        for prop in component['properties']:
            if prop['name'] == "nix:out_path":
                item['out_path'] = prop['value']
            elif prop['name'] == "nix:output_path":
                item['out_path'] = prop['value']
            elif prop['name'] == "nix:drv_path":
                item['drv_path'] = prop['value']
            elif prop['name'] == "nix:output":
                item['output'] = prop['value']
        if 'out_path' in item:
            paths[item['out_path']] = item
    return paths




@router.get("/{evaluation_id}/suggest")
def suggest_derivations_for_rebuilding(
    evaluation_id: int,
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    """Get suggested derivations for rebuilding from an evaluation"""
    evaluation = crud.get_evaluation(db, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    report_def = json.loads(evaluation.definition_sbom)
    # This part should be replaced by some qerying from evaluation_derivation table, but we are lacking output paths
    derivations = report_elements(report_def)
    user_id = crud.get_user_with_token(db, token)

    suggestions = crud.suggest(db, derivations, user_id)

    result = list(suggestions.values())
    random.shuffle(result)
    return result[:50]

