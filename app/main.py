#!/usr/bin/env python
# coding: utf-8
import sys
import time
import argparse
import asyncio

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import logger
from app.database import DatabaseManager, Base
from app.models import Car
from app.scheduler import ScraperScheduler
from app.scraper import (
    AutoRiaScraper, create_db_dump, get_timestamp
)


async def run_scraper() -> None:
    """Run scraper job"""
    try:
        logger.info("Starting scraper job...")
        # ---------------------------------------------------------------------
        # --- Create scraper instance ---
        # ---------------------------------------------------------------------
        async with AutoRiaScraper() as scraper:
            logger.info("AutoRiaScraper instance created")

            # -----------------------------------------------------------------
            # --- Run scraper ---
            # -----------------------------------------------------------------
            start_time = time.time()
            logger.info("Beginning scraping process...")
            pages_processed, cars_saved = await scraper.run()
            end_time = time.time()

            # -----------------------------------------------------------------
            # --- Calculate execution time ---
            # -----------------------------------------------------------------
            execution_time = end_time - start_time

            logger.info(
                f"Scraper job completed in {execution_time:.2f} seconds"
            )
            logger.info(
                f"Processed {pages_processed} pages, "
                f"saved {cars_saved} new cars"
            )

    except Exception as error:
        logger.error(f"Error running scraper job: {error}", exc_info=True)


async def create_backup() -> None:
    """Create backup of database using pg_dump"""
    try:
        logger.info("Starting database backup process...")

        # ---------------------------------------------------------------------
        # --- Generate timestamped filename ---
        # ---------------------------------------------------------------------
        timestamp = get_timestamp()
        dump_filename = f"backup_{timestamp}.sql"

        # ---------------------------------------------------------------------
        # --- Create database dump ---
        # ---------------------------------------------------------------------
        success = create_db_dump(dump_filename)

        if success:
            logger.info(f"Backup created successfully: dumps/{dump_filename}")
        else:
            logger.warning("Database dump failed")

    except Exception as error:
        # ---------------------------------------------------------------------
        # --- Handle unexpected errors ---
        # ---------------------------------------------------------------------
        logger.error(f"Error creating backup: {error}", exc_info=True)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="AutoRIA Scraper")
    parser.add_argument(
        '--run-now', action='store_true', help='Run scraper immediately'
    )
    parser.add_argument(
        '--schedule', type=str, help='Set custom schedule time (HH:MM)'
    )
    parser.add_argument(
        '--backup', action='store_true', help='Create backup of current data'
    )
    return parser.parse_args()


async def main_async() -> None:
    try:
        logger.info("Starting AutoRIA Scraper application...")
        # ---------------------------------------------------------------------
        # --- Parse command line args ---
        # ---------------------------------------------------------------------
        args = parse_args()
        logger.info(
            f"Command line arguments: "
            f"run_now={args.run_now}, "
            f"schedule={args.schedule}, "
            f"backup={args.backup}"
        )

        # ---------------------------------------------------------------------
        # --- Setup database ---
        # ---------------------------------------------------------------------
        logger.info("Setting up database...")
        await DatabaseManager.create_tables_async()
        logger.info("Database tables created/verified")

        # ---------------------------------------------------------------------
        # --- Create backup ---
        # ---------------------------------------------------------------------
        if args.backup:
            logger.info("Backup flag detected, creating backup...")
            await create_backup()
            if not args.run_now and not args.schedule:
                logger.info("No other actions requested, exiting after backup")
                return

        # ---------------------------------------------------------------------
        # --- Initialize scheduler ---
        # ---------------------------------------------------------------------
        logger.info("Initializing scheduler...")
        scheduler = ScraperScheduler()

        # ---------------------------------------------------------------------
        # --- Schedule scrapper job ---
        # ---------------------------------------------------------------------
        if args.schedule:
            logger.info(f"Setting custom schedule time: {args.schedule}")
            scheduler.add_daily_job(run_scraper, args.schedule)
        else:
            logger.info("Using default schedule time from config")
            scheduler.add_daily_job(run_scraper)

        # ---------------------------------------------------------------------
        # --- Schedule backup job ---
        # ---------------------------------------------------------------------
        logger.info("Scheduling backup job...")
        scheduler.add_backup_job(create_backup)

        # ---------------------------------------------------------------------
        # --- Run now if requested ---
        # ---------------------------------------------------------------------
        if args.run_now:
            logger.info("Running scraper immediately as requested")
            await run_scraper()

        # ---------------------------------------------------------------------
        # --- Keep the main event loop alive ---
        # ---------------------------------------------------------------------
        logger.info("Entering main loop, press Ctrl+C to exit")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            await scheduler.shutdown()

    except Exception as error:
        logger.error(f"Application error: {error}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_async())
