from __future__ import annotations

import enum
from datetime import date

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Text,
    Boolean,
    ForeignKey,
    func,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from database import Base


# =========================
# Suggestion Source Enum
# =========================
class SuggestionSource(str, enum.Enum):
    user = "user"
    ai = "ai"
    system = "system"


# =========================
# USER
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    birth_date = Column(Date, nullable=True)
    onboarding_completed = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    moods = relationship("Mood", back_populates="user", lazy="selectin")
    suggestions = relationship("Suggestion", back_populates="user", lazy="selectin")
    gamification_entries = relationship("Gamification", back_populates="user", lazy="selectin")
    profiles = relationship("UserProfile", back_populates="user", lazy="selectin")
    chat_activities = relationship("ChatActivity", back_populates="user", lazy="selectin")


# =========================
# USER PROFILE
# =========================
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    age_range = Column(String(50))
    gender = Column(String(50))
    mood = Column(String(50))
    support_topics = Column(String(255))
    location = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profiles", lazy="selectin")


# =========================
# MOOD
# =========================
class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mood = Column(String(50), nullable=False)
    note = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="moods", lazy="selectin")


# =========================
# PERSONALITY
# =========================
class PersonalityResponse(Base):
    __tablename__ = "personality_responses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    q1_answer = Column(String, nullable=False)
    q2_answer = Column(String, nullable=False)
    q3_answer = Column(String, nullable=False)
    q4_answer = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# =========================
# SUGGESTIONS
# =========================
class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    text = Column(String(500), nullable=False)

    source = Column(
        SAEnum(SuggestionSource, name="suggestion_source"),
        nullable=False,
        server_default="user",
        index=True,
    )

    is_approved = Column(Boolean, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="suggestions", lazy="selectin")


# =========================
# GAMIFICATION
# =========================
class Gamification(Base):
    __tablename__ = "gamification"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    points = Column(Integer, nullable=False, server_default="0")
    badge_level = Column(String, nullable=False, server_default="Newbie")

    user = relationship("User", back_populates="gamification_entries", lazy="selectin")


# =========================
# CHAT ACTIVITY
# =========================
class ChatActivity(Base):
    __tablename__ = "chat_activities"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# =========================
# CHARACTERS
# =========================
class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    asset_key = Column(String(50), unique=True, nullable=False, index=True)
    cost = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="1")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserCharacter(Base):
    __tablename__ = "user_characters"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "character_id", name="uq_user_character"),
    )


# =========================
# REWARDS  ✅ EKLENEN
# =========================
class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    points = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="1")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RewardClaim(Base):
    __tablename__ = "reward_claims"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reward_id = Column(Integer, ForeignKey("rewards.id"), nullable=False)
    claimed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "reward_id", name="uq_user_reward"),
    )
