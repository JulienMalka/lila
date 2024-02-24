import typing as t
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, crud
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


def get_drv_recap_or_404(session, drv_hash):
    drv = session.query(models.Derivation).filter_by(drv_hash=drv_hash).one_or_none()
    if drv is None:
        raise HTTPException(status_code=404, detail="Not found")

    reports = session.query(models.Report).filter_by(drv_id=drv.id).all()
    report_outputs = {}
    for report in reports:
        if report.output_name not in report_outputs.keys() or report.output_hash not in report_outputs[report.output_name].keys():
            report_outputs[report.output_name] = {}
            report_outputs[report.output_name][report.output_hash] = 1
        else:
            report_outputs[report.output_name][report.output_hash] += 1

        

    return report_outputs


@app.get("/derivations/")
def get_derivations(db: Session = Depends(get_db)):
    return db.query(models.Derivation).all()


@app.get("/derivation/{drv_hash}")
def get_machines(drv_hash: str, db: Session = Depends(get_db)):
    return get_drv_recap_or_404(db, drv_hash)


@app.post("/report/{drv_hash}")
def record_report(
    drv_hash: str,
    output_sha256_map: list[schemas.OuputHashPair],
    token: str = Depends(get_token),
    db: Session = Depends(get_db),
):
    user = crud.get_user_with_token(db, token)
    crud.create_report(db, drv_hash, output_sha256_map, user)
    return {
        "Report accepted"
    }


