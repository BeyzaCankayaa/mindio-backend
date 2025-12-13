from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import PersonalityResponse, User
from auth import get_current_user

router = APIRouter(prefix="/personality", tags=["Personality"])


class PersonalityRequest(BaseModel):
    q1_answer: str   # yaş aralığı
    q2_answer: str   # cinsiyet
    q3_answer: str   # ruh hali
    q4_answer: Union[List[str], str]  # Flutter bazen string yollayabilir


class PersonalityResponseDTO(BaseModel):
    id: int
    user_id: int
    q1_answer: str
    q2_answer: str
    q3_answer: str
    q4_answer: str

    class Config:
        from_attributes = True


def _normalize_topics(q4: Union[List[str], str]) -> str:
    if isinstance(q4, list):
        items = [x.strip() for x in q4 if str(x).strip()]
        return ", ".join(items)
    # string geldiyse:
    return str(q4).strip()


@router.post("/submit", response_model=PersonalityResponseDTO)
def submit_personality(
    payload: PersonalityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q4_joined = _normalize_topics(payload.q4_answer)
    if not q4_joined:
        raise HTTPException(status_code=400, detail="q4_answer cannot be empty")

    record = PersonalityResponse(
        user_id=current_user.id,
        q1_answer=payload.q1_answer,
        q2_answer=payload.q2_answer,
        q3_answer=payload.q3_answer,
        q4_answer=q4_joined,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record
