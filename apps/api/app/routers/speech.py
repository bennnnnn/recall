from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.models.orm import User
from app.models.schemas import SpeechTranscriptionOut
from app.services import speech as speech_service

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/transcribe", response_model=SpeechTranscriptionOut)
async def transcribe_speech(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> SpeechTranscriptionOut:
    del user
    if not settings.speech_transcription_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    data = await file.read()
    text = await speech_service.transcribe_audio(
        settings,
        data,
        filename=file.filename or "speech.m4a",
    )
    if not text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not transcribe audio",
        )
    return SpeechTranscriptionOut(text=text)
