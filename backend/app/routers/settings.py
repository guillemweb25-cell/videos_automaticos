from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.user_settings import UserSettings
from app.models.global_settings import GlobalSettings
from app.models.user import User
from app.core.deps import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

class SettingsUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    leonardo_api_key: Optional[str] = None
    assemblyai_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None

class SettingsResponse(BaseModel):
    has_openai: bool
    has_leonardo: bool
    has_assemblyai: bool
    has_elevenlabs: bool

class PublicSettingsResponse(BaseModel):
    registration_enabled: bool

class GlobalSettingsUpdate(BaseModel):
    registration_enabled: bool

@router.get("/", response_model=SettingsResponse)
def get_user_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = current_user.settings
    if not settings:
        return SettingsResponse(has_openai=False, has_leonardo=False, has_assemblyai=False, has_elevenlabs=False)
    
    return SettingsResponse(
        has_openai=bool(settings.openai_api_key),
        has_leonardo=bool(settings.leonardo_api_key),
        has_assemblyai=bool(settings.assemblyai_api_key),
        has_elevenlabs=bool(settings.elevenlabs_api_key)
    )

@router.put("/", response_model=SettingsResponse)
def update_user_settings(data: SettingsUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = current_user.settings
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
    
    if data.openai_api_key is not None:
        settings.openai_api_key = data.openai_api_key
    if data.leonardo_api_key is not None:
        settings.leonardo_api_key = data.leonardo_api_key
    if data.assemblyai_api_key is not None:
        settings.assemblyai_api_key = data.assemblyai_api_key
    if data.elevenlabs_api_key is not None:
        settings.elevenlabs_api_key = data.elevenlabs_api_key
        
    db.commit()
    db.refresh(settings)
    
    return SettingsResponse(
        has_openai=bool(settings.openai_api_key),
        has_leonardo=bool(settings.leonardo_api_key),
        has_assemblyai=bool(settings.assemblyai_api_key),
        has_elevenlabs=bool(settings.elevenlabs_api_key)
    )

@router.get("/public", response_model=PublicSettingsResponse)
def get_public_settings(db: Session = Depends(get_db)):
    gs = db.query(GlobalSettings).first()
    return PublicSettingsResponse(registration_enabled=gs.registration_enabled if gs else False)

@router.post("/global", response_model=PublicSettingsResponse)
def update_global_settings(data: GlobalSettingsUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    gs = db.query(GlobalSettings).first()
    if not gs:
        gs = GlobalSettings(registration_enabled=data.registration_enabled)
        db.add(gs)
    else:
        gs.registration_enabled = data.registration_enabled
    db.commit()
    db.refresh(gs)
    return PublicSettingsResponse(registration_enabled=gs.registration_enabled)
