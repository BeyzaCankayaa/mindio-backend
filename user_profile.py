from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import User, UserProfile
from auth import get_current_user

router = APIRouter(prefix="/user", tags=["User"])


# -------------------------
# BASIC PROFILE (UI)
# -------------------------

class ProfileResponse(BaseModel):
    name: str
    email: EmailStr
    birth_date: Optional[date] = None

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    birth_date: Optional[date] = None


@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return ProfileResponse(
        name=current_user.username,
        email=current_user.email,
        birth_date=getattr(current_user, "birth_date", None),
    )


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.name is None and payload.email is None and payload.birth_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to update.",
        )

    if payload.email and payload.email != current_user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
        current_user.email = payload.email

    if payload.name:
        current_user.username = payload.name

    if payload.birth_date is not None:
        current_user.birth_date = payload.birth_date

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return ProfileResponse(
        name=current_user.username,
        email=current_user.email,
        birth_date=current_user.birth_date,
    )


# -------------------------
# AI PROFILE (DB context)
# -------------------------

class AIProfileResponse(BaseModel):
    age_range: Optional[str] = None
    gender: Optional[str] = None
    mood: Optional[str] = None
    support_topics: Optional[str] = None
    location: Optional[str] = None

    class Config:
        from_attributes = True


class AIProfileUpdateRequest(BaseModel):
    age_range: Optional[str] = None
    gender: Optional[str] = None
    mood: Optional[str] = None
    support_topics: Optional[str] = None
    location: Optional[str] = None


@router.get("/ai-profile", response_model=AIProfileResponse)
def get_ai_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .order_by(desc(UserProfile.id))
        .first()
    )
    if not profile:
        return AIProfileResponse()
    return profile


@router.put("/ai-profile", response_model=AIProfileResponse)
def upsert_ai_profile(
    payload: AIProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # En az bir alan gelmiş mi?
    if (
        payload.age_range is None
        and payload.gender is None
        and payload.mood is None
        and payload.support_topics is None
        and payload.location is None
    ):
        raise HTTPException(status_code=400, detail="Nothing to update.")

    # En güncel profili çek, yoksa yeni oluştur
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .order_by(desc(UserProfile.id))
        .first()
    )

    if not profile:
        profile = UserProfile(user_id=current_user.id)

    if payload.age_range is not None:
        profile.age_range = payload.age_range
    if payload.gender is not None:
        profile.gender = payload.gender
    if payload.mood is not None:
        profile.mood = payload.mood
    if payload.support_topics is not None:
        profile.support_topics = payload.support_topics
    if payload.location is not None:
        profile.location = payload.location

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile
