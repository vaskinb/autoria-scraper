#!/usr/bin/env python
# coding: utf-8
import re
import math
import asyncio
from datetime import datetime

# -----------------------------------------------------------------------------
# --- Typing ---
# -----------------------------------------------------------------------------
from typing import Any, Dict, List, Optional, Set, Tuple

# -----------------------------------------------------------------------------
# --- Parsers ---
# -----------------------------------------------------------------------------
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import (
    Browser, BrowserContext, Page, async_playwright
)
from tenacity import retry, stop_after_attempt, wait_fixed

# -----------------------------------------------------------------------------
# --- App ---
# -----------------------------------------------------------------------------
from app.config import (
    HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT, START_URL, logger,
    CAR_SEMAPHORE_VALUE, PAGE_SEMAPHORE_VALUE
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
        self.session = None
        self.context = None
        self.browser = None
        self.playwright = None
        self._pagination_urls = []

        logger.info("AutoRiaScraper with async Playwright initialized")

    async def initialize(self):
        """Initialize aiohttp session and Playwright browser"""
        # --- Init aiohttp session ---
        self.session = aiohttp.ClientSession(headers=self.headers)

        # --- Init Playwright ---
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        await self.rotate_user_agent()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_resources()

    async def _close_resources(self):
        """Close all async resources"""
        try:
            if self.session:
                await self.session.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.debug("All async resources closed")
        except Exception as error:
            logger.error(f"Error closing async resources: {error}")

    async def rotate_user_agent(self) -> None:
        """Rotate user agent to avoid detection"""
        try:
            ua = UserAgent()
            self.headers["User-Agent"] = ua.random
            if self.context:
                await self.context.close()

            self.context = await self.browser.new_context(
                user_agent=self.headers["User-Agent"],
                viewport={"width": 1920, "height": 1080}
            )

            logger.debug(f"Rotated User-Agent: {self.headers['User-Agent']}.")
        except Exception as error:
            logger.warning(f"Failed to rotate User-Agent: {error}.")

    async def fetch_page_with_playwright(self, url: str) -> Optional[Tuple[
        Optional[Page], Optional[BeautifulSoup]]
    ]:
        """Fetch a page using Playwright and return page and soup objects"""
        page = None
        try:
            # -----------------------------------------------------------------
            # --- Create a new page ---
            # -----------------------------------------------------------------
            page = await self.context.new_page()

            # -----------------------------------------------------------------
            # --- Navigate to URL ---
            # -----------------------------------------------------------------
            await page.goto(
                url, timeout=self.timeout * 1000, wait_until="networkidle"
            )

            # -----------------------------------------------------------------
            # --- Get page content ---
            # -----------------------------------------------------------------
            content = await page.content()

            # -----------------------------------------------------------------
            # --- Parse with BeautifulSoup ---
            # -----------------------------------------------------------------
            soup = BeautifulSoup(content, 'lxml')

            return page, soup
        except Exception as error:
            logger.error(f"Error fetching {url}: {error}")
            if page:
                await page.close()
            return None, None
        finally:
            await asyncio.sleep(get_random_delay(self.delay))

    async def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch page and return BeautifulSoup object"""
        page, soup = await self.fetch_page_with_playwright(url)
        if page:
            await page.close()
        return soup

    @staticmethod
    def get_pagination(soup: BeautifulSoup) -> int:
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

            return total_pages

        except Exception as error:
            logger.error(f"Error calculating pagination: {error}")
            return 0

    def get_pagination_urls(self, soup: BeautifulSoup) -> List[str]:
        """ Generate pagination URLs """
        pagination_urls = []
        try:
            # -----------------------------------------------------------------
            # --- Calculate pagination params ---
            # -----------------------------------------------------------------
            total_pages = self.get_pagination(soup)

            if total_pages <= 0:
                logger.warning("No pages to process")
                return pagination_urls

            # -----------------------------------------------------------------
            # --- Generate pagination URLs ---
            # -----------------------------------------------------------------
            base_url = self._prepare_base_url()

            # -----------------------------------------------------------------
            # --- Generate URLs for pages ---
            # -----------------------------------------------------------------
            for page_num in range(2, total_pages + 1):
                page_url = f"{base_url}page={page_num}"
                pagination_urls.append(page_url)

        except Exception as error:
            logger.error(f"Error generating pagination URLs: {error}")

        logger.info(f"Generated {len(pagination_urls)} pagination URLs")
        return pagination_urls

    def _prepare_base_url(self) -> str:
        """Prepare base URL for pagination"""
        base_url = self.start_url

        # ---------------------------------------------------------------------
        # --- Remove existing page parameter ---
        # ---------------------------------------------------------------------
        if "?" in base_url:
            base_parts = base_url.split("?")
            base_url = base_parts[0]
            params = base_parts[1].split("&")
            filtered_params = [
                p for p in params if not p.startswith("page=")
            ]
            if filtered_params:
                base_url = f"{base_url}?{'&'.join(filtered_params)}"

        # ---------------------------------------------------------------------
        # --- Add page parameter connector ---
        # ---------------------------------------------------------------------
        connector = "&" if "?" in base_url else "?"
        return f"{base_url}{connector}"

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

    async def extract_phone_number(self, page: Page) -> Optional[str]:
        """Extract phone number from car page (async version)"""
        try:
            logger.debug(
                "Extracting phone number - clicking on show phone button")
            # -----------------------------------------------------------------
            # --- Get show phone link ---
            # -----------------------------------------------------------------
            show_phone_link = page.locator('a.phone_show_link').first
            if show_phone_link:
                try:
                    # ---------------------------------------------------------
                    # --- Click show link ---
                    # ---------------------------------------------------------
                    await show_phone_link.click(timeout=1000)

                    # ---------------------------------------------------------
                    # --- Wait for popup ---
                    # ---------------------------------------------------------
                    await page.wait_for_timeout(2000)
                except Exception as error:
                    logger.error(f"Error clicking show phone link: {error}")

            # -----------------------------------------------------------------
            # --- Get content after click ---
            # -----------------------------------------------------------------
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')

            # -----------------------------------------------------------------
            # --- Find number with regex ---
            # -----------------------------------------------------------------
            pattern = re.compile(r'\(\d{3}\)\s*\d{3}\s*\d{2}\s*\d{2}')
            for tag in soup.find_all(text=pattern):
                phone_match = pattern.search(tag)
                if phone_match:
                    phone_text = phone_match.group(0)
                    phone_number = re.sub(r'[^\d+]', '', phone_text)
                    if not phone_number.startswith('+'):
                        phone_number = '+38' + phone_number
                    return phone_number

            logger.warning("Could not find phone number")
            return None

        except Exception as error:
            logger.error(f"Error extracting phone: {str(error)}")
            return None

    async def parse_car_details(self, url: str) -> Optional[Dict[str, Any]]:
        """Parse car details from page"""
        page, soup = await self.fetch_page_with_playwright(url)
        if not page or not soup:
            return None

        try:
            car_details = {
                'url': url,
                'datetime_found': datetime.now()
            }

            # -----------------------------------------------------------------
            # --- Extract basic car info ---
            # -----------------------------------------------------------------
            car_details.update(self._extract_basic_info(soup))

            # -----------------------------------------------------------------
            # --- Extract phone - must be on the same page (important!) ---
            # -----------------------------------------------------------------
            car_details['phone_number'] = await self.extract_phone_number(page)

            # -----------------------------------------------------------------
            # --- Extract additional car info ---
            # -----------------------------------------------------------------
            car_details.update(self._extract_additional_info(soup))

            logger.debug(
                f"Parsed car details for {url}: {car_details['title']}")

            return car_details

        except Exception as error:
            logger.error(f"Error parsing car details from {url}: {error}")
            return None
        finally:
            if page:
                await page.close()

    def _extract_basic_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract basic car information from the page"""
        basic_info = {}

        # -----------------------------------------------------------------
        # --- Extract title ---
        # -----------------------------------------------------------------
        title = clean_text(
            soup.find('h1', class_='head').text
            if soup.find('h1', class_='head') else ""
        )
        basic_info['title'] = title

        # -----------------------------------------------------------------
        # --- Extract price ---
        # -----------------------------------------------------------------
        price_usd = None
        price_elem = soup.find('div', class_='price_value')
        if price_elem:
            price_text = price_elem.find('strong')
            if price_text:
                price_usd = extract_number(price_text.text)
        basic_info['price_usd'] = price_usd

        # -----------------------------------------------------------------
        # --- Extract odometer ---
        # -----------------------------------------------------------------
        odometer = None
        odometer_elem = soup.find('div', class_='base-information')

        if odometer_elem and 'тис. км' in odometer_elem.text:
            match = re.search(r'(\d+)\s*тис\. км', odometer_elem.text)
            if match:
                odometer = int(match.group(1)) * 1000
        basic_info['odometer'] = odometer

        # -----------------------------------------------------------------
        # --- Extract username ---
        # -----------------------------------------------------------------
        username_elem = soup.find('div', class_='seller_info_name')
        username = clean_text(username_elem.text) if username_elem else None
        basic_info['username'] = username

        return basic_info

    @staticmethod
    def _extract_additional_info(soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional car information from the page"""
        additional_info = {}

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
        additional_info['image_url'] = image_url
        additional_info['images_count'] = images_count

        # -----------------------------------------------------------------
        # --- Extract car number ---
        # -----------------------------------------------------------------
        car_number = None
        number_elem = soup.find('span', class_='state-num')
        if number_elem:
            car_number = clean_text(number_elem.contents[0])
        additional_info['car_number'] = car_number

        # -----------------------------------------------------------------
        # --- Extract VIN ---
        # -----------------------------------------------------------------
        car_vin = None
        vin_elem = soup.find('span', class_='label-vin')
        if vin_elem:
            car_vin = clean_text(vin_elem.text)
        additional_info['car_vin'] = car_vin

        return additional_info

    @staticmethod
    async def save_car_to_db(car_data: Dict[str, Any]) -> bool:
        """ Save car data to db """
        try:
            # -----------------------------------------------------------------
            # --- Check if car already exists ---
            # -----------------------------------------------------------------
            exists = await DatabaseManager.exists_by_field_async(
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
            result = await DatabaseManager.add_item_async(car)

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

    async def process_car_page(self, url: str) -> bool:
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
        car_data = await self.parse_car_details(url)
        if not car_data:
            return False

        # ---------------------------------------------------------------------
        # --- Save to database ---
        # ---------------------------------------------------------------------
        return await self.save_car_to_db(car_data)

    async def process_car_with_semaphore(
            self, url: str, semaphore: asyncio.Semaphore
    ) -> bool:
        """Process a car URL with semaphore control"""
        async with semaphore:
            return await self.process_car_page(url)

    async def process_pagination_page(
            self, page_url: str, car_semaphore: asyncio.Semaphore
    ) -> int:
        """Process a pagination page and its car listings"""
        logger.info(f"Processing page: {page_url}")

        # -----------------------------------------------------------------
        # --- Fetch page ---
        # -----------------------------------------------------------------
        soup = await self.fetch_page(page_url)
        if not soup:
            logger.warning(f"Could not fetch page: {page_url}")
            return 0

        # -----------------------------------------------------------------
        # --- Get car links ---
        # -----------------------------------------------------------------
        car_links = self.get_car_links(soup)

        # -----------------------------------------------------------------
        # --- Process car links concurrently ---
        # -----------------------------------------------------------------
        tasks = [
            self.process_car_with_semaphore(link, car_semaphore)
            for link in car_links
        ]
        car_results = await asyncio.gather(*tasks)

        page_cars_saved = sum(1 for result in car_results if result)

        # -----------------------------------------------------------------
        # --- Rotate user agent if we saved cars ---
        # -----------------------------------------------------------------
        if page_cars_saved > 0:
            await self.rotate_user_agent()

        logger.info(f"Page {page_url} processed, saved {page_cars_saved} cars")
        return page_cars_saved

    async def process_pagination_page_with_semaphore(
            self, url: str, car_semaphore: asyncio.Semaphore,
            page_semaphore: asyncio.Semaphore
    ) -> int:
        """Process a pagination page with semaphore control"""
        async with page_semaphore:
            return await self.process_pagination_page(url, car_semaphore)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    async def run(self) -> Optional[Tuple[int, int]]:
        """Run the scraper"""
        logger.info("Starting AutoRIA scrapper")

        pages_processed = 0
        cars_saved = 0

        try:
            # -----------------------------------------------------------------
            # --- Initialize resources if not already done ---
            # -----------------------------------------------------------------
            if not self.session or not self.browser:
                await self.initialize()

            # -----------------------------------------------------------------
            # --- Process start page ---
            # -----------------------------------------------------------------
            start_page_cars = await self._process_start_page()
            cars_saved += start_page_cars
            pages_processed += 1

            # -----------------------------------------------------------------
            # --- Process remaining pages concurrently ---
            # -----------------------------------------------------------------
            car_semaphore = asyncio.Semaphore(CAR_SEMAPHORE_VALUE)
            page_semaphore = asyncio.Semaphore(PAGE_SEMAPHORE_VALUE)

            # -----------------------------------------------------------------
            # --- Process pages with semaphore control ---
            # -----------------------------------------------------------------
            tasks = [
                self.process_pagination_page_with_semaphore(
                    url, car_semaphore, page_semaphore)
                for url in self._pagination_urls
            ]

            results = await asyncio.gather(*tasks)

            # -----------------------------------------------------------------
            # --- Calc processed pages ---
            # -----------------------------------------------------------------
            pages_processed += len(self._pagination_urls)
            cars_saved += sum(results)

            logger.info(
                f"AutoRIA scraper finished. "
                f"Total: {pages_processed} pages processed, "
                f"{cars_saved} cars saved."
            )

        except Exception as error:
            logger.error(f"Error in scraper run: {error}")
        finally:
            # -----------------------------------------------------------------
            # --- Close async resources ---
            # -----------------------------------------------------------------
            await self._close_resources()

        return pages_processed, cars_saved

    async def _process_start_page(self) -> int:
        """Process the initial page"""
        # ---------------------------------------------------------------------
        # --- Fetch start page ---
        # ---------------------------------------------------------------------
        soup = await self.fetch_page(self.start_url)
        if not soup:
            logger.info("Could not fetch the start page")
            return 0

        # ---------------------------------------------------------------------
        # --- Get pagination URLs for later ---
        # ---------------------------------------------------------------------
        self._pagination_urls = self.get_pagination_urls(soup)

        # ---------------------------------------------------------------------
        # --- Process car links from start page ---
        # ---------------------------------------------------------------------
        car_links = self.get_car_links(soup)

        # ---------------------------------------------------------------------
        # --- Process cars with concurrency ---
        # ---------------------------------------------------------------------
        car_semaphore = asyncio.Semaphore(CAR_SEMAPHORE_VALUE)

        tasks = [
            self.process_car_with_semaphore(link, car_semaphore)
            for link in car_links
        ]
        results = await asyncio.gather(*tasks)

        # ---------------------------------------------------------------------
        # --- Calc processed cars ---
        # ---------------------------------------------------------------------
        cars_saved = sum(1 for result in results if result)
        logger.info(
            f"Processed start page, found {len(car_links)} cars, "
            f"saved {cars_saved}."
        )

        return cars_saved
