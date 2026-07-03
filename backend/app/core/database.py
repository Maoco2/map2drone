import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./map2drone.db",
)

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)


if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_spatialite(dbapi_connection, connection_record):
        dbapi_connection.enable_load_extension(True)
        try:
            dbapi_connection.load_extension("mod_spatialite")
        except Exception:
            pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
