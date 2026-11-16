from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models import User
from app.schemas import ResourceAllocationRequest, ResourceAllocationResponse
from app.services import allocation_service


router = APIRouter(prefix="/api/v1/resource-allocation", tags=["Resource allocation"])


@router.post("", response_model=ResourceAllocationResponse)
def allocate_resources(payload: ResourceAllocationRequest, _: User = Depends(get_current_user)):
    """Allocate supplies from the nearest warehouse, then each next-nearest warehouse."""
    try:
        return allocation_service.allocate_resources(
            latitude=payload.latitude,
            longitude=payload.longitude,
            required_resources=payload.required_resources,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
