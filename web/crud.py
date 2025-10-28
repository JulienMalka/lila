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

def report(db: Session, name: str):
    r = db.query(models.Report).filter_by(name=name).one_or_none()
    if r == None:
        return None
    return json.loads(r.definition)

def suggest(db: Session, paths, user_id):
    # Derivations in the database might not match derivations on the rebuilder system.
    # TODO: can this happen only for FODs or also for other derivations?
    # TODO: Add enough metadata to the report so you know what to nix-instantiate to get all relevant drvs
    # TODO: don't suggest nodes that have already been rebuilt by the current user
    #stmt = select(models.Derivation.drv_hash, models.Attestation.output_path).join(models.Attestation).where(models.Attestation.output_path.in_(paths)).group_by(models.Attestation.output_path).having(func.count(models.Attestation.id) < 2)
    #suggestions = []
    #for row in db.execute(stmt):
    #    suggestions.append(row._mapping['drv_hash'])
    candidates = paths
    if user:
        for attestation in db.query(models.Attestation).filter(models.Attestation.output_path.in_(candidates)).filter_by(user_id=user_id).all():
            if attestation.output_path in candidates:
                candidates.remove(attestation.output_path)
    # TODO don't consider attestations that have been built twice by the same user
    # as 'rebuilt'
    stmt = select(models.Attestation.output_path).where(models.Attestation.output_path.in_(candidates)).group_by(models.Attestation.output_path).having(func.count(models.Attestation.id) > 1)
    for row in db.execute(stmt):
        candidates.remove(row._mapping['output_path'])
    return candidates

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

def define_report(db: Session, name: str, definition: dict):
    db.execute(
        insert(models.Report).values({
            "name": name,
            "definition": json.dumps(definition),
        }))
    db.commit()

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
