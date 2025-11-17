"""
Link pattern API routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models
from ..common import get_db, get_token

router = APIRouter()


@router.get("")
def get_link_patterns(db: Session = Depends(get_db)):
    """Get all link patterns"""
    return db.query(models.LinkPattern).all()


@router.post("")
def post_link_pattern(
    pattern: str,
    link: str,
    token: str = Depends(get_token),
    db: Session = Depends(get_db)
):
    """Add a link pattern"""
    user = crud.get_user_with_token(db, token)
    if user == None:
        raise HTTPException(status_code=401, detail="User not found")
    crud.add_link_pattern(db, pattern, link)
    return "OK"
