import datetime
import random
import string
from typing import List

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, Table,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

class Derivation(Base):
    __tablename__ = "derivations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    drv_hash: Mapped[str] = mapped_column(index=True)
    attestations: Mapped[List["Attestation"]] = relationship(back_populates="derivation")



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    tokens: Mapped[List["Token"]] = relationship(back_populates="user")

    def __init__(self, name):
        self.name = name
        self.tokens = []

    @classmethod
    def create(cls, db, **kw):
        obj = cls(**kw)
        db.add(obj)
        db.commit()
        return obj


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column()
    valid: Mapped[bool] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="tokens")

    def __init__(self, user, value = ""):
        if value == "":
            self.value = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=30))
        else:
            self.value = value
        self.user = user
        self.user_id = user.id
        self.valid = True

    @classmethod
    def create(cls, db, **kw):
        obj = cls(**kw)
        db.add(obj)
        db.commit()
        return obj


class Attestation(Base):
    __tablename__ = "attestations"

    id: Mapped[int] = mapped_column(primary_key=True)
    output_path: Mapped[str] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    drv_id: Mapped[str] = mapped_column(ForeignKey("derivations.id"))
    derivation: Mapped["Derivation"] = relationship(back_populates="attestations")
    output_hash: Mapped[str] = mapped_column()
    output_sig: Mapped[str] = mapped_column()

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    # For now we store the definition in a CycloneDX JSON blob,
    # later we might want to normalize it into its own database
    # structure.
    definition: Mapped[str] = mapped_column()

class LinkPattern(Base):
    __tablename__ = "link_patterns"
    pattern: Mapped[str] = mapped_column(primary_key=True)
    link: Mapped[str] = mapped_column()
