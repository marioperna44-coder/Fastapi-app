from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# SQLite-Datenbank im Projektordner
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./app.db"
)

# Engine & Session
engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Basisklasse für Modelle
Base = declarative_base()

 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()