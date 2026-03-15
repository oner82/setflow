from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_PATH = os.environ.get("SETFLOW_DB_PATH", os.path.join("data", "setflow.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

ENGINE = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass
