"""
Lila - Reproducibility tracker for Nix builds
Main FastAPI application
"""
import pathlib
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from .api import attestations, derivations, evaluations, jobsets, link_patterns, signatures
from .views import home, jobsets as jobsets_views, evaluations as evaluations_views, derivations as derivations_views, outputs as outputs_views

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

# Include view routers (HTML)
app.include_router(home.router)
app.include_router(jobsets_views.router, prefix="/jobsets")
app.include_router(evaluations_views.router, prefix="/evaluations")
app.include_router(derivations_views.router, prefix="/derivations")
app.include_router(outputs_views.router, prefix="/outputs")

# Include API routers (JSON)
app.include_router(
    attestations.router,
    prefix="/api",
    tags=["attestations"]
)

app.include_router(
    derivations.router,
    prefix="/api/derivations",
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
    prefix="/api/link_patterns",
    tags=["link_patterns"]
)

app.include_router(
    signatures.router,
    prefix="/api/signatures",
    tags=["signatures"]
)
