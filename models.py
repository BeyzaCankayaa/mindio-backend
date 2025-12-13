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


# ===================== USERS =====================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profil ekranı için doğum tarihi (şimdilik kapalı)
    # birth_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    moods = relationship("Mood", back_populates="user")
    suggestions = relationship("Suggestion", back_populates="user", lazy="selectin")
    gamification_entries = relationship("Gamification", back_populates="user", lazy="selectin")

    # ✅ Yeni: suggestions etkileşimleri
    suggestion_reactions = relationship("SuggestionReaction", back_populates="user", lazy="selectin")
    suggestion_saves = relationship("SuggestionSave", back_populates="user", lazy="selectin")
    suggestion_comments = relationship("SuggestionComment", back_populates="user", lazy="selectin")


# ===================== MOOD TRACKING =====================

class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mood = Column(String(50), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="moods")


# ===================== PERSONALITY TEST =====================

class PersonalityResponse(Base):
    __tablename__ = "personality_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    q1_answer = Column(String, nullable=False)
    q2_answer = Column(String, nullable=False)
    q3_answer = Column(String, nullable=False)
    q4_answer = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ===================== CROWDSOURCING SUGGESTIONS =====================

class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    text = Column(String(500), nullable=False)

    is_approved = Column(Boolean, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="suggestions")

    # ✅ Yeni: suggestion ilişkileri
    reactions = relationship("SuggestionReaction", back_populates="suggestion", lazy="selectin")
    saves = relationship("SuggestionSave", back_populates="suggestion", lazy="selectin")
    comments = relationship("SuggestionComment", back_populates="suggestion", lazy="selectin")


class SuggestionReaction(Base):
    __tablename__ = "suggestion_reactions"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # "like" | "dislike"
    reaction = Column(String(10), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("suggestion_id", "user_id", name="uq_reaction_suggestion_user"),
    )

    user = relationship("User", back_populates="suggestion_reactions")
    suggestion = relationship("Suggestion", back_populates="reactions")


class SuggestionSave(Base):
    __tablename__ = "suggestion_saves"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("suggestion_id", "user_id", name="uq_save_suggestion_user"),
    )

    user = relationship("User", back_populates="suggestion_saves")
    suggestion = relationship("Suggestion", back_populates="saves")


class SuggestionComment(Base):
    __tablename__ = "suggestion_comments"

    id = Column(Integer, primary_key=True, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    text = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="suggestion_comments")
    suggestion = relationship("Suggestion", back_populates="comments")


# ===================== DAILY SUGGESTION (PER USER PER DAY) =====================

class UserDailySuggestion(Base):
    __tablename__ = "user_daily_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, default=date.today, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_user_daily_suggestion"),
    )

    user = relationship("User")
    suggestion = relationship("Suggestion")


# ===================== GAMIFICATION =====================

class Gamification(Base):
    __tablename__ = "gamification"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    points = Column(Integer, nullable=False, server_default="0")
    badge_level = Column(String, nullable=False, server_default="Newbie")

    user = relationship("User", back_populates="gamification_entries")
