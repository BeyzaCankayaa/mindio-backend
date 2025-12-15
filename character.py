# character.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Character  # Character modelin varsa

router = APIRouter(prefix="/shop", tags=["Characters"])

class CharacterDTO(BaseModel):
    id: int
    name: str
    asset_key: str
    cost: int

    class Config:
        from_attributes = True

@router.get("/characters", response_model=list[CharacterDTO])
def get_shop_characters(db: Session = Depends(get_db)):
    return db.query(Character).order_by(Character.id.asc()).all()
