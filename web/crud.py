import json
import os

from sqlalchemy import distinct, func, select, values
if 'SQLALCHEMY_DATABASE_URL' in os.environ and 'postgres' in os.environ['SQLALCHEMY_DATABASE_URL']:
    print("Using postgres dialect")
    from sqlalchemy.dialects.postgresql import insert
else:
    print("Using sqlite dialect")
    from sqlalchemy.dialects.sqlite import insert

from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import user

from . import models, schemas


def create_attestation(db: Session, drv_hash: str, output_hash_map: list[schemas.OutputHashPair], user_id):
    derivation = db.query(models.Derivation).filter_by(drv_hash=drv_hash).first()
    if not derivation:
        derivation = models.Derivation(drv_hash=drv_hash)
        db.add(derivation)
        db.commit()
    for item in output_hash_map:
        db.execute(
                insert(models.Attestation)
                .values(
                    {
                        "output_digest": item.output_digest,
                        "output_name": item.output_name,
                        "user_id": user_id,
                        "drv_id": derivation.id,
                        "output_hash": item.output_hash,
                        "output_sig": item.output_sig,
                        }
        ))
        db.commit()

def suggest(db: Session, elements, user_id):
    # Derivations in the database might not match derivations on the rebuilder system.
    # TODO: can this happen only for FODs or also for other derivations?
    # TODO: Add enough metadata to the report so you know what to nix-instantiate to get all relevant drvs
    # TODO: don't suggest nodes that have already been rebuilt by the current user
    #stmt = select(models.Derivation.drv_hash, models.Attestation.output_path).join(models.Attestation).where(models.Attestation.output_path.in_(paths)).group_by(models.Attestation.output_path).having(func.count(models.Attestation.id) < 2)
    #suggestions = []
    #for row in db.execute(stmt):
    #    suggestions.append(row._mapping['drv_hash'])
    candidates = list(elements.keys())
    if user:
        for attestation in db.query(models.Attestation).filter(models.Attestation.output_path.in_(candidates)).filter_by(user_id=user_id).all():
            if attestation.output_path in candidates:
                candidates.remove(attestation.output_path)
    # TODO don't consider attestations that have been built twice by the same user
    # as 'rebuilt'
    stmt = select(models.Attestation.output_path).where(models.Attestation.output_path.in_(candidates)).group_by(models.Attestation.output_path).having(func.count(models.Attestation.id) > 1)
    for row in db.execute(stmt):
        candidates.remove(row._mapping['output_path'])
    return { candidate: elements[candidate] for candidate in candidates }

# TODO ideally this should take into account derivation paths as well as
# output paths, as for example for a fixed-output derivation we'd want
# to rebuild it with each different collection of inputs, not just once.
# OTOH, it seems caches may also have different derivers for non-FODs?
# To look into further: https://github.com/NixOS/nix/issues/7562
def path_summaries(db: Session, paths):
    # TODO make sure multiple identical results from the same submitter
    # don't get counted as 'successfully reproduced'
    stmt = select(models.Attestation.output_path, func.count(models.Attestation.id), func.count(distinct(models.Attestation.output_hash))).where(models.Attestation.output_path.in_(paths)).group_by(models.Attestation.output_path)
    results = {}
    for output_path in paths:
        results[output_path] = "No builds"
    for result in db.execute(stmt):
        output_path = result._mapping['output_path']
        n_results = result._mapping['count']
        distinct_results = result._mapping['count_1']
        if n_results == 1:
            results[output_path] = "One build"
        elif distinct_results == 1:
            results[output_path] = "Successfully reproduced"
        elif distinct_results < n_results:
            results[output_path] = "Partially reproduced"
        elif distinct_results == n_results:
            results[output_path] = "Consistently nondeterministic"
    return results

def add_link_pattern(db: Session, pattern: str, link: str):
    db.execute(
        insert(models.LinkPattern).values({
            "pattern": pattern,
            "link": link,
            }).on_conflict_do_update(index_elements=['pattern'], set_={'link': link})
        )
    db.commit()

def get_user_with_token(db: Session, token_val: str):
    token = db.query(models.Token).filter_by(value=token_val).one_or_none()
    if token is None:
        return None
    return token.user_id

# Jobset CRUD operations
def create_jobset(db: Session, name: str, flakeref: str, description: str = None, enabled: bool = True):
    jobset = models.Jobset(
        name=name,
        flakeref=flakeref,
        description=description,
        enabled=enabled
    )
    db.add(jobset)
    db.commit()
    db.refresh(jobset)
    return jobset

def get_jobset(db: Session, jobset_id: int):
    return db.query(models.Jobset).filter_by(id=jobset_id).one_or_none()

def get_jobset_by_name(db: Session, name: str):
    return db.query(models.Jobset).filter_by(name=name).one_or_none()

def list_jobsets(db: Session):
    return db.query(models.Jobset).all()

def update_jobset(db: Session, jobset_id: int, **kwargs):
    jobset = get_jobset(db, jobset_id)
    if jobset is None:
        return None

    for key, value in kwargs.items():
        if value is not None and hasattr(jobset, key):
            setattr(jobset, key, value)

    db.commit()
    db.refresh(jobset)
    return jobset

def delete_jobset(db: Session, jobset_id: int):
    jobset = get_jobset(db, jobset_id)
    if jobset is None:
        return False
    db.delete(jobset)
    db.commit()
    return True

# Evaluation CRUD operations
def create_evaluation(db: Session, jobset_id: int):
    """Create a new evaluation for a jobset"""
    # Get the next evaluation number for this jobset
    last_eval = db.query(models.Evaluation)\
        .filter_by(jobset_id=jobset_id)\
        .order_by(models.Evaluation.evaluation_number.desc())\
        .first()

    eval_number = (last_eval.evaluation_number + 1) if last_eval else 1

    evaluation = models.Evaluation(
        jobset_id=jobset_id,
        evaluation_number=eval_number,
        status="pending"
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation

def get_evaluation(db: Session, evaluation_id: int):
    return db.query(models.Evaluation).filter_by(id=evaluation_id).one_or_none()

def list_evaluations(db: Session, jobset_id: int = None):
    query = db.query(models.Evaluation)
    if jobset_id is not None:
        query = query.filter_by(jobset_id=jobset_id)
    return query.order_by(models.Evaluation.started_at.desc()).all()

def update_evaluation(db: Session, evaluation_id: int, **kwargs):
    evaluation = get_evaluation(db, evaluation_id)
    if evaluation is None:
        return None

    for key, value in kwargs.items():
        if hasattr(evaluation, key):
            setattr(evaluation, key, value)

    db.commit()
    db.refresh(evaluation)
    return evaluation

def add_evaluation_derivation(db: Session, evaluation_id: int, derivation_id: int,
                              attribute_path: str = None, output_paths: str = None):
    """Link a derivation to an evaluation"""
    eval_drv = models.EvaluationDerivation(
        evaluation_id=evaluation_id,
        derivation_id=derivation_id,
        attribute_path=attribute_path,
        output_paths=output_paths
    )
    db.add(eval_drv)
    db.commit()
    return eval_drv
