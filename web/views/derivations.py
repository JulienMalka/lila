"""
Derivation view routes (HTML)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..common import get_db, templates, get_derivation_status, get_matching_links

router = APIRouter()


@router.get("")
async def list_derivations(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all derivations"""
    derivations = (
        db.query(models.Derivation)
        .order_by(models.Derivation.id.desc())
        .limit(limit)
        .all()
    )

    # Get attestation counts for each
    drv_stats = []
    for drv in derivations:
        drv_status = get_derivation_status(drv.attestations)
        drv_stats.append({
            "derivation": drv,
            "attestation_count": drv_status["attestation_count"],
            "unique_hashes": drv_status["unique_hashes"],
            "status": drv_status["status"]
        })

    return templates.TemplateResponse("derivations.html", {
        "request": request,
        "derivations": drv_stats
    })


@router.get("/{drv_hash}")
async def get_derivation_detail(
    request: Request,
    drv_hash: str,
    db: Session = Depends(get_db)
):
    """Get derivation detail page with all attestations"""
    derivation = db.query(models.Derivation).filter_by(drv_hash=drv_hash).first()
    if not derivation:
        raise HTTPException(status_code=404, detail="Derivation not found")

    # Get all attestations with user info
    attestations = (
        db.query(models.Attestation, models.User)
        .join(models.User, models.Attestation.user_id == models.User.id)
        .filter(models.Attestation.drv_id == derivation.id)
        .all()
    )

    # Group attestations by output_path first, then by output_hash (clusters)
    outputs = {}
    for attestation, user in attestations:
        output_path = attestation.output_path
        if output_path not in outputs:
            outputs[output_path] = {"clusters": {}, "attestations": []}

        outputs[output_path]["attestations"].append({"attestation": attestation, "user": user})

        output_hash = attestation.output_hash
        if output_hash not in outputs[output_path]["clusters"]:
            outputs[output_path]["clusters"][output_hash] = []
        outputs[output_path]["clusters"][output_hash].append({
            "attestation": attestation,
            "user": user
        })

    # Process each output: sort clusters and calculate stats
    outputs_list = []
    for output_path, data in sorted(outputs.items()):
        sorted_clusters = sorted(data["clusters"].items(), key=lambda x: len(x[1]), reverse=True)
        num_attestations = len(data["attestations"])
        num_unique_hashes = len(data["clusters"])

        # Determine status for this output
        if num_attestations < 2:
            status = "pending"
        elif num_unique_hashes == 1:
            status = "reproducible"
        else:
            status = "not_reproducible"

        outputs_list.append({
            "output_path": output_path,
            "clusters": sorted_clusters,
            "num_attestations": num_attestations,
            "num_unique_hashes": num_unique_hashes,
            "status": status
        })

    # Calculate overall statistics
    unique_users = len(set(a.user_id for a, u in attestations))
    total_attestations = len(attestations)
    num_outputs = len(outputs)

    # Get overall reproducibility status using shared function
    overall_status = get_derivation_status(derivation.attestations)
    reproducibility_status = overall_status["status"]

    # Get evaluations that contain output paths from this derivation's attestations
    output_paths_for_drv = [a.output_path for a, u in attestations]
    eval_output_paths = (
        db.query(models.EvaluationOutputPath)
        .join(models.Evaluation)
        .join(models.Jobset)
        .filter(models.EvaluationOutputPath.output_path.in_(output_paths_for_drv))
        .order_by(models.Evaluation.uploaded_at.desc())
        .all()
    ) if output_paths_for_drv else []

    # Get matching link patterns
    link_patterns = db.query(models.LinkPattern).all()
    matching_links = get_matching_links(drv_hash, link_patterns)

    return templates.TemplateResponse("derivation_detail.html", {
        "request": request,
        "derivation": derivation,
        "outputs": outputs_list,
        "num_outputs": num_outputs,
        "total_attestations": total_attestations,
        "unique_users": unique_users,
        "reproducibility_status": reproducibility_status,
        "evaluations": eval_output_paths,
        "matching_links": matching_links
    })
