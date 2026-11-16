from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, WarehouseStock
from app.schemas import WarehouseResponse
from app.services import allocation_service
from app.services.translation_service import translate


router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouses"])


@router.get("", response_model=list[WarehouseResponse])
def list_warehouses(request: Request, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List every warehouse, including its location and available resource quantities."""
    # This is the operational inventory, not the immutable CSV seed file.  It
    # therefore reflects allocations, cancellations, and returns immediately.
    stocks = list(db.scalars(select(WarehouseStock).order_by(WarehouseStock.warehouse_id, WarehouseStock.resource)))
    warehouses: dict[str, dict] = {}
    for stock in stocks:
        warehouse = warehouses.setdefault(stock.warehouse_id, {
            "warehouse_id": stock.warehouse_id,
            # Keep the source name intact in warehouse_stock; translated display
            # values are generated/cached per locale in the translation tables.
            "warehouse_name": translate(db, f"warehouse.name.{stock.warehouse_id}", stock.warehouse_name, request.state.locale),
            "state": stock.state, "latitude": stock.latitude, "longitude": stock.longitude, "inventory": [],
        })
        warehouse["inventory"].append({"resource": stock.resource, "available_quantity": stock.available_quantity})
    return list(warehouses.values())
