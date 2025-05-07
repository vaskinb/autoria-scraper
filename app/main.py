#!/usr/bin/env python
# coding: utf-8
import sys
import time
import argparse
import os

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import logger
from app.database import DatabaseManager, Base, engine
from app.models import Car
from app.scheduler import ScraperScheduler
from app.scraper import (
    AutoRiaScraper, save_to_json, save_to_csv, get_timestamp
)


def run_scraper() -> None:
    """Run scraper job"""
    try:
        logger.info("Starting scraper job...")
        # ---------------------------------------------------------------------
        # --- Create scraper instance ---
        # ---------------------------------------------------------------------
        scraper = AutoRiaScraper()
        logger.info("AutoRiaScraper instance created")

        # ---------------------------------------------------------------------
        # --- Run scraper ---
        # ---------------------------------------------------------------------
        start_time = time.time()
        logger.info("Beginning scraping process...")
        pages_processed, cars_saved = scraper.run()
        end_time = time.time()

        # ---------------------------------------------------------------------
        # --- Calculate execution time ---
        # ---------------------------------------------------------------------
        execution_time = end_time - start_time

        logger.info(f"Scraper job completed in {execution_time:.2f} seconds")
        logger.info(
            f"Processed {pages_processed} pages, saved {cars_saved} new cars"
        )

    except Exception as error:
        logger.error(f"Error running scraper job: {error}", exc_info=True)


def create_backup() -> None:
    """Create backup of database data"""
    try:
        logger.info("Starting database backup process...")
        # ---------------------------------------------------------------------
        # --- Get all cars from database ---
        # ---------------------------------------------------------------------
        session = DatabaseManager.get_session()
        logger.info("Database session created, querying cars...")
        cars = session.query(Car).all()
        cars_count = len(cars)
        logger.info(f"Retrieved {cars_count} cars from database")
        session.close()

        if not cars:
            logger.info("No cars to backup")
            return

        # ---------------------------------------------------------------------
        # --- Convert to dicts ---
        # ---------------------------------------------------------------------
        logger.info("Converting car objects to dictionaries...")
        car_dicts = [car.to_dict() for car in cars]

        # ---------------------------------------------------------------------
        # --- Create backup ---
        # ---------------------------------------------------------------------
        timestamp = get_timestamp()
        json_filename = f"backup_{timestamp}.json"
        csv_filename = f"backup_{timestamp}.csv"

        # ---------------------------------------------------------------------
        # --- Make dumps dir if not exists ---
        # ---------------------------------------------------------------------
        dumps_dir = os.path.join(os.getcwd(), "dumps")
        if not os.path.exists(dumps_dir):
            logger.info(f"Creating dumps directory: {dumps_dir}")
            os.makedirs(dumps_dir)

        json_path = os.path.join(dumps_dir, json_filename)
        csv_path = os.path.join(dumps_dir, csv_filename)

        logger.info(f"Preparing to save backup to {json_path} and {csv_path}")

        # ---------------------------------------------------------------------
        # --- Save backups ---
        # ---------------------------------------------------------------------
        logger.info(f"Saving JSON backup to {json_filename}...")
        save_to_json(car_dicts, json_filename)
        logger.info(f"JSON backup saved successfully")

        logger.info(f"Saving CSV backup to {csv_filename}...")
        save_to_csv(car_dicts, csv_filename)
        logger.info(f"CSV backup saved successfully")

        logger.info(f"Created backup with {len(car_dicts)} cars")

    except Exception as error:
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


def main() -> None:
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
        DatabaseManager.create_tables()
        logger.info("Database tables created/verified")

        # ---------------------------------------------------------------------
        # --- Create backup ---
        # ---------------------------------------------------------------------
        if args.backup:
            logger.info("Backup flag detected, creating backup...")
            create_backup()
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
            scheduler.run_immediately(run_scraper)

        # ---------------------------------------------------------------------
        # --- Keep the main thread alive ---
        # ---------------------------------------------------------------------
        logger.info("Entering main loop, press Ctrl+C to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            scheduler.shutdown()

    except Exception as error:
        logger.error(f"Application error: {error}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
