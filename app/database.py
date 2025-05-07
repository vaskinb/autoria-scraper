#!/usr/bin/env python
# coding: utf-8
# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Any, Dict, Optional, Type, TypeVar

# -----------------------------------------------------------------------------
# --- SQLAlchemy ---
# -----------------------------------------------------------------------------
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declared_attr

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import DB_URL, logger

# -----------------------------------------------------------------------------
# --- Type variable for ORM model classes ---
# -----------------------------------------------------------------------------
T = TypeVar('T')

# -----------------------------------------------------------------------------
# --- Create SQLAlchemy engine ---
# -----------------------------------------------------------------------------
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        return {c.key: getattr(self, c.key) for c in
                inspect(self).mapper.column_attrs}


class DatabaseManager:

    @staticmethod
    def get_session() -> Session:
        session = SessionLocal()
        try:
            return session
        except SQLAlchemyError as error:
            session.close()
            logger.error(f"Database session error: {error}")
            raise

    @staticmethod
    def create_tables() -> None:
        """Create all tables defined in models"""
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as error:
            logger.error(f"Error creating database tables: {error}")
            raise

    @staticmethod
    def add_item(item: Base) -> Optional[Base]:
        """Add a single item to the database"""
        logger.debug(f"Adding item {item.to_dict()}")

        session = DatabaseManager.get_session()
        try:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item
        except SQLAlchemyError as error:
            session.rollback()
            logger.error(f"Error adding item to database: {error}")
            return None
        finally:
            session.close()

    @staticmethod
    def exists_by_field(model: Type[T], field_name: str, value: Any) -> bool:
        """Check if item exists"""
        session = DatabaseManager.get_session()
        try:
            exists = session.query(model).filter(
                getattr(model, field_name) == value
            ).first() is not None
            return exists
        except SQLAlchemyError as error:
            logger.error(f"Error checking existence in database: {error}")
            return False
        finally:
            session.close()
