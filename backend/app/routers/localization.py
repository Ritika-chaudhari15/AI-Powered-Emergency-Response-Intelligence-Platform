from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.indictrans_local_service import LocalIndicTransUnavailable
from app.services.translation_service import DEFAULT_LOCALE, SUPPORTED_LOCALES, get_bundle

router = APIRouter(prefix="/api/v1/i18n", tags=["Localization"])


@router.get("/languages")
def list_languages():
    """Public endpoint: language selector can be populated before login."""
    return {"default": DEFAULT_LOCALE, "supported": [{"code": code, "name": name} for code, name in SUPPORTED_LOCALES.items()]}


@router.get("/status")
def translation_service_status():
    """Public diagnostic endpoint; does not initialize or load the model."""
    from app.config import get_settings
    from pathlib import Path

    settings = get_settings()
    backend_path = Path(__file__).resolve().parents[2]
    configured_path = Path(settings.indictrans_model_path)
    model_path = configured_path if configured_path.is_absolute() else backend_path / configured_path
    return {
        "translation_provider": "local_indictrans2",
        "model_files_present": model_path.is_dir(),
        "model_load_deferred": True,
        "configured_device": settings.indictrans_device,
    }


@router.get("/bundle")
def get_translation_bundle(request: Request, db: Session = Depends(get_db)):
    """Public cache-first UI bundle; local model runs only for uncached values."""
    try:
        translations = get_bundle(db, request.state.locale)
    except LocalIndicTransUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return {"locale": request.state.locale, "translations": translations}
