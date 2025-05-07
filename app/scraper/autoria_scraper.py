#!/usr/bin/env python
# coding: utf-8
import re
import time
import math
from datetime import datetime

# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Any, Dict, List, Optional, Set, Tuple

# -----------------------------------------------------------------------------
# --- Parsers ---
# -----------------------------------------------------------------------------
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from tenacity import retry, stop_after_attempt, wait_fixed

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import (
    HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT, START_URL, logger
)
from app.database import DatabaseManager
from app.models import Car
from app.scraper.utils import (
    clean_text, extract_number, get_random_delay,
)


class AutoRiaScraper:
    def __init__(self) -> None:
        self.start_url = START_URL
        self.headers = HEADERS.copy()
        self.timeout = REQUEST_TIMEOUT
        self.delay = REQUEST_DELAY
        self.processed_urls: Set[str] = set()
        self.session = requests.Session()
        self.context = None

        # --- Init Playwright ---
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.rotate_user_agent()

        logger.info("AutoRiaScraper with Playwright initialized")

    def __del__(self):
        self._close_playwright_resources()

    def _close_playwright_resources(self):
        try:
            if hasattr(self, 'context') and self.context:
                self.context.close()
            if hasattr(self, 'browser') and self.browser:
                self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                self.playwright.stop()
        except Exception as error:
            logger.error(f"Error closing Playwright resources: {error}")

    def rotate_user_agent(self) -> None:
        try:
            ua = UserAgent()
            self.headers["User-Agent"] = ua.random
            if hasattr(self, 'context') and self.context:
                self.context.close()

            self.context = self.browser.new_context(
                user_agent=self.headers["User-Agent"],
                viewport={"width": 1920, "height": 1080}
            )

            logger.debug(f"Rotated User-Agent: {self.headers['User-Agent']}.")
        except Exception as error:
            logger.warning(f"Failed to rotate User-Agent: {error}.")

    def fetch_page_with_playwright(self, url: str) -> Optional[Tuple[
        Optional[Page], Optional[BeautifulSoup]]
    ]:
        """Fetch a page using Playwright and return page and soup objects"""
        page = None
        try:
            # -----------------------------------------------------------------
            # --- Create a new page ---
            # -----------------------------------------------------------------
            page = self.context.new_page()

            # -----------------------------------------------------------------
            # --- Navigate to URL ---
            # -----------------------------------------------------------------
            page.goto(
                url, timeout=self.timeout * 1000, wait_until="networkidle"
            )

            # -----------------------------------------------------------------
            # --- Get page content ---
            # -----------------------------------------------------------------
            content = page.content()

            # -----------------------------------------------------------------
            # --- Parse with BeautifulSoup ---
            # -----------------------------------------------------------------
            soup = BeautifulSoup(content, 'lxml')

            return page, soup
        except Exception as error:
            logger.error(f"Error fetching {url}: {error}")
            if page:
                page.close()
            return None, None
        finally:
            time.sleep(get_random_delay(self.delay))

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch page and return BeautifulSoup object"""
        page, soup = self.fetch_page_with_playwright(url)
        if page:
            page.close()
        return soup

    @staticmethod
    def get_pagination(soup: BeautifulSoup) -> Tuple[int, int, int]:
        """ Calculate pagination params """
        try:
            # -----------------------------------------------------------------
            # --- Find total count ---
            # -----------------------------------------------------------------
            total_count_elem = soup.find('span', id='staticResultsCount')
            total_count = 0

            if total_count_elem:
                total_count_text = total_count_elem.text.strip()
                # -------------------------------------------------------------
                # --- Extract numbers ---
                # -------------------------------------------------------------
                total_count = int(re.sub(r'\s+', '', total_count_text))
                logger.info(f"Total listings count: {total_count}")
            else:
                logger.warning("Could not find total count element")

            # -----------------------------------------------------------------
            # -- Find items per page ---
            # -----------------------------------------------------------------
            items_per_page = 20  # Default value
            pagination_size_elem = soup.find('a', id='paginationChangeSize')

            if pagination_size_elem:
                items_text = pagination_size_elem.text.strip()
                # -------------------------------------------------------------
                # --- Extract numbers ---
                # -------------------------------------------------------------
                match = re.search(r'(\d+)\s+оголошень', items_text)
                if match:
                    items_per_page = int(match.group(1))
                    logger.info(f"Items per page: {items_per_page}")
            else:
                logger.warning(
                    "Could not find items per page element"
                )

            # -----------------------------------------------------------------
            # --- Calculate total pages ---
            # -----------------------------------------------------------------
            total_pages = math.ceil(
                total_count / items_per_page) if total_count > 0 else 0
            logger.info(f"Total pages to process: {total_pages}")

            return total_count, items_per_page, total_pages

        except Exception as error:
            logger.error(f"Error calculating pagination: {error}")
            return 0, 20, 0  # Default values

    def get_pagination_urls(self, soup: BeautifulSoup) -> List[str]:
        """ Generate pagination URLs """
        pagination_urls = []
        try:
            # -----------------------------------------------------------------
            # --- Calculate pagination params ---
            # -----------------------------------------------------------------
            total_count, items_per_page, total_pages = self.get_pagination(
                soup
            )

            if total_pages <= 0:
                logger.warning("No pages to process")
                return pagination_urls

            # -----------------------------------------------------------------
            # --- Generate pagination URLs ---
            # -----------------------------------------------------------------
            base_url = self.start_url

            # -----------------------------------------------------------------
            # --- Remove existing page parameter ---
            # -----------------------------------------------------------------
            if "?" in base_url:
                base_parts = base_url.split("?")
                base_url = base_parts[0]
                params = base_parts[1].split("&")
                filtered_params = [
                    p for p in params if not p.startswith("page=")
                ]
                if filtered_params:
                    base_url = f"{base_url}?{'&'.join(filtered_params)}"

            # -----------------------------------------------------------------
            # --- Add page parameter connector ---
            # -----------------------------------------------------------------
            connector = "&" if "?" in base_url else "?"

            # -----------------------------------------------------------------
            # --- Generate URLs for pages ---
            # -----------------------------------------------------------------
            for page_num in range(2, total_pages + 1):
                page_url = f"{base_url}{connector}page={page_num}"
                pagination_urls.append(page_url)

        except Exception as error:
            logger.error(f"Error generating pagination URLs: {error}")

        logger.info(f"Generated {len(pagination_urls)} pagination URLs")
        return pagination_urls

    def get_car_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract car links from soup"""
        car_links = []
        try:
            # -----------------------------------------------------------------
            # --- Find all cards ---
            # -----------------------------------------------------------------
            car_cards = soup.find_all('a', class_='m-link-ticket')

            for card in car_cards:
                # -------------------------------------------------------------
                # --- Get card URL ---
                # -------------------------------------------------------------
                href = card.get('href')
                if href and href not in self.processed_urls:
                    # ---------------------------------------------------------
                    # --- Make absolute URL ---
                    # ---------------------------------------------------------
                    if href.startswith('/'):
                        href = f"https://auto.ria.com{href}"

                    # ---------------------------------------------------------
                    # --- Append to processed ---
                    # ---------------------------------------------------------
                    car_links.append(href)
        except Exception as error:
            logger.error(f"Error extracting car links: {error}")

        logger.debug(f"Found {len(car_links)} car links on page")
        return car_links

    @staticmethod
    def extract_phone_number(page: Page) -> Optional[str]:
        """Extract phone number from car page"""
        try:
            logger.debug("Clicking on show phone button")
            # -----------------------------------------------------------------
            # --- Get show phone link ---
            # -----------------------------------------------------------------
            show_phone_link = page.query_selector(
                'a.phone_show_link'
            )
            if show_phone_link:
                try:
                    # ---------------------------------------------------------
                    # --- Click show link ---
                    # ---------------------------------------------------------
                    show_phone_link.click(timeout=1000)

                    # ---------------------------------------------------------
                    # --- Wait for popup ---
                    # ---------------------------------------------------------
                    page.wait_for_timeout(2000)
                except Exception as error:
                    logger.error(
                        f"Error clicking show phone link: {error}"
                    )

            # -----------------------------------------------------------------
            # --- Get content after click ---
            # -----------------------------------------------------------------
            content = page.content()
            soup = BeautifulSoup(content, 'lxml')

            # -----------------------------------------------------------------
            # --- Find number with regex ---
            # -----------------------------------------------------------------
            pattern = re.compile(r'\(\d{3}\)\s*\d{3}\s*\d{2}\s*\d{2}')
            for tag in soup.find_all(text=pattern):
                phone_match = pattern.search(tag)
                if phone_match:
                    phone_text = phone_match.group(0)
                    phone = re.sub(r'[^\d+]', '', phone_text)
                    if not phone.startswith('+'):
                        phone = '+38' + phone
                    return phone

            logger.warning("Could not found phone number")
            return None

        except Exception as error:
            logger.error(f"Error extracting phone: {str(error)}")
            return None

    def parse_car_details(self, url: str) -> Optional[Dict[str, Any]]:
        """Parse car details from page"""
        page, soup = self.fetch_page_with_playwright(url)
        if not page or not soup:
            return None

        try:
            # -----------------------------------------------------------------
            # --- Extract title ---
            # -----------------------------------------------------------------
            title = clean_text(
                soup.find('h1', class_='head').text
                if soup.find('h1', class_='head') else ""
            )

            # -----------------------------------------------------------------
            # --- Extract price ---
            # -----------------------------------------------------------------
            price_usd = None
            price_elem = soup.find('div', class_='price_value')
            if price_elem:
                price_text = price_elem.find('strong')
                if price_text:
                    price_usd = extract_number(price_text.text)

            # -----------------------------------------------------------------
            # --- Extract odometer ---
            # -----------------------------------------------------------------
            odometer = None
            odometer_elem = soup.find('div', class_='base-information')

            if odometer_elem and 'тис. км' in odometer_elem.text:
                match = re.search(r'(\d+)\s*тис\. км', odometer_elem.text)
                if match:
                    odometer = int(match.group(1)) * 1000

            # -----------------------------------------------------------------
            # --- Extract username ---
            # -----------------------------------------------------------------
            username_elem = soup.find('div', class_='seller_info_name')
            username = clean_text(
                username_elem.text
            ) if username_elem else None

            # -----------------------------------------------------------------
            # --- Extract phone ---
            # -----------------------------------------------------------------
            phone_number = self.extract_phone_number(page)

            # -----------------------------------------------------------------
            # --- Extract images ---
            # -----------------------------------------------------------------
            image_url = None
            images_count = 0
            gallery = soup.find('div', class_='gallery-order')
            if gallery:
                images = gallery.find_all('img')
                images_count = len(images)
                if images_count > 0:
                    image_url = images[0].get('src')

            # -----------------------------------------------------------------
            # --- Extract car number ---
            # -----------------------------------------------------------------
            car_number = None
            number_elem = soup.find('span', class_='state-num')
            if number_elem:
                car_number = clean_text(number_elem.contents[0])

            # -----------------------------------------------------------------
            # --- Extract VIN ---
            # -----------------------------------------------------------------
            car_vin = None
            vin_elem = soup.find('span', class_='label-vin')
            if vin_elem:
                car_vin = clean_text(vin_elem.text)

            # -----------------------------------------------------------------
            # --- Create car details dict ---
            # -----------------------------------------------------------------
            car_details = {
                'url': url,
                'title': title,
                'price_usd': price_usd,
                'odometer': odometer,
                'username': username,
                'phone_number': phone_number,
                'image_url': image_url,
                'images_count': images_count,
                'car_number': car_number,
                'car_vin': car_vin,
                'datetime_found': datetime.now()
            }

            logger.debug(f"Parsed car details for {url}: {title}")

            return car_details

        except Exception as error:
            logger.error(f"Error parsing car details from {url}: {error}")
            return None
        finally:
            if page:
                page.close()

    @staticmethod
    def save_car_to_db(car_data: Dict[str, Any]) -> bool:
        """ Save car data to db """
        try:
            # -----------------------------------------------------------------
            # --- Check if car already exists ---
            # -----------------------------------------------------------------
            exists = DatabaseManager.exists_by_field(
                Car, 'url', car_data['url']
            )
            if exists:
                logger.debug(
                    f"Car {car_data['url']} already exists in database"
                )
                return False

            # -----------------------------------------------------------------
            # --- Create car object ---
            # -----------------------------------------------------------------
            car = Car(**car_data)

            # -----------------------------------------------------------------
            # --- Save to database ---
            # -----------------------------------------------------------------
            result = DatabaseManager.add_item(car)

            if result:
                logger.info(f"Car saved to database: {car_data['title']}")
                return True
            else:
                logger.warning(
                    f"Failed to save car to database: {car_data['title']}")
                return False

        except Exception as error:
            logger.error(f"Error saving car to database: {error}")
            return False

    def process_car_page(self, url: str) -> bool:
        """Process a single car page"""
        # ---------------------------------------------------------------------
        # --- Skip if already processed ---
        # ---------------------------------------------------------------------
        if url in self.processed_urls:
            return False

        # ---------------------------------------------------------------------
        # --- Mark as processed ---
        # ---------------------------------------------------------------------
        self.processed_urls.add(url)

        # ---------------------------------------------------------------------
        # --- Parse car details ---
        # ---------------------------------------------------------------------
        car_data = self.parse_car_details(url)
        if not car_data:
            return False

        # ---------------------------------------------------------------------
        # --- Save to database ---
        # ---------------------------------------------------------------------
        return self.save_car_to_db(car_data)

    def run(self) -> Tuple[int, int]:
        """Run the scraper"""
        logger.info("Starting AutoRIA scrapper")

        pages_processed = 0
        cars_saved = 0

        try:
            # -----------------------------------------------------------------
            # --- Start with the initial URL ---
            # -----------------------------------------------------------------
            current_url = self.start_url

            # -----------------------------------------------------------------
            # --- Fetch start page ---
            # -----------------------------------------------------------------
            soup = self.fetch_page(current_url)
            if not soup:
                logger.error("Could not fetch the start page")
                return pages_processed, cars_saved

            pages_processed += 1

            # -----------------------------------------------------------------
            # --- Get pagination URLs ---
            # -----------------------------------------------------------------
            pagination_urls = self.get_pagination_urls(soup)

            # -----------------------------------------------------------------
            # --- Process start page ---
            # -----------------------------------------------------------------
            car_links = self.get_car_links(soup)
            for car_link in car_links:
                if self.process_car_page(car_link):
                    cars_saved += 1

                # -------------------------------------------------------------
                # --- Rotate user agent ---
                # -------------------------------------------------------------
                if cars_saved % 10 == 0:
                    self.rotate_user_agent()

            logger.info(
                f"Processed start page, "
                f"found {len(car_links)} cars, saved {cars_saved}."
            )

            # -----------------------------------------------------------------
            # --- Process remaining pages ---
            # -----------------------------------------------------------------
            for page_url in pagination_urls:
                logger.info(
                    f"Processing page {pages_processed + 1}: {page_url}")

                # -------------------------------------------------------------
                # --- Fetch page ---
                # -------------------------------------------------------------
                soup = self.fetch_page(page_url)
                if not soup:
                    logger.warning(f"Could not fetch page: {page_url}")
                    continue

                pages_processed += 1

                # --------------------------------------------------------------
                # --- Get car links ---
                # -------------------------------------------------------------
                car_links = self.get_car_links(soup)

                for car_link in car_links:
                    # ---------------------------------------------------------
                    # --- Process car page ---
                    # ---------------------------------------------------------
                    if self.process_car_page(car_link):
                        cars_saved += 1

                    # ---------------------------------------------------------
                    # --- Rotate user agent ---
                    # ---------------------------------------------------------
                    if cars_saved % 10 == 0:
                        self.rotate_user_agent()

                logger.info(
                    f"Processed {pages_processed} pages, "
                    f"saved {cars_saved} cars."
                )

            logger.info(
                f"AutoRIA scraper finished. "
                f"Total: {pages_processed} pages processed, "
                f"{cars_saved} cars saved."
            )

        except Exception as error:
            logger.error(f"Error in scraper run: {error}")
        finally:
            # -----------------------------------------------------------------
            # --- Close Playwright resources ---
            # -----------------------------------------------------------------
            self._close_playwright_resources()

        return pages_processed, cars_saved
