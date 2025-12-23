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
# ENUMS
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

    # Relations
    moods = relationship("Mood", back_populates="user", lazy="selectin")
    suggestions = relationship("Suggestion", back_populates="user", lazy="selectin")
    gamification_entries = relationship("Gamification", back_populates="user", lazy="selectin")

    suggestion_reactions = relationship("SuggestionReaction", back_populates="user", lazy="selectin")
    suggestion_saves = relationship("SuggestionSave", back_populates="user", lazy="selectin")
    suggestion_comments = relationship("SuggestionComment", back_populates="user", lazy="selectin")

    daily_suggestions = relationship("UserDailySuggestion", back_populates="user", lazy="selectin")

    # UserProfile
    profiles = relationship("UserProfile", back_populates="user", lazy="selectin")

    # Shop / Characters
    owned_characters = relationship("UserCharacter", back_populates="user", lazy="selectin")

    # Rewards
    reward_claims = relationship("RewardClaim", back_populates="user", lazy="selectin")


# =========================
# USER PROFILE
# =========================
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    age_range = Column(String(50), nullable=True)
    gender = Column(String(50), nullable=True)
    mood = Column(String(50), nullable=True)
    support_topics = Column(String(255), nullable=True)
    location = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profiles", lazy="selectin")


# =========================
# MOOD
# =========================
class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mood = Column(String(50), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="moods", lazy="selectin")


# =========================
# PERSONALITY RESPONSES (history)
# =========================
class PersonalityResponse(Base):
    __tablename__ = "personality_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    q1_answer = Column(String, nullable=False)
    q2_answer = Column(String, nullable=False)
    q3_answer = Column(String, nullable=False)
    q4_answer = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# =========================
# SUGGESTION
# =========================
class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    text = Column(String(500), nullable=False)

    source = Column(
        SAEnum(SuggestionSource, name="suggestion_source"),
        nullable=False,
        server_default="user",
        index=True,
    )

    is_approved = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="suggestions", lazy="selectin")

    reactions = relationship("SuggestionReaction", back_populates="suggestion", lazy="selectin")
    saves = relationship("SuggestionSave", back_populates="suggestion", lazy="selectin")
    comments = relationship("SuggestionComment", back_populates="suggestion", lazy="selectin")

    daily_used_by = relationship("UserDailySuggestion", back_populates="suggestion", lazy="selectin")


class SuggestionReaction(Base):
    __tablename__ = "suggestion_reactions"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    reaction = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("suggestion_id", "user_id", name="uq_reaction_suggestion_user"),)

    user = relationship("User", back_populates="suggestion_reactions", lazy="selectin")
    suggestion = relationship("Suggestion", back_populates="reactions", lazy="selectin")


class SuggestionSave(Base):
    __tablename__ = "suggestion_saves"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("suggestion_id", "user_id", name="uq_save_suggestion_user"),)

    user = relationship("User", back_populates="suggestion_saves", lazy="selectin")
    suggestion = relationship("Suggestion", back_populates="saves", lazy="selectin")


class SuggestionComment(Base):
    __tablename__ = "suggestion_comments"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    text = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="suggestion_comments", lazy="selectin")
    suggestion = relationship("Suggestion", back_populates="comments", lazy="selectin")


class UserDailySuggestion(Base):
    __tablename__ = "user_daily_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, default=date.today, index=True)

    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_user_daily_suggestion"),)

    user = relationship("User", back_populates="daily_suggestions", lazy="selectin")
    suggestion = relationship("Suggestion", back_populates="daily_used_by", lazy="selectin")


class GlobalDailySuggestion(Base):
    __tablename__ = "global_daily_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, default=date.today, index=True)

    __table_args__ = (UniqueConstraint("day", name="uq_global_daily_suggestion_day"),)


# =========================
# GAMIFICATION
# =========================
class Gamification(Base):
    __tablename__ = "gamification"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    points = Column(Integer, nullable=False, server_default="0")
    badge_level = Column(String, nullable=False, server_default="Newbie")

    user = relationship("User", back_populates="gamification_entries", lazy="selectin")


# =========================
# SHOP CHARACTERS
# =========================
class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    asset_key = Column(String(50), nullable=False, unique=True, index=True)
    cost = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owners = relationship("UserCharacter", back_populates="character", lazy="selectin")


# =========================
# USER CHARACTERS (Owned)
# =========================
class UserCharacter(Base):
    __tablename__ = "user_characters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)

    # This is used by user_character.py (active selected character)
    is_active = Column(Boolean, nullable=False, server_default="false")

    acquired_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "character_id", name="uq_user_character"),)

    user = relationship("User", back_populates="owned_characters", lazy="selectin")
    character = relationship("Character", back_populates="owners", lazy="selectin")


# =========================
# REWARDS
# =========================
class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    points = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")

    claims = relationship("RewardClaim", back_populates="reward", lazy="selectin")


class RewardClaim(Base):
    __tablename__ = "reward_claims"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reward_id = Column(Integer, ForeignKey("rewards.id"), nullable=False, index=True)
    claimed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "reward_id", name="uq_user_reward"),)

    user = relationship("User", back_populates="reward_claims", lazy="selectin")
    reward = relationship("Reward", back_populates="claims", lazy="selectin")
