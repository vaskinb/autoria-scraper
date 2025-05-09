#!/usr/bin/env python
# coding: utf-8
import os

from dotenv import load_dotenv
from loguru import logger

# -----------------------------------------------------------------------------
# --- Loading env variables ---
# -----------------------------------------------------------------------------
load_dotenv()

# -----------------------------------------------------------------------------
# --- Database Configuration ---
# -----------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "autoria")
DB_PASSWORD = os.getenv("DB_PASSWORD", "autopassword")
DB_NAME = os.getenv("DB_NAME", "autoria_db")

# -----------------------------------------------------------------------------
# --- Connection string ---
# -----------------------------------------------------------------------------
DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
BACKUP_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# -----------------------------------------------------------------------------
# --- Scraper config ---
# -----------------------------------------------------------------------------
START_URL = os.getenv("START_URL", "https://auto.ria.com/uk/car/used")
SCRAPER_RUN_TIME = os.getenv("SCRAPER_RUN_TIME", "12:00")
BACKUP_RUN_TIME = os.getenv("BACKUP_RUN_TIME", "23:00")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
REQUEST_DELAY = int(os.getenv("REQUEST_DELAY", "2"))
CAR_SEMAPHORE_VALUE = int(os.getenv("REQUEST_TIMEOUT", "5"))
PAGE_SEMAPHORE_VALUE = int(os.getenv("REQUEST_DELAY", "3"))

# -----------------------------------------------------------------------------
# --- Headers for HTTP requests ---
# -----------------------------------------------------------------------------
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Connection": "keep-alive"
}

# -----------------------------------------------------------------------------
# --- Logging configuration ---
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "{time} | {level} | {message}")
LOG_ROTATION = os.getenv("LOG_ROTATION", "500 MB")

# -----------------------------------------------------------------------------
# --- Configure logger ---
# -----------------------------------------------------------------------------
logger.remove()
logger.add(
    "logs/autoria_scraper.log",
    rotation=LOG_ROTATION,
    format=LOG_FORMAT,
    level=LOG_LEVEL,
    enqueue=True
)
logger.add(
    lambda msg: print(msg),
    format=LOG_FORMAT,
    level=LOG_LEVEL
)

# -----------------------------------------------------------------------------
# --- Create dumps directory if not exists ---
# -----------------------------------------------------------------------------
os.makedirs("dumps", exist_ok=True)
os.makedirs("logs", exist_ok=True)
