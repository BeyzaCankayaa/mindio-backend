# rewards.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models import Reward, RewardClaim, Gamification, User

router = APIRouter(prefix="/rewards", tags=["Rewards"])


class ClaimBody(BaseModel):
    reward_id: int


@router.post("/claim")
def claim_reward(
    body: ClaimBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reward = db.query(Reward).filter(Reward.id == body.reward_id, Reward.is_active == True).first()
    if not reward:
        raise HTTPException(status_code=404, detail="reward_not_found")

    already = db.query(RewardClaim).filter(
        RewardClaim.user_id == current_user.id,
        RewardClaim.reward_id == reward.id
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="already_claimed")

    g = db.query(Gamification).filter(Gamification.user_id == current_user.id).first()
    if not g:
        g = Gamification(user_id=current_user.id, points=0)
        db.add(g)
        db.commit()
        db.refresh(g)

    g.points += reward.points
    db.add(RewardClaim(user_id=current_user.id, reward_id=reward.id))
    db.commit()

    return {
        "points_added": reward.points,
        "new_points": g.points
    }

