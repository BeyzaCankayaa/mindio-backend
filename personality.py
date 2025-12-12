# personality.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import PersonalityResponse

router = APIRouter(
    prefix="/personality",
    tags=["Personality"]
)

# ----------------------------
# 1️⃣ REQUEST SCHEMA
# Flutter’dan gelen veri
# ----------------------------
class PersonalityRequest(BaseModel):
    user_id: int
    q1_answer: str   # yaş aralığı
    q2_answer: str   # cinsiyet
    q3_answer: str   # ruh hali
    q4_answer: list[str]  # destek konuları (çoklu)


# ----------------------------
# 2️⃣ RESPONSE SCHEMA
# DB’den dönen veri
# ----------------------------
class PersonalityResponseDTO(BaseModel):
    id: int
    user_id: int
    q1_answer: str
    q2_answer: str
    q3_answer: str
    q4_answer: str  # DB'de string olarak tutuluyor

    class Config:
        orm_mode = True


# ----------------------------
# 3️⃣ DATABASE CONNECTION
# ----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------
# 4️⃣ SUBMIT ENDPOINT
# ----------------------------
@router.post("/submit", response_model=PersonalityResponseDTO)
def submit_personality(
    payload: PersonalityRequest,
    db: Session = Depends(get_db)
):
    """
    Kullanıcının kişilik testi cevaplarını alır
    ve veritabanına kaydeder.
    """

    # Çoklu cevapları stringe çeviriyoruz
    q4_joined = ", ".join(payload.q4_answer)

    # DB kaydı oluştur
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
