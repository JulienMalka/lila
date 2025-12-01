"""
Jobset view routes (HTML)
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..common import get_db, templates, get_evaluation_output_paths, fetch_attestations_grouped, calculate_output_path_stats

router = APIRouter()


@router.get("")
async def list_jobsets(request: Request, db: Session = Depends(get_db)):
    """List all jobsets"""
    jobsets = db.query(models.Jobset).all()

    # Add latest evaluation to each jobset
    for jobset in jobsets:
        jobset.latest_eval = (
            db.query(models.Evaluation)
            .filter_by(jobset_id=jobset.id)
            .order_by(models.Evaluation.uploaded_at.desc())
            .first()
        )

    return templates.TemplateResponse("jobsets.html", {
        "request": request,
        "jobsets": jobsets
    })


@router.get("/{jobset_id}")
async def get_jobset_detail(
    request: Request,
    jobset_id: int,
    db: Session = Depends(get_db)
):
    """Get jobset detail page"""
    jobset = db.query(models.Jobset).filter_by(id=jobset_id).first()
    if not jobset:
        raise HTTPException(status_code=404, detail="Jobset not found")

    # Get evaluations for this jobset (ordered chronologically for charts)
    evaluations = (
        db.query(models.Evaluation)
        .filter_by(jobset_id=jobset_id)
        .order_by(models.Evaluation.uploaded_at.asc())
        .all()
    )

    # Calculate stats for each evaluation using the shared function
    # This data is used for both charts and table
    eval_stats = []
    chart_data = {
        'eval_numbers': [],
        'dates': [],
        'reproducible': [],
        'not_reproducible': [],
        'pending': [],
        'reproducible_pct': [],
        'not_reproducible_pct': [],
        'pending_pct': [],
    }

    for idx, evaluation in enumerate(evaluations, 1):
        output_path_list = get_evaluation_output_paths(db, evaluation.id)
        total = len(output_path_list)
        attestations_by_path = fetch_attestations_grouped(db, output_path_list)
        stats = calculate_output_path_stats(attestations_by_path, output_path_list)

        eval_stats.append({
            "evaluation": evaluation,
            "total": total,
            "reproducible": stats["reproducible"],
            "not_reproducible": stats["not_reproducible"],
            "pending": stats["pending"],
            "reproducible_pct": round(stats["reproducible"] / total * 100, 1) if total > 0 else 0,
        })

        # Add to chart data
        if total > 0 and evaluation.uploaded_at:
            chart_data['eval_numbers'].append(idx)
            chart_data['dates'].append(evaluation.uploaded_at.strftime('%Y-%m-%d'))
            chart_data['reproducible'].append(stats["reproducible"])
            chart_data['not_reproducible'].append(stats["not_reproducible"])
            chart_data['pending'].append(stats["pending"])
            chart_data['reproducible_pct'].append(round(stats["reproducible"] / total * 100, 1))
            chart_data['not_reproducible_pct'].append(round(stats["not_reproducible"] / total * 100, 1))
            chart_data['pending_pct'].append(round(stats["pending"] / total * 100, 1))

    # Reverse for display (most recent first in table)
    eval_stats.reverse()

    return templates.TemplateResponse("jobset_detail.html", {
        "request": request,
        "jobset": jobset,
        "evaluations": eval_stats,
        "chart_data": json.dumps(chart_data)
    })
