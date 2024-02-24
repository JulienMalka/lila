from sqlalchemy import values
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import user

from . import models, schemas


def create_report(db: Session, drv_hash: str, output_hash_map: list[schemas.OuputHashPair], user_id):
    derivation = db.query(models.Derivation).filter_by(drv_hash=drv_hash).first()
    if not derivation:
        derivation = models.Derivation(drv_hash=drv_hash)
        db.add(derivation)
        db.commit()
    for item in output_hash_map:
        db.execute(
                insert(models.Report)
                .values(
                    {
                        "output_name": item.output_name,
                        "user_id": user_id,
                        "drv_id": derivation.id,
                        }
        ))
        db.commit()




def get_user_with_token(db: Session, token_val: str):
    token = db.query(models.Token).filter_by(value=token_val).one()
    return token.user_id
