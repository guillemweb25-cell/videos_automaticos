from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.lora import Lora
from app.models.user import User
from app.schemas.lora import LoraCreate, LoraUpdate, LoraResponse
from app.core.deps import get_current_user
from app.services.comfy_service import ComfyService

router = APIRouter(prefix="/loras", tags=["loras"])


@router.get("/available-files", response_model=List[str])
async def available_lora_files(current_user: User = Depends(get_current_user)):
    """The LoRA files ComfyUI can load right now (for the file picker in the UI).
    Returned verbatim from ComfyUI, so the exact strings are safe to store."""
    return await ComfyService().get_available_loras()


@router.get("/", response_model=List[LoraResponse])
def list_loras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Lora)
        .filter(Lora.user_id == current_user.id)
        .order_by(Lora.label)
        .all()
    )


@router.post("/", response_model=LoraResponse, status_code=status.HTTP_201_CREATED)
def create_lora(
    data: LoraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lora = Lora(**data.model_dump(), user_id=current_user.id)
    db.add(lora)
    db.commit()
    db.refresh(lora)
    return lora


@router.patch("/{lora_id}", response_model=LoraResponse)
def update_lora(
    lora_id: int,
    data: LoraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lora = db.query(Lora).filter(Lora.id == lora_id, Lora.user_id == current_user.id).first()
    if not lora:
        raise HTTPException(status_code=404, detail="LoRA no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(lora, key, value)
    db.commit()
    db.refresh(lora)
    return lora


@router.delete("/{lora_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lora(
    lora_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lora = db.query(Lora).filter(Lora.id == lora_id, Lora.user_id == current_user.id).first()
    if not lora:
        raise HTTPException(status_code=404, detail="LoRA no encontrado")
    db.delete(lora)
    db.commit()
    return None
