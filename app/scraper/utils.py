#!/usr/bin/env python
# coding: utf-8
import os
import random
import re
import subprocess
from datetime import datetime

# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Any, Dict, List, Optional

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import logger, BACKUP_URL


def clean_text(text: str) -> str:
    if not text:
        return ""

    # -------------------------------------------------------------------------
    # --- Replace spaces and newlines ---
    # -------------------------------------------------------------------------
    cleaned = re.sub(r'\s+', ' ', text)

    # -------------------------------------------------------------------------
    # --- Strip spaces ---
    # -------------------------------------------------------------------------
    cleaned = cleaned.strip()

    return cleaned


def extract_number(text: str) -> Optional[float]:
    if not text:
        return None

    # -------------------------------------------------------------------------
    # --- Remove non-numeric characters except dots and commas ---
    # -------------------------------------------------------------------------
    cleaned = re.sub(r'[^\d\.,]', '', text)

    # -------------------------------------------------------------------------
    # --- Replace commas with dots ---
    # -------------------------------------------------------------------------
    cleaned = cleaned.replace(',', '.')

    # -------------------------------------------------------------------------
    # --- Find all numbers in text ---
    # -------------------------------------------------------------------------
    numbers = re.findall(r'\d+\.?\d*', cleaned)

    if numbers:
        try:
            return float(numbers[0])
        except ValueError:
            return None

    return None


def get_random_delay(base_delay: float) -> float:
    # -------------------------------------------------------------------------
    # --- Add random offset in range of ±30% of base delay ---
    # -------------------------------------------------------------------------
    offset = random.uniform(-0.3, 0.3) * base_delay
    return max(0.5, base_delay + offset)


def create_db_dump(filename: str) -> bool:
    try:
        # ---------------------------------------------------------------------
        # --- Ensure directory exists ---
        # ---------------------------------------------------------------------
        os.makedirs("dumps", exist_ok=True)

        # ---------------------------------------------------------------------
        # --- Create full path to file ---
        # ---------------------------------------------------------------------
        filepath = os.path.join("dumps", filename)

        # ---------------------------------------------------------------------
        # --- Create pg_dump command ---
        # ---------------------------------------------------------------------
        cmd = [
            'pg_dump',
            f'--dbname={BACKUP_URL}',
            '--clean',
            '--if-exists',
            f'--file={filepath}'
        ]

        # ---------------------------------------------------------------------
        # --- Execute pg_dump command ---
        # ---------------------------------------------------------------------
        result = subprocess.run(cmd, capture_output=True, text=True)

        # ---------------------------------------------------------------------
        # --- Check result and log output ---
        # ---------------------------------------------------------------------
        if result.returncode == 0:
            logger.info(f"Database dump successfully created at {filepath}")
            return True
        else:
            logger.error(f"Error during database dump: {result.stderr}")
            return False

    except Exception as error:
        # ---------------------------------------------------------------------
        # --- Handle unexpected errors ---
        # ---------------------------------------------------------------------
        logger.exception(f"Unexpected error during database dump: {error}")
        return False


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
