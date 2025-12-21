# models.py (FULL REVİZE)

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
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # ✅ FIX: user_profile.py bunu kullanıyor
    birth_date = Column(Date, nullable=True)

    onboarding_completed = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relations
    moods = relationship("Mood", back_populates="user", lazy="selectin")
    suggestions = relationship("Suggestion", back_populates="user", lazy="selectin")
    gamification_entries = relationship("Gamification", back_populates="user", lazy="selectin")

    suggestion_reactions = relationship("SuggestionReaction", back_populates="user", lazy="selectin")
    suggestion_saves = relationship("SuggestionSave", back_populates="user", lazy="selectin")

    # ✅ FIX: comments tablosu var ama User'da relation yoktu → crash/orm warning çıkarır
    suggestion_comments = relationship("SuggestionComment", back_populates="user", lazy="selectin")

    daily_suggestions = relationship("UserDailySuggestion", back_populates="user", lazy="selectin")

    # ✅ NEW: AI için kalıcı profil
    profiles = relationship("UserProfile", back_populates="user", lazy="selectin")

    # ✅ NEW: chat activity (homepage stats için)
    chat_activities = relationship("ChatActivity", back_populates="user", lazy="selectin")


class UserProfile(Base):
    """
    ✅ NEW TABLE: AI context için kalıcı ve güvenilir profil datası.
    Personality test sonuçları buraya yazılacak.
    """
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Personality test / onboarding alanları
    age_range = Column(String(50), nullable=True)
    gender = Column(String(50), nullable=True)
    mood = Column(String(50), nullable=True)
    support_topics = Column(String(255), nullable=True)
    location = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profiles", lazy="selectin")


class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mood = Column(String(50), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="moods")


class PersonalityResponse(Base):
    """
    Backward-compat / history amaçlı tutulabilir.
    Asıl kalıcı veri UserProfile.
    """
    __tablename__ = "personality_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    q1_answer = Column(String, nullable=False)
    q2_answer = Column(String, nullable=False)
    q3_answer = Column(String, nullable=False)
    q4_answer = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", lazy="selectin")


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    text = Column(String(500), nullable=False)

    is_approved = Column(Boolean, nullable=False, server_default="1")
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

    __table_args__ = (
        UniqueConstraint("suggestion_id", "user_id", name="uq_reaction_suggestion_user"),
    )

    user = relationship("User", back_populates="suggestion_reactions", lazy="selectin")
    suggestion = relationship("Suggestion", back_populates="reactions", lazy="selectin")


class SuggestionSave(Base):
    __tablename__ = "suggestion_saves"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("suggestion_id", "user_id", name="uq_save_suggestion_user"),
    )

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

    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_user_daily_suggestion"),
    )

    user = relationship("User", back_populates="daily_suggestions", lazy="selectin")
    suggestion = relationship("Suggestion", back_populates="daily_used_by", lazy="selectin")


class GlobalDailySuggestion(Base):
    __tablename__ = "global_daily_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, default=date.today, index=True)

    __table_args__ = (
        UniqueConstraint("day", name="uq_global_daily_suggestion_day"),
    )

    suggestion = relationship("Suggestion", lazy="selectin")


class Gamification(Base):
    __tablename__ = "gamification"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    points = Column(Integer, nullable=False, server_default="0")
    badge_level = Column(String, nullable=False, server_default="Newbie")

    user = relationship("User", back_populates="gamification_entries", lazy="selectin")


# ✅ NEW: Chat activity event table (n8n chat sonrası çağrılır)
class ChatActivity(Base):
    __tablename__ = "chat_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="chat_activities", lazy="selectin")


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    asset_key = Column(String(50), unique=True, nullable=False, index=True)
    cost = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="1")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owners = relationship("UserCharacter", back_populates="character", lazy="selectin")


class UserCharacter(Base):
    __tablename__ = "user_characters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "character_id", name="uq_user_character"),
    )

    user = relationship("User", lazy="selectin")
    character = relationship("Character", back_populates="owners", lazy="selectin")
