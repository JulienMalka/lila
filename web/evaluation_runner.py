"""
Evaluation runner - triggers and manages jobset evaluations
"""
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from . import crud, models
from .evaluator import NixEvaluator

logger = logging.getLogger(__name__)


def run_evaluation(db: Session, evaluation_id: int) -> models.Evaluation:
    """
    Run an evaluation for a jobset

    Args:
        db: Database session
        evaluation_id: ID of the evaluation to run

    Returns:
        Updated evaluation object
    """
    evaluation = crud.get_evaluation(db, evaluation_id)
    if not evaluation:
        raise ValueError(f"Evaluation {evaluation_id} not found")

    jobset = evaluation.jobset
    if not jobset:
        raise ValueError(f"Jobset not found for evaluation {evaluation_id}")

    logger.info(f"Starting evaluation {evaluation_id} for jobset '{jobset.name}'")

    # Update status to running
    crud.update_evaluation(db, evaluation_id, status="running")

    try:
        # Run Nix evaluation
        evaluator = NixEvaluator()
        result = evaluator.evaluate_flakeref(jobset.flakeref)

        if not result.success:
            # Evaluation failed
            logger.error(f"Evaluation {evaluation_id} failed: {result.error}")
            crud.update_evaluation(
                db,
                evaluation_id,
                status="failed",
                error_message=result.error,
                completed_at=datetime.utcnow()
            )
            return crud.get_evaluation(db, evaluation_id)

        logger.info(f"Evaluation {evaluation_id} found {len(result.derivations)} derivations")

        # Store derivations and link to evaluation
        derivation_count = 0
        for drv_info in result.derivations:
            # Extract drv hash from path (/nix/store/<hash>-<name>.drv)
            drv_path_parts = drv_info.drv_path.split('/')
            if len(drv_path_parts) < 4:
                logger.warning(f"Invalid drv_path format: {drv_info.drv_path}")
                continue

            drv_hash = drv_path_parts[-1]  # Get the filename part

            # Get or create derivation
            derivation = db.query(models.Derivation).filter_by(drv_hash=drv_hash).first()
            if not derivation:
                derivation = models.Derivation(drv_hash=drv_hash)
                db.add(derivation)
                db.commit()
                db.refresh(derivation)

            # Link derivation to evaluation
            crud.add_evaluation_derivation(
                db,
                evaluation_id=evaluation_id,
                derivation_id=derivation.id,
                attribute_path=drv_info.attr,
                output_paths=json.dumps(drv_info.outputs)
            )
            derivation_count += 1

        # Update evaluation with results
        crud.update_evaluation(
            db,
            evaluation_id,
            status="completed",
            completed_at=datetime.utcnow(),
            derivation_count=derivation_count
        )

        logger.info(f"Evaluation {evaluation_id} completed successfully")

        return crud.get_evaluation(db, evaluation_id)

    except Exception as e:
        logger.exception(f"Unexpected error in evaluation {evaluation_id}")
        crud.update_evaluation(
            db,
            evaluation_id,
            status="failed",
            error_message=str(e),
            completed_at=datetime.utcnow()
        )
        return crud.get_evaluation(db, evaluation_id)


def trigger_evaluation(db: Session, jobset_id: int) -> models.Evaluation:
    """
    Trigger a new evaluation for a jobset

    Args:
        db: Database session
        jobset_id: ID of the jobset to evaluate

    Returns:
        Newly created evaluation (in pending/running state)
    """
    jobset = crud.get_jobset(db, jobset_id)
    if not jobset:
        raise ValueError(f"Jobset {jobset_id} not found")

    if not jobset.enabled:
        raise ValueError(f"Jobset '{jobset.name}' is disabled")

    # Create evaluation
    evaluation = crud.create_evaluation(db, jobset_id)

    logger.info(f"Triggered evaluation {evaluation.id} for jobset '{jobset.name}'")

    # Run evaluation synchronously (for now)
    # Later this can be moved to a background task
    return run_evaluation(db, evaluation.id)
