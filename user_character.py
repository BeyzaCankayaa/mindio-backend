
print("USER_CHARACTER ROUTER LOADED")

# user_character.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models import User, Gamification, UserCharacter, Character  # örnek ilişkiler

router = APIRouter(prefix="/user/characters", tags=["Characters"])

class UserCharactersResponse(BaseModel):
    points: int
    owned_character_ids: list[int]
    active_character_id: int | None
    asset_key: str | None

class BuyBody(BaseModel):
    character_id: int

class ActiveBody(BaseModel):
    character_id: int

@router.get("", response_model=UserCharactersResponse)
def get_user_characters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # points
    g = db.query(Gamification).filter(Gamification.user_id == current_user.id).first()
    points = int(g.points) if g else 0

    rows = db.query(UserCharacter).filter(UserCharacter.user_id == current_user.id).all()
    owned_ids = [r.character_id for r in rows]
    active_id = next((r.character_id for r in rows if r.is_active), None)

    asset_key = None
    if active_id:
        c = db.query(Character).filter(Character.id == active_id).first()
        asset_key = c.asset_key if c else None

    return {
        "points": points,
        "owned_character_ids": owned_ids,
        "active_character_id": active_id,
        "asset_key": asset_key,
    }

@router.post("/buy", response_model=UserCharactersResponse)
def buy_character(
    body: BuyBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    char = db.query(Character).filter(Character.id == body.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="character_not_found")

    g = db.query(Gamification).filter(Gamification.user_id == current_user.id).order_by(Gamification.id.desc()).first()
    if not g:
        g = Gamification(user_id=current_user.id, points=0, badge_level="Newbie")
        db.add(g)
        db.commit()
        db.refresh(g)

    if int(g.points) < int(char.cost):
        raise HTTPException(status_code=400, detail="insufficient_points")

    already = db.query(UserCharacter).filter(
        UserCharacter.user_id == current_user.id,
        UserCharacter.character_id == body.character_id
    ).first()
    if already:
        return get_user_characters(db, current_user)

    # ✅ 1) puanı düş
    g.points = int(g.points) - int(char.cost)
    db.add(g)

    # ✅ 2) satın alımı yaz
    db.add(UserCharacter(user_id=current_user.id, character_id=body.character_id, is_active=False))

    # ✅ 3) commit + refresh
    db.commit()
    db.refresh(g)

    return get_user_characters(db, current_user)


@router.put("/active", response_model=UserCharactersResponse)
def set_active_character(
    body: ActiveBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owned = db.query(UserCharacter).filter(
        UserCharacter.user_id == current_user.id,
        UserCharacter.character_id == body.character_id
    ).first()
    if not owned:
        raise HTTPException(status_code=400, detail="not_owned")

    # hepsini pasif yap
    db.query(UserCharacter).filter(UserCharacter.user_id == current_user.id).update({"is_active": False})
    # seçileni aktif yap
    owned.is_active = True
    db.commit()

    return get_user_characters(db, current_user)
