from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.core.deps import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])

class UserAdminResponse(BaseModel):
    id: int
    email: str
    is_admin: bool
    credits: int
    created_at: datetime
    video_count: int

class AddCreditsRequest(BaseModel):
    amount: int

@router.get("/users", response_model=List[UserAdminResponse])
def get_all_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    users = db.query(User).all()
    result = []
    for user in users:
        video_count = db.query(Video).join(User.channels).filter(User.id == user.id).count()
        # Note: This query might need optimization for many users, but fine for now
        result.append({
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
            "credits": user.credits,
            "created_at": user.created_at,
            "video_count": video_count
        })
    return result

@router.post("/users/{user_id}/add-credits")
def add_credits(user_id: int, data: AddCreditsRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user.credits += data.amount
    db.commit()
    db.refresh(user)
    return user

@router.get("/stats")
def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    total_users = db.query(User).count()
    total_videos = db.query(Video).count()
    total_credits = db.query(User).with_entities(func.sum(User.credits)).scalar() or 0
    
    return {
        "total_users": total_users,
        "total_videos": total_videos,
        "total_credits": total_credits
    }

from sqlalchemy import func
