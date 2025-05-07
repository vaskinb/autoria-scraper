#!/usr/bin/env python
# coding: utf-8
from datetime import datetime

# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Any, Dict

# -----------------------------------------------------------------------------
# --- AQLAlchemy ---
# -----------------------------------------------------------------------------
from sqlalchemy import Column, DateTime, Float, Integer, String

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.database import Base


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String(500), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    price_usd = Column(Float, nullable=True)
    odometer = Column(Integer, nullable=True)
    username = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    image_url = Column(String(500), nullable=True)
    images_count = Column(Integer, nullable=True)
    car_number = Column(String(20), nullable=True)
    car_vin = Column(String(50), nullable=True)
    datetime_found = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<Car {self.id}: {self.title}>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "price_usd": self.price_usd,
            "odometer": self.odometer,
            "username": self.username,
            "phone_number": self.phone_number,
            "image_url": self.image_url,
            "images_count": self.images_count,
            "car_number": self.car_number,
            "car_vin": self.car_vin,
            "datetime_found": self.datetime_found.isoformat(),
        }
