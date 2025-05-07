#!/usr/bin/env python
# coding: utf-8
import csv
import json
import os
import random
import re
from datetime import datetime

# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Any, Dict, List, Optional

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import logger


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


def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
    try:
        # ---------------------------------------------------------------------
        # --- Ensure directory exists ---
        # ---------------------------------------------------------------------
        os.makedirs("dumps", exist_ok=True)

        # ---------------------------------------------------------------------
        # --- Full path to file ---
        # ---------------------------------------------------------------------
        filepath = os.path.join("dumps", filename)

        # ---------------------------------------------------------------------
        # --- Convert datetime objects to strings ---
        # ---------------------------------------------------------------------
        serializable_data = []
        for item in data:
            serializable_item = item.copy()
            for key, value in serializable_item.items():
                if isinstance(value, datetime):
                    serializable_item[key] = value.isoformat()
            serializable_data.append(serializable_item)

        # ---------------------------------------------------------------------
        # --- Save to file ---
        # ---------------------------------------------------------------------
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Data saved to {filepath}")
    except Exception as error:
        logger.error(f"Error saving data to JSON: {error}")


def save_to_csv(data: List[Dict[str, Any]], filename: str) -> None:
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
        # --- Convert datetime objects to strings ---
        # ---------------------------------------------------------------------
        serializable_data = []
        for item in data:
            serializable_item = item.copy()
            for key, value in serializable_item.items():
                if isinstance(value, datetime):
                    serializable_item[key] = value.isoformat()
            serializable_data.append(serializable_item)

        # ---------------------------------------------------------------------
        # --- Get fieldnames from first item ---
        # ---------------------------------------------------------------------
        if serializable_data:
            fieldnames = list(serializable_data[0].keys())

            # -----------------------------------------------------------------
            # --- Save to file ---
            # -----------------------------------------------------------------
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(serializable_data)

            logger.info(f"Data saved to {filepath}")
        else:
            logger.warning("No data to save to CSV")
    except Exception as error:
        logger.error(f"Error saving data to CSV: {error}")


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
