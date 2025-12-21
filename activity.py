from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from auth import get_current_user
from models import User, ChatActivity, Gamification

router = APIRouter(prefix="/activity", tags=["Activity"])


@router.post("/chat", status_code=200)
def log_chat_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        db.add(ChatActivity(user_id=current_user.id))

        g = db.query(Gamification).filter(Gamification.user_id == current_user.id).first()
        if not g:
            g = Gamification(user_id=current_user.id, points=0, badge_level="Newbie")
            db.add(g)
            db.flush()

        g.points = int(g.points or 0) + 1  # her sohbet +1 puan

        db.commit()
        return {"status": "ok"}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while saving chat activity.")
