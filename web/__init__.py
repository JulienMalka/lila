"""
Lila - Reproducibility tracker for Nix builds
Main FastAPI application
"""
import pathlib
from fastapi import Depends, FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import routers
from .api import attestations, derivations, evaluations, jobsets, link_patterns, signatures

# Import common utilities
from .common import get_db, get_token


app = FastAPI(
    title="Lila",
    description="Reproducibility tracker for Nix builds",
    version="0.1.0"
)

# Static files
thispath = pathlib.Path(__file__).parent.resolve()
app.mount("/static", StaticFiles(directory=str(thispath / "static")), name="static")

# CORS middleware
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


# Include API routers (JSON)
app.include_router(
    attestations.router,
    tags=["attestations"]
)

app.include_router(
    derivations.router,
    prefix="/derivations",
    tags=["derivations"]
)

app.include_router(
    evaluations.router,
    prefix="/api/evaluations",
    tags=["evaluations"]
)

app.include_router(
    jobsets.router,
    prefix="/api/jobsets",
    tags=["jobsets"]
)

app.include_router(
    link_patterns.router,
    prefix="/link_patterns",
    tags=["link_patterns"]
)

app.include_router(
    signatures.router,
    prefix="/signatures",
    tags=["signatures"]
)
