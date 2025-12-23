from __future__ import annotations
import enum
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean,
    ForeignKey, func, UniqueConstraint, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from database import Base


class SuggestionSource(str, enum.Enum):
    user = "user"
    ai = "ai"
    system = "system"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    gamification = relationship("Gamification", back_populates="user", uselist=False)


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    text = Column(String(500), nullable=False)
    source = Column(SAEnum(SuggestionSource, name="suggestion_source"),
                    nullable=False, server_default="user")
    is_approved = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Gamification(Base):
    __tablename__ = "gamification"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    points = Column(Integer, nullable=False, server_default="0")
    badge_level = Column(String(50), nullable=False, server_default="Newbie")

    user = relationship("User", back_populates="gamification")


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    points = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")


class RewardClaim(Base):
    __tablename__ = "reward_claims"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reward_id = Column(Integer, ForeignKey("rewards.id"), nullable=False)
    claimed_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "reward_id", name="uq_user_reward"),
    )
