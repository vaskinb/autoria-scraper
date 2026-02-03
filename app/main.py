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
from app.database import DatabaseManager
from app.scheduler import ScraperScheduler
from app.scraper import (
    AutoRiaScraper, create_db_dump, get_timestamp
)


async def test_initial_scrape_and_first_car() -> None:
    """Test initial scrape pagination and first car detail parsing."""
    try:
        logger.info("Starting diagnostic test: initial scrape and first car.")

        # ---------------------------------------------------------------------
        # --- Create scraper instance ---
        # ---------------------------------------------------------------------
        async with AutoRiaScraper() as scraper:
            logger.info("AutoRiaScraper instance created for test run")

            # -----------------------------------------------------------------
            # --- Process start page ---
            # -----------------------------------------------------------------
            start_time = time.time()
            logger.info("Beginning start page processing.")

            # -----------------------------------------------------------------
            # --- Fetch start page ---
            # -----------------------------------------------------------------
            soup = await scraper.fetch_page(scraper.start_url)
            if not soup:
                logger.error("Could not fetch start page for testing.")
                return

            # -----------------------------------------------------------------
            # --- Get pagination URLs ---
            # -----------------------------------------------------------------
            pagination_urls = scraper.get_pagination_urls(soup)
            logger.info(
                f"Pagination discovered: {len(pagination_urls)} subsequent "
                f"pages identified."
            )

            # -----------------------------------------------------------------
            # --- Get car links ---
            # -----------------------------------------------------------------
            car_links = scraper.get_car_links(soup)
            logger.info(f"Found {len(car_links)} car links on the start page.")

            if not car_links:
                logger.warning("No car links found on the start page to test.")
                return

            first_car_url = car_links[0]
            logger.info(
                f"Targeting first car URL for detail parsing: {first_car_url}")

            # -----------------------------------------------------------------
            # --- Parse details of the first car ---
            # -----------------------------------------------------------------
            car_data = await scraper.parse_car_details(first_car_url)

            end_time = time.time()
            execution_time = end_time - start_time

            if car_data:
                logger.info(
                    f"Successfully parsed details for: "
                    f"{car_data.get('title', 'Unknown Title')}"
                )
                logger.info("--- DETAILED PARSED DATA DUMP (First Car) ---")

                # -------------------------------------------------------------
                # --- Log all collected fields for diagnostics ---
                # -------------------------------------------------------------
                for key, value in car_data.items():
                    if key != 'datetime_found':
                        logger.info(f"{key:<15}: {value}")

                logger.info("--- END OF DUMP ---")
                logger.info(
                    f"Diagnostic test completed in {execution_time:.2f} seconds."
                )
            else:
                logger.error(
                    f"Failed to parse details for first car URL: {first_car_url}")

    except Exception as error:
        logger.error(
            f"Error during diagnostic test run: {error}", exc_info=True
        )


async def run_scraper(full_update: bool = False) -> None:
    """Run scraper job"""
    try:
        logger.info("Starting scraper job...")
        # ---------------------------------------------------------------------
        # --- Create scraper instance ---
        # ---------------------------------------------------------------------
        async with AutoRiaScraper(full_update=full_update) as scraper:
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
                f"saved/updated {cars_saved} cars"
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
        '--full-update', action='store_true',
        help='Update all cars, even existing ones'
    )
    parser.add_argument(
        '--schedule', type=str, help='Set custom schedule time (HH:MM)'
    )
    parser.add_argument(
        '--backup', action='store_true', help='Create backup of current data'
    )
    parser.add_argument(
        '--test-run', action='store_true',
        help='Test scrape start page, check pagination, parse first car'
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
            f"Command line arguments: run_now={args.run_now}, "
            f"schedule={args.schedule}, backup={args.backup}, "
            f"test_run={args.test_run}, full_update={args.full_update}"
        )

        # ---------------------------------------------------------------------
        # --- Setup database ---
        # ---------------------------------------------------------------------
        logger.info("Setting up database...")
        await DatabaseManager.create_tables_async()
        logger.info("Database tables created/verified")

        # ---------------------------------------------------------------------
        # --- Handle Test Run ---
        # ---------------------------------------------------------------------
        if args.test_run:
            await test_initial_scrape_and_first_car()
            logger.info("Diagnostic test finished, exiting.")
            return

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
            await run_scraper(full_update=args.full_update)

        # ---------------------------------------------------------------------
        # --- Keep the main event loop alive ---
        # ---------------------------------------------------------------------
        logger.info("Entering main loop, press Ctrl+C to exit")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            scheduler.shutdown()

    except Exception as error:
        logger.error(f"Application error: {error}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_async())
