from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()
# Accept PostgreSQL's common URL form as well as SQLAlchemy's explicit psycopg3 form.
database_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()