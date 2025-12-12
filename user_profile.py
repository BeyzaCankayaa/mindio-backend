from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth import get_current_user

router = APIRouter(prefix="/user", tags=["User"])


# ---------- SCHEMAS ----------

class ProfileResponse(BaseModel):
    name: str
    email: EmailStr
    birth_date: date | None = None

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    birth_date: date | None = None


# ---------- ROUTES ----------

@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return ProfileResponse(
        name=current_user.username,
        email=current_user.email,
        birth_date=current_user.birth_date,
    )


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # En az bir alan gelmiş mi?
    if payload.name is None and payload.email is None and payload.birth_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to update.",
        )

    # Email değişiyorsa: çakışma kontrolü
    if payload.email and payload.email != current_user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
        current_user.email = payload.email

    # İsim (username) güncelle
    if payload.name:
        current_user.username = payload.name

    # Doğum tarihi güncelle
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
