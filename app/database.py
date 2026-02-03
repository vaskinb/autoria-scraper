#!/usr/bin/env python
# coding: utf-8
# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Any, Dict, Optional, Type, TypeVar

# -----------------------------------------------------------------------------
# --- SQLAlchemy ---
# -----------------------------------------------------------------------------
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import DB_URL, logger
from app.models import Base, Car

# -----------------------------------------------------------------------------
# --- Type variable for ORM model classes ---
# -----------------------------------------------------------------------------
T = TypeVar('T')

# -----------------------------------------------------------------------------
# --- Create SQLAlchemy engine ---
# -----------------------------------------------------------------------------
async_engine = create_async_engine(
    DB_URL, echo=False, pool_pre_ping=True
)
AsyncSessionLocal = async_sessionmaker(
    async_engine, autocommit=False, autoflush=False, expire_on_commit=False
)


class DatabaseManager:

    @staticmethod
    async def get_async_session() -> AsyncSession:
        """Get async session"""
        session = AsyncSessionLocal()
        try:
            return session
        except SQLAlchemyError as error:
            await session.close()
            logger.error(f"Async database session error: {error}")
            raise

    @staticmethod
    async def create_tables_async() -> None:
        """Create all tables defined in models (async)"""
        try:
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully (async)")
        except SQLAlchemyError as error:
            logger.error(f"Error creating database tables (async): {error}")
            raise

    @staticmethod
    async def add_item_async(item: Base) -> Optional[Base]:
        """Add a single item to the database (async)"""
        logger.debug(f"Adding item asynchronously {item.to_dict()}")

        session = await DatabaseManager.get_async_session()
        try:
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item
        except SQLAlchemyError as error:
            await session.rollback()
            logger.error(f"Error adding item to database (async): {error}")
            return None
        finally:
            await session.close()

    @staticmethod
    async def update_car_by_url_async(
            url: str, car_data: Dict[str, Any]
    ) -> bool:
        """Update car item by its URL (async)"""
        session = await DatabaseManager.get_async_session()
        try:
            # -----------------------------------------------------------------
            # --- Do not update primary key or creation date ---
            # -----------------------------------------------------------------
            car_data.pop('url', None)
            car_data.pop('datetime_found', None)

            # -----------------------------------------------------------------
            # --- Create and execute update statement ---
            # -----------------------------------------------------------------
            stmt = update(Car).where(Car.url == url).values(**car_data)
            result = await session.execute(stmt)
            await session.commit()

            # -----------------------------------------------------------------
            # --- Check if any row was updated ---
            # -----------------------------------------------------------------
            if result.rowcount > 0:
                logger.info(f"Car {url} updated successfully.")
                return True
            else:
                logger.warning(f"Car {url} not found for update.")
                return False
        except SQLAlchemyError as error:
            await session.rollback()
            logger.error(f"Error updating car {url} (async): {error}")
            return False
        finally:
            await session.close()

    @staticmethod
    async def exists_by_field_async(
            model: Type[T], field_name: str, value: Any
    ) -> bool:
        """Check if item exists (async)"""
        session = await DatabaseManager.get_async_session()
        try:
            stmt = (
                model.__table__.select()
                .where(getattr(model, field_name) == value)
                .limit(1)
            )
            result = await session.execute(stmt)
            exists = result.first() is not None
            return exists
        except SQLAlchemyError as error:
            logger.error(
                f"Error checking existence in database (async): {error}")
            return False
        finally:
            await session.close()
