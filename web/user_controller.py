from . import models
from .db import SessionLocal, engine
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db = SessionLocal()

def create_user(name: str, token: str = ""):
    user = models.User.create(db, name=name)
    token = models.Token.create(db, user=user, value=token)
    print(f"Created user {name} with token {token.value}")


