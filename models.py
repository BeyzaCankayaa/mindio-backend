from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    func
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    moods = relationship("Mood", back_populates="user")


class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mood = Column(String(50), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="moods")
# ==================== PERSONALITY TEST MODEL ====================

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean

class PersonalityResponse(Base):
    __tablename__ = "personality_responses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # İstersen ileride JWT'den bağlarız
    q1_answer = Column(String, nullable=False)
    q2_answer = Column(String, nullable=False)
    q3_answer = Column(String, nullable=False)
    q4_answer = Column(String, nullable=False)  # Çoklu seçimler virgülle tutulur
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== CROWDSOURCING SUGGESTION MODEL ====================

class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # anonim olacaksa boş bırakırız
    text = Column(String(500), nullable=False)
    is_approved = Column(Boolean, default=True)  # basit tutuyoruz: default onaylı
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== GAMIFICATION MODEL ====================

class Gamification(Base):
    __tablename__ = "gamification"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    points = Column(Integer, default=0)
    badge_level = Column(String, default="Newbie")  # Newbie / Bronze / Silver / Gold
