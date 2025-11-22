import datetime
import random
import string
from typing import List, Optional

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, Table,
                        UniqueConstraint, func, Text)
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

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
    # identification
    output_digest: Mapped[str] = mapped_column()
    output_name: Mapped[str] = mapped_column()
    output_path = column_property("/nix/store/" + output_digest + "-" + output_name)
    # metadata
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    drv_id: Mapped[str] = mapped_column(ForeignKey("derivations.id"))
    derivation: Mapped["Derivation"] = relationship(back_populates="attestations")
    # data
    output_hash: Mapped[str] = mapped_column()
    output_sig: Mapped[str] = mapped_column()

class LinkPattern(Base):
    __tablename__ = "link_patterns"
    pattern: Mapped[str] = mapped_column(primary_key=True)
    link: Mapped[str] = mapped_column()

class Jobset(Base):
    __tablename__ = "jobsets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(default=None)

    # Flakeref (includes branch and package)
    # Example: "github:NixOS/nixpkgs/nixos-unstable#legacyPackages.x86_64-linux.hello"
    flakeref: Mapped[str] = mapped_column()

    # Settings
    enabled: Mapped[bool] = mapped_column(default=True)

    # Metadata
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )

    # Relationships
    evaluations: Mapped[List["Evaluation"]] = relationship(back_populates="jobset")

class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    jobset_id: Mapped[int] = mapped_column(ForeignKey("jobsets.id"), index=True)

    # Evaluation metadata
    evaluation_number: Mapped[int] = mapped_column()  # Sequential per jobset
    started_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="pending")  # pending, running, completed, failed

    # Results
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    derivation_count: Mapped[Optional[int]] = mapped_column(default=None)

    # Relationships
    jobset: Mapped["Jobset"] = relationship(back_populates="evaluations")
    derivations: Mapped[List["EvaluationDerivation"]] = relationship(back_populates="evaluation")

class EvaluationDerivation(Base):
    __tablename__ = "evaluation_derivations"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id"), index=True)
    derivation_id: Mapped[int] = mapped_column(ForeignKey("derivations.id"), index=True)

    # Metadata from this specific evaluation
    attribute_path: Mapped[Optional[str]] = mapped_column(default=None)
    output_paths: Mapped[Optional[str]] = mapped_column(Text, default=None)  # JSON array

    # Relationships
    evaluation: Mapped["Evaluation"] = relationship(back_populates="derivations")
    derivation: Mapped["Derivation"] = relationship()
