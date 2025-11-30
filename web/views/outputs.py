"""
Output path view routes (HTML)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..common import get_db, templates, get_output_path_status, get_matching_links

router = APIRouter()


@router.get("/{store_path:path}")
async def get_output_detail(
    request: Request,
    store_path: str,
    db: Session = Depends(get_db)
):
    """Get output path detail page with all attestations"""
    # Parse output_digest and output_name from store_path (e.g., "abc123-package-1.0")
    parts = store_path.split("-", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=404, detail="Invalid output path format")

    output_digest = parts[0]
    output_name = parts[1]
    output_path = f"/nix/store/{store_path}"

    # Get all attestations for this output path with user and derivation info
    attestations = (
        db.query(models.Attestation, models.User, models.Derivation)
        .join(models.User, models.Attestation.user_id == models.User.id)
        .join(models.Derivation, models.Attestation.drv_id == models.Derivation.id)
        .filter(models.Attestation.output_digest == output_digest)
        .filter(models.Attestation.output_name == output_name)
        .all()
    )

    if not attestations:
        raise HTTPException(status_code=404, detail="Output path not found")

    # Build attestation list and group by hash (clusters)
    attestation_list = []
    derivations_set = {}
    clusters = {}

    for att, user, drv in attestations:
        attestation_list.append({
            "attestation": att,
            "user": user,
            "derivation": drv
        })
        if drv.drv_hash not in derivations_set:
            derivations_set[drv.drv_hash] = drv

        # Group by output_hash for clusters
        if att.output_hash not in clusters:
            clusters[att.output_hash] = []
        clusters[att.output_hash].append({
            "attestation": att,
            "user": user,
            "derivation": drv
        })

    # Sort clusters by count (most common first)
    sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)

    # Calculate overall statistics
    total_attestations = len(attestations)
    unique_users = len(set(att.user_id for att, user, drv in attestations))
    num_unique_hashes = len(clusters)

    # Get overall reproducibility status
    all_atts = [att for att, user, drv in attestations]
    overall_status = get_output_path_status(all_atts)
    reproducibility_status = overall_status["status"]

    # Get evaluations containing this output path
    eval_output_paths = (
        db.query(models.EvaluationOutputPath)
        .options(joinedload(models.EvaluationOutputPath.evaluation).joinedload(models.Evaluation.jobset))
        .filter(models.EvaluationOutputPath.output_path == output_path)
        .all()
    )

    # Get matching link patterns
    link_patterns = db.query(models.LinkPattern).all()
    matching_links = get_matching_links(output_path, link_patterns)

    return templates.TemplateResponse("output_detail.html", {
        "request": request,
        "output_path": output_path,
        "output_digest": output_digest,
        "output_name": output_name,
        "attestations": attestation_list,
        "clusters": sorted_clusters,
        "derivations": list(derivations_set.values()),
        "num_derivations": len(derivations_set),
        "total_attestations": total_attestations,
        "unique_users": unique_users,
        "num_unique_hashes": num_unique_hashes,
        "reproducibility_status": reproducibility_status,
        "evaluations": eval_output_paths,
        "matching_links": matching_links
    })
