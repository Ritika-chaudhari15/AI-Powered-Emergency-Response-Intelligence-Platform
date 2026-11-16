from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models import User
from app.schemas import ImpactPredictionRequest, ImpactPredictionResponse
from app.services import model_service

router = APIRouter(prefix="/api/v1/predictions", tags=["Impact prediction"])


@router.post("/impact", response_model=ImpactPredictionResponse)
def predict_impact(payload: ImpactPredictionRequest, _: User = Depends(get_current_user)):
    """Predict the disaster impact score using the saved trained model."""
    try:
        impact_score = model_service.predict_impact(payload.model_dump(by_alias=True))
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except Exception:
        # Keep implementation details out of the response, while preserving server logs.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="The trained model could not make a prediction")
    return ImpactPredictionResponse(predicted_impact_score=impact_score)
