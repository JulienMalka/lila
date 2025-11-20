"""
Common utilities for the application
Provides: database sessions, authentication, templates
"""
import pathlib
import typing as t
from fastapi import Depends, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud
from .db import SessionLocal

# Database dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication
get_bearer_token = HTTPBearer(auto_error=False)

async def get_token(
    auth: t.Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
) -> str:
    """Extract bearer token from Authorization header"""
    if auth is not None:
        return auth.credentials
    else:
        return ""

async def get_user(
    token: str = Depends(get_token),
    db: Session = Depends(get_db)
) -> int:
    """Get user ID from token, raise 401 if invalid"""
    user_id = crud.get_user_with_token(db, token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user_id

# Templates
thispath = pathlib.Path(__file__).parent.resolve()
templates = Jinja2Templates(directory=str(thispath / "templates"))
