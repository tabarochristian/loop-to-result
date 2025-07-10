import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from models import Base
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def get_database_uri() -> str:
    """
    Retrieves the database URI, configurable via environment variables.
    Defaults to SQLite in the data directory.
    """
    base_dir = os.path.abspath(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, "..", "data")
    default_db_path = os.path.join(data_dir, "db.sqlite3")
    
    db_path = os.getenv("DATABASE_PATH", default_db_path)
    
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        logger.info(f"Ensured database directory exists at {os.path.dirname(db_path)}")
    except OSError as e:
        logger.error(f"Failed to create database directory: {str(e)}")
        raise RuntimeError(f"Cannot create database directory: {str(e)}")
    
    return f"sqlite:///{db_path}"

def initialize_database(engine) -> None:
    """
    Initializes the database by creating tables if they don't exist.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except OperationalError as e:
        logger.error(f"Failed to initialize database tables: {str(e)}")
        raise RuntimeError(f"Database initialization failed: {str(e)}")

# Get database URI
SQLALCHEMY_DATABASE_URI = get_database_uri()

# Create engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    echo=False
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

@asynccontextmanager
async def get_db() -> AsyncGenerator[Session, None]:
    """
    Async context manager for database sessions.
    Usage: async with get_db() as db: ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        db.close()

# Dependency for FastAPI to get a Session object
async def get_session():
    async with get_db() as session:
        yield session

# Initialize database on module import
try:
    initialize_database(engine)
except Exception as e:
    logger.critical(f"Failed to initialize database: {str(e)}")
    raise