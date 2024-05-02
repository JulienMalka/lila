from collections import defaultdict
from sys import argv
import typing as t
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, crud, user_controller
from .db import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

origins = [
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

get_bearer_token = HTTPBearer(auto_error=False)

async def get_token(
    auth: t.Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
) -> str:
    if auth is not None:
        return auth.credentials
    else:
        return ""



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_user(username, token=None):
    if token is not None:
        user_controller.create_user(username, token)
    else:
        user_controller.create_user(username)



def get_drv_recap_or_404(session, drv_hash, full) -> schemas.DerivationAttestation:
    drv = session.query(models.Derivation).filter_by(drv_hash=drv_hash).one_or_none()
    if drv is None:
        raise HTTPException(status_code=404, detail="Not found")

    attestations = drv.attestations
    if (full):
        return attestations;

    attestation_outputs = defaultdict(dict)
    for attestation in attestations:
        if attestation.output_hash not in attestation_outputs[attestation.output_path].keys():
            attestation_outputs[attestation.output_path][attestation.output_hash] = 1
        else:
            attestation_outputs[attestation.output_path][attestation.output_hash] += 1

    return attestation_outputs

@app.get("/derivations/")
def get_derivations(db: Session = Depends(get_db)) -> schemas.DerivationList:
    return db.query(models.Derivation).all()

@app.get("/derivations/{drv_hash}")
def get_drv(drv_hash: str,
            full: bool = False,
            db: Session = Depends(get_db),
):
    return get_drv_recap_or_404(db, drv_hash, full)

@app.get("/derivations/{drv_hash}")
def get_drv_recap(drv_hash: str, db: Session = Depends(get_db)) -> schemas.DerivationAttestation:
    return get_drv_recap_or_404(db, drv_hash)

@app.post("/attestation/{drv_hash}")
def record_attestation(
    drv_hash: str,
    output_sha256_map: list[schemas.OutputHashPair],
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    user = crud.get_user_with_token(db, token)
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")

    crud.create_attestation(db, drv_hash, output_sha256_map, user)
    return {
        "Attestation accepted"
    }


