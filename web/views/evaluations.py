"""
Evaluation view routes (HTML)
"""
import json
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..common import get_db, templates, get_derivation_status, get_matching_links

router = APIRouter()


def get_status_icon(status: str) -> str:
    """Get emoji icon for reproducibility status"""
    if status == "reproducible":
        return "✅"
    elif status == "not_reproducible":
        return "❌"
    else:  # pending
        return "❔"


def get_status_label(status: str) -> str:
    """Get human-readable label for status"""
    if status == "reproducible":
        return "Successfully reproduced"
    elif status == "not_reproducible":
        return "Not reproducible"
    else:
        return "Pending verification"


@router.get("")
async def list_evaluations(request: Request, db: Session = Depends(get_db)):
    """List all evaluations"""
    evaluations = (
        db.query(models.Evaluation)
        .join(models.Jobset)
        .order_by(models.Evaluation.uploaded_at.desc())
        .limit(100)
        .all()
    )

    return templates.TemplateResponse("evaluations.html", {
        "request": request,
        "evaluations": evaluations
    })


@router.get("/{evaluation_id}")
async def get_evaluation_detail(
    request: Request,
    evaluation_id: int,
    db: Session = Depends(get_db)
):
    """Get evaluation detail page"""
    evaluation = db.query(models.Evaluation).filter_by(id=evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # Get derivations for this evaluation
    eval_derivations = (
        db.query(models.EvaluationDerivation)
        .join(models.Derivation)
        .filter(models.EvaluationDerivation.evaluation_id == evaluation_id)
        .all()
    )

    # Get all link patterns once
    link_patterns = db.query(models.LinkPattern).all()

    # Calculate stats for each derivation
    derivation_stats = []
    stats_summary = {"reproducible": 0, "not_reproducible": 0, "pending": 0}

    for eval_drv in eval_derivations:
        drv = eval_drv.derivation
        drv_status = get_derivation_status(drv.attestations)
        stats_summary[drv_status["status"]] += 1

        # Get matching links for this derivation
        matching_links = get_matching_links(drv.drv_hash, link_patterns)

        derivation_stats.append({
            "eval_drv": eval_drv,
            "derivation": drv,
            "attestation_count": drv_status["attestation_count"],
            "unique_hashes": drv_status["unique_hashes"],
            "status": drv_status["status"],
            "matching_links": matching_links
        })

    return templates.TemplateResponse("evaluation_detail.html", {
        "request": request,
        "evaluation": evaluation,
        "derivations": derivation_stats,
        "stats_summary": stats_summary
    })


@router.get("/{evaluation_id}/tree")
async def get_evaluation_tree(
    request: Request,
    evaluation_id: int,
    db: Session = Depends(get_db)
):
    """Get evaluation dependency tree view"""
    evaluation = db.query(models.Evaluation).filter_by(id=evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # Parse the SBOM
    try:
        sbom = json.loads(evaluation.definition_sbom)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid SBOM data")

    # Extract components and build lookup maps
    components = sbom.get("components", [])
    dependencies = sbom.get("dependencies", [])

    # Build a map from out_path to component info
    out_path_to_component = {}
    out_path_to_drv_hash = {}
    for comp in components:
        out_path = None
        drv_hash = None
        for prop in comp.get("properties", []):
            if prop["name"] == "nix:out_path":
                out_path = prop["value"]
            elif prop["name"] == "nix:derivation":
                drv_hash = prop["value"]
        if out_path:
            out_path_to_component[out_path] = {
                "name": comp.get("name", ""),
                "version": comp.get("version", ""),
                "out_path": out_path,
                "drv_hash": drv_hash
            }
            if drv_hash:
                out_path_to_drv_hash[out_path] = drv_hash

    # Get all derivations for this evaluation to determine status
    eval_derivations = (
        db.query(models.EvaluationDerivation)
        .join(models.Derivation)
        .filter(models.EvaluationDerivation.evaluation_id == evaluation_id)
        .all()
    )

    # Build a map from drv_hash to status
    drv_hash_to_status = {}
    for eval_drv in eval_derivations:
        drv = eval_drv.derivation
        status = get_derivation_status(drv.attestations)
        drv_hash_to_status[drv.drv_hash] = status["status"]

    # Build results map (out_path -> status)
    results = {}
    for out_path, comp in out_path_to_component.items():
        drv_hash = comp.get("drv_hash")
        if drv_hash and drv_hash in drv_hash_to_status:
            results[out_path] = drv_hash_to_status[drv_hash]
        else:
            results[out_path] = "pending"

    # Get the root from metadata
    root = sbom.get("metadata", {}).get("component", {}).get("bom-ref", "")
    if not root and components:
        # Fallback: use first component's out_path
        for prop in components[0].get("properties", []):
            if prop["name"] == "nix:out_path":
                root = prop["value"]
                break

    # Generate tree HTML
    def generate_tree_html(node_path, seen=None):
        if seen is None:
            seen = set()

        if node_path in seen:
            return '<summary class="text-gray-400">...</summary>'

        seen.add(node_path)

        comp = out_path_to_component.get(node_path, {})
        name = comp.get("name", node_path[44:] if len(node_path) > 44 else node_path)
        version = comp.get("version", "")
        drv_hash = comp.get("drv_hash", "")
        status = results.get(node_path, "pending")
        icon = get_status_icon(status)
        label = get_status_label(status)

        # Build the summary line
        display_name = f"{name}-{version}" if version else name
        if drv_hash:
            link = f'<a href="/derivations/{drv_hash}" class="text-blue-600 hover:text-blue-800 hover:underline">{display_name}</a>'
        else:
            link = display_name

        html = f'<summary title="{node_path}"><span title="{label}">{icon}</span> {link}</summary>\n'

        # Find children
        children = []
        for dep in dependencies:
            if dep.get("ref") == node_path:
                children = dep.get("dependsOn", [])
                break

        if children:
            html += '<ul>\n'
            for child in children:
                html += f'<li><details open>{generate_tree_html(child, seen.copy())}</details></li>\n'
            html += '</ul>\n'

        return html

    # Calculate statistics
    stats = defaultdict(int)
    for status in results.values():
        stats[status] += 1

    total = len(results)
    tree_html = generate_tree_html(root) if root else "<p>No dependency tree available</p>"

    return templates.TemplateResponse("evaluation_tree.html", {
        "request": request,
        "evaluation": evaluation,
        "tree_html": tree_html,
        "stats": {
            "total": total,
            "reproducible": stats["reproducible"],
            "not_reproducible": stats["not_reproducible"],
            "pending": stats["pending"],
        }
    })
