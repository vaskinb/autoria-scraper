#!/usr/bin/env python
# coding: utf-8
# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Callable, Optional
import asyncio

# -----------------------------------------------------------------------------
# --- Apscheduler ---
# -----------------------------------------------------------------------------
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import SCRAPER_RUN_TIME, BACKUP_RUN_TIME, logger


class ScraperScheduler:
    """Scheduler for running scraper"""

    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Scheduler initialized")

    def _wrap_async_job(self, job_func: Callable) -> Callable:
        def wrapper():
            asyncio.get_event_loop().create_task(job_func())
        return wrapper

    def add_daily_job(
            self, job_func: Callable, job_time: Optional[str] = None
    ) -> None:
        if job_time is None:
            job_time = SCRAPER_RUN_TIME

        # ---------------------------------------------------------------------
        # --- Split job time ---
        # ---------------------------------------------------------------------
        hour, minute = job_time.split(":")

        # ---------------------------------------------------------------------
        # --- Add job with cron trigger ---
        # ---------------------------------------------------------------------
        self.scheduler.add_job(
            self._wrap_async_job(job_func),
            CronTrigger(hour=hour, minute=minute),
            id="daily_scraper",
            replace_existing=True
        )

        logger.info(f"Daily job scheduled at {job_time}")

    def add_backup_job(
            self, job_func: Callable, job_time: Optional[str] = None
    ) -> None:
        if job_time is None:
            job_time = BACKUP_RUN_TIME

        hour, minute = job_time.split(":")

        self.scheduler.add_job(
            self._wrap_async_job(job_func),
            CronTrigger(hour=int(hour), minute=int(minute)),
            id="daily_backup",
            replace_existing=True
        )

        logger.info(f"Backup job scheduled at {job_time}")

    def add_interval_job(self, job_func: Callable, hours: int = 24) -> None:
        self.scheduler.add_job(
            self._wrap_async_job(job_func),
            IntervalTrigger(hours=hours),
            id="interval_scraper",
            replace_existing=True
        )

        logger.info(f"Interval job scheduled every {hours} hours")

    def run_immediately(self, job_func: Callable) -> None:
        logger.info("Running scraper job immediately")

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            loop.create_task(job_func())
        else:
            loop.run_until_complete(job_func())

    def shutdown(self) -> None:
        self.scheduler.shutdown()
        logger.info("Scheduler shutdown")
