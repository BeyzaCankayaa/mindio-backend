from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc

from database import get_db
from models import PersonalityResponse, User
from auth import get_current_user

router = APIRouter(prefix="/personality", tags=["Personality / Onboarding"])


class PersonalitySubmitRequest(BaseModel):
    q1_answer: str  # Age range
    q2_answer: str  # Gender
    q3_answer: str  # Current mood
    q4_answer: str  # Support topics


class PersonalitySubmitResponse(BaseModel):
    message: str
    onboarding_completed: bool


@router.post(
    "/submit",
    response_model=PersonalitySubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_personality_test(
    payload: PersonalitySubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ✅ NEW BEHAVIOR:
    - PersonalityResponse (history) yaz
    - UserProfile (kalıcı AI context) yaz / güncelle
    - user.onboarding_completed = True
    """

    if getattr(current_user, "onboarding_completed", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Personality test already completed.",
        )

    response = PersonalityResponse(
        user_id=current_user.id,
        q1_answer=payload.q1_answer,
        q2_answer=payload.q2_answer,
        q3_answer=payload.q3_answer,
        q4_answer=payload.q4_answer,
    )

    try:
        db.add(response)

        # ✅ Upsert UserProfile (latest record)
        profile = (
            db.query(UserProfile)
            .filter(UserProfile.user_id == current_user.id)
            .order_by(desc(UserProfile.id))
            .first()
        )
        if not profile:
            profile = UserProfile(user_id=current_user.id)

        profile.age_range = payload.q1_answer
        profile.gender = payload.q2_answer
        profile.mood = payload.q3_answer
        profile.support_topics = payload.q4_answer

        db.add(profile)

        # ✅ onboarding flag
        current_user.onboarding_completed = True
        db.add(current_user)

        db.commit()
        db.refresh(current_user)

    except SQLAlchemyError as e:
        db.rollback()
        print("DB ERROR submit_personality_test:", str(e))
        raise HTTPException(
            status_code=500,
            detail="Database error while saving personality test.",
        )

    return {
        "message": "Personality test completed successfully.",
        "onboarding_completed": True,
    }
