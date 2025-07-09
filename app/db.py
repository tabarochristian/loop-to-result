from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base  # import your SQLAlchemy Base metadata
import os
import logging

# Determine absolute path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
DB_PATH = os.path.join(DATA_DIR, "db.sqlite3")

# Ensure `data/` folder exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)
    logging.info(f"Created database directory at {DATA_DIR}")

SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"

# SQLite specific: `check_same_thread=False` to allow multithreaded access
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False}
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create tables if database file does not exist
if not os.path.exists(DB_PATH):
    logging.info("Database file not found. Creating new database and tables...")
    Base.metadata.create_all(bind=engine)
    logging.info("Database initialized successfully.")
