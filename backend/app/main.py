from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.database import Base, SessionLocal, engine
from app.routers import allocations, analytics, auth, disaster_reports, knowledge_base, localization, notifications, operations, predictions, updates, users, volunteers, warehouses
from app.services.operations_service import seed_warehouse_stock
from app.services.translation_service import ensure_catalog, resolve_locale, translate_api_detail


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Lightweight forward migration for installations created before live
    # vehicle telemetry was added. New databases receive these via create_all.
    columns = {column["name"] for column in inspect(engine).get_columns("vehicle_tracking")}
    additions = {
        "route_geometry": "JSON", "route_distance_km": "FLOAT DEFAULT 0 NOT NULL",
        "speed_kmph": "FLOAT DEFAULT 45 NOT NULL", "estimated_arrival_at": "TIMESTAMP",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE vehicle_tracking ADD COLUMN {name} {definition}"))
    db = SessionLocal()
    try:
        seed_warehouse_stock(db)
        ensure_catalog(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Disaster Response API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def set_request_locale(request: Request, call_next):
    locale = resolve_locale(request.query_params.get("lang"), request.headers.get("accept-language"))
    request.state.locale = locale
    response = await call_next(request)
    response.headers["Content-Language"] = locale
    vary_values = {value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()}
    vary_values.add("Accept-Language")
    response.headers["Vary"] = ", ".join(sorted(vary_values))
    return response


@app.exception_handler(HTTPException)
async def localize_http_exception(request: Request, exc: HTTPException):
    locale = getattr(request.state, "locale", "en")
    db = SessionLocal()
    try:
        detail = translate_api_detail(db, exc.detail, locale)
    except Exception:
        # Translation must never prevent the API from returning the original error.
        detail = exc.detail
    finally:
        db.close()
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(predictions.router)
app.include_router(allocations.router)
app.include_router(warehouses.router)
app.include_router(operations.team_router)
app.include_router(operations.report_router)
app.include_router(operations.stock_router)
app.include_router(disaster_reports.router)
app.include_router(analytics.router)
app.include_router(knowledge_base.router)
app.include_router(volunteers.router)
app.include_router(notifications.router)
app.include_router(updates.router)
app.include_router(localization.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
