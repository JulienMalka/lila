"""
Evaluation view routes (HTML)
"""
import json
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..common import get_db, templates, get_output_path_status, get_matching_links, get_evaluation_output_paths, fetch_attestations_grouped, calculate_output_path_stats

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


@router.get("/{jobset_id}/{git_revision}")
async def get_evaluation_detail(
    request: Request,
    jobset_id: int,
    git_revision: str,
    db: Session = Depends(get_db)
):
    """Get evaluation detail page"""
    evaluation = db.query(models.Evaluation).filter_by(
        jobset_id=jobset_id,
        git_revision=git_revision
    ).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # Get output paths for this evaluation
    output_path_list = get_evaluation_output_paths(db, evaluation.id)

    # Get all link patterns once
    link_patterns = db.query(models.LinkPattern).all()

    # Batch query attestations with derivation eager loaded
    attestations_by_path = fetch_attestations_grouped(db, output_path_list, eager_load_derivation=True)

    # Track unique derivations per output path (for multi-drv detection)
    derivations_by_path = {}
    for output_path, attestations in attestations_by_path.items():
        derivations_by_path[output_path] = set(att.drv_id for att in attestations)

    # Calculate stats for each output path
    output_path_stats = []
    stats_summary = {"reproducible": 0, "not_reproducible": 0, "pending": 0}

    for output_path in output_path_list:
        attestations = attestations_by_path.get(output_path, [])
        out_status = get_output_path_status(attestations)
        stats_summary[out_status["status"]] += 1

        # Get matching links for this output path
        matching_links = get_matching_links(output_path, link_patterns)

        # Get derivation hash if there's at least one attestation
        drv_hash = None
        if attestations:
            drv_hash = attestations[0].derivation.drv_hash

        # Check if multiple derivations produced this output path
        unique_drvs = len(derivations_by_path.get(output_path, set()))

        output_path_stats.append({
            "output_path": output_path,
            "attestation_count": out_status["attestation_count"],
            "unique_hashes": out_status["unique_hashes"],
            "status": out_status["status"],
            "matching_links": matching_links,
            "drv_hash": drv_hash,
            "multi_drv": unique_drvs > 1,
            "drv_count": unique_drvs
        })

    return templates.TemplateResponse("evaluation_detail.html", {
        "request": request,
        "evaluation": evaluation,
        "output_paths": output_path_stats,
        "stats_summary": stats_summary
    })


@router.get("/{jobset_id}/{git_revision}/tree")
async def get_evaluation_tree(
    request: Request,
    jobset_id: int,
    git_revision: str,
    db: Session = Depends(get_db)
):
    """Get evaluation dependency tree view"""
    evaluation = db.query(models.Evaluation).filter_by(
        jobset_id=jobset_id,
        git_revision=git_revision
    ).first()
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

    # Get all output paths for this evaluation to determine status
    output_path_list = get_evaluation_output_paths(db, evaluation.id)
    attestations_by_path = fetch_attestations_grouped(db, output_path_list)

    # Build results map (out_path -> {status, attestation_count})
    results = {}
    for output_path in output_path_list:
        attestations = attestations_by_path.get(output_path, [])
        status_info = get_output_path_status(attestations)
        results[output_path] = {
            "status": status_info["status"],
            "attestation_count": status_info["attestation_count"]
        }

    # For output paths in SBOM but not in evaluation_output_paths, mark as pending
    for out_path in out_path_to_component:
        if out_path not in results:
            results[out_path] = {"status": "pending", "attestation_count": 0}

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
        result_info = results.get(node_path, {"status": "pending", "attestation_count": 0})
        status = result_info["status"]
        attestation_count = result_info["attestation_count"]
        icon = get_status_icon(status)
        label = get_status_label(status)

        # Build the summary line with output path link
        display_name = f"{name}-{version}" if version else name
        store_path = node_path.replace("/nix/store/", "") if node_path.startswith("/nix/store/") else node_path

        if attestation_count > 0:
            # Link to output path detail page
            link = f'<a href="/outputs/{store_path}" class="text-blue-600 hover:text-blue-800 hover:underline">{display_name}</a>'
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
    for result_info in results.values():
        stats[result_info["status"]] += 1

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
