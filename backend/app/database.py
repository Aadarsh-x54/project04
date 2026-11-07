import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine = None
_SessionLocal = None
_using_pgvector = False


def init_db_engine():
    global _engine, _SessionLocal, _using_pgvector
    if _engine is not None:
        return _engine

    # Attempt PostgreSQL + pgvector connection first
    if settings.DATABASE_URL.startswith("postgresql"):
        try:
            pg_engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 3},
            )
            with pg_engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            _engine = pg_engine
            _using_pgvector = True
            logger.info("Connected to PostgreSQL with pgvector extension enabled.")
        except Exception as exc:
            logger.warning(
                "PostgreSQL unavailable (%s). Falling back to local SQLite + vector store.",
                exc,
            )

    if _engine is None:
        _engine = create_engine(
            settings.SQLITE_FALLBACK_URL,
            connect_args={"check_same_thread": False},
        )
        _using_pgvector = False

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def is_pgvector_active() -> bool:
    init_db_engine()
    return _using_pgvector


def get_session_local():
    init_db_engine()
    return _SessionLocal


def get_db():
    session_cls = get_session_local()
    db = session_cls()
    try:
        yield db
    finally:
        db.close()

