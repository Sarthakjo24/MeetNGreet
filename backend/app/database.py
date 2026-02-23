from collections.abc import Generator
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings


def _build_database_url() -> str:
    if settings.use_local_db:
        db_path = Path(settings.local_db_path).expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"

    if settings.database_url:
        return settings.database_url

    password = quote_plus(settings.mysql_password)
    return (
        "mysql+pymysql://"
        f"{settings.mysql_user}:{password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
    )


database_url = _build_database_url()
connect_args: dict[str, bool] = {}
if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(database_url, future=True, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
