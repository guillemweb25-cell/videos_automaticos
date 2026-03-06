from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.channel import Channel
from app.models.user import User
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelUpdate
from app.core.deps import get_current_user

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    channel_data: ChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo canal para el usuario actual."""
    channel = Channel(
        **channel_data.model_dump(),
        user_id=current_user.id
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/", response_model=List[ChannelResponse])
def get_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene todos los canales del usuario actual."""
    return db.query(Channel).filter(Channel.user_id == current_user.id).all()


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina un canal."""
    channel = db.query(Channel).filter(
        Channel.id == channel_id, 
        Channel.user_id == current_user.id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    db.delete(channel)
    db.commit()
    return None

@router.patch("/{channel_id}", response_model=ChannelResponse)
def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza un canal del usuario actual."""
    channel = db.query(Channel).filter(
        Channel.id == channel_id, 
        Channel.user_id == current_user.id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    update_data = channel_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(channel, key, value)
    
    db.commit()
    db.refresh(channel)
    return channel
