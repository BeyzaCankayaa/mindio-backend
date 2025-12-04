# personality.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import PersonalityResponse

router = APIRouter(prefix="/personality", tags=["Personality"])


class PersonalityRequest(BaseModel):
    user_id: int | None = None
    q1_answer: str
    q2_answer: str
    q3_answer: str
    q4_answer: list[str]  # Çoklu seçenekler gelecek


class PersonalityResponseDTO(BaseModel):
    id: int
    user_id: int | None
    q1_answer: str
    q2_answer: str
    q3_answer: str
    q4_answer: str

    class Config:
        orm_mode = True  # Pydantic v2'de warning verir ama çalışır


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/submit", response_model=PersonalityResponseDTO)
def submit_personality(
    payload: PersonalityRequest,
    db: Session = Depends(get_db)   # ❗ Buraya dikkat: next(get_db()) YOK
):
    """
    Personality test cevaplarını kaydeder.
    Şimdilik user_id body'den geliyor, ileride JWT'den çekilebilir.
    """
    q4_joined = ", ".join(payload.q4_answer)

    record = PersonalityResponse(
        user_id=payload.user_id,
        q1_answer=payload.q1_answer,
        q2_answer=payload.q2_answer,
        q3_answer=payload.q3_answer,
        q4_answer=q4_joined,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
