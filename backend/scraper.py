# scraper.py — BeiSmart KE
# Handles all web scraping from Jumia, Avechi, Hotpoint and Quickmart

import re
import time
import random
import logging
import concurrent.futures
import requests
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.sync_api import sync_playwright

from config import (
    MIN_DELAY_SECONDS, MAX_DELAY_SECONDS,
    REQUEST_TIMEOUT, MAX_RETRIES,
    MAX_RESULTS_PER_SITE,
    JUMIA_BASE_URL, JUMIA_SELECTORS,
    AVECHI_BASE_URL, AVECHI_SELECTORS,
    HOTPOINT_BASE_URL, HOTPOINT_SELECTORS,
    KILIMALL_API_URL,
    CARREFOUR_BASE_URL, CARREFOUR_API_URL,
    AMAZON_BASE_URL, AMAZON_SELECTORS, USD_TO_KSH,
)

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("beismart.scraper")


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════════════════════════════

class ScraperError(Exception):
    """Base exception for all scraper errors."""
    pass

class FetchError(ScraperError):
    """Raised when an HTTP request fails or returns a bad status code."""
    pass

class ParseError(ScraperError):
    """Raised when product data cannot be parsed from the HTML response."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT DATA CLASS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Product:
    """Represents a single scraped product listing."""
    site: str
    name: str
    price: float
    currency: str
    url: str
    image_url: Optional[str] = field(default=None)

    def __repr__(self):
        return (f"Product(site={self.site!r}, name={self.name[:40]!r}, "
                f"price={self.currency} {self.price:,.0f}, url={self.url[:50]!r})")


# ══════════════════════════════════════════════════════════════════════════════
# HELPER — PRICE PARSER
# ══════════════════════════════════════════════════════════════════════════════

def parse_price(raw: str) -> tuple[float, str]:
    """
    Converts a raw price string like 'KSh 28,999' or 'KES 55.00'
    into a (float, currency_string) tuple.
    For ranges like 'KSh 507 - KSh 508', takes the lower price.
    Returns (0.0, 'KSh') if parsing fails.
    """
    if not raw:
        return 0.0, "KSh"

    raw = raw.strip()

    currency = "KSh"
    for token in ["KSh", "KES", "Ksh"]:
        if token in raw:
            currency = "KSh"
            break

    # If it's a range (e.g. "KSh 507 - KSh 508"), take the first price only
    if " - " in raw:
        raw = raw.split(" - ")[0]

    digits = ""
    for ch in raw:
        if ch.isdigit() or ch == ".":
            digits += ch
        elif ch == ",":
            continue

    try:
        return float(digits), currency
    except ValueError:
        logger.warning(f"Could not parse price from: {raw!r}")
        return 0.0, "KSh"


_ACCESSORY_TERMS = {
    "case", "cover", "screen protector", "tempered glass", "charger",
    "cable", "adapter", "holder", "stand", "skin", "pouch", "sleeve",
    "strap", "band", "stylus", "headset", "earphone", "earpiece",
    "protector", "film", "bumper", "shell", "wallet", "flip cover",
}

def is_relevant(product_name: str, query: str, threshold: float = 0.6) -> bool:
    """
    Returns True if the product name is relevant to the search query.
    Raises threshold to 0.6 and filters out common accessory terms
    unless the query itself is for an accessory.
    """
    query_lower = query.lower()
    name_lower  = product_name.lower()

    # If the query isn't about an accessory, exclude accessory-only results
    query_is_accessory = any(t in query_lower for t in _ACCESSORY_TERMS)
    if not query_is_accessory:
        if any(t in name_lower for t in _ACCESSORY_TERMS):
            return False

    query_words = [w.lower() for w in query.split() if len(w) > 2]
    if not query_words:
        return True

    matches = sum(1 for word in query_words if word in name_lower)
    return (matches / len(query_words)) >= threshold


# ══════════════════════════════════════════════════════════════════════════════
# BASE SCRAPER (requests-based)
# ══════════════════════════════════════════════════════════════════════════════

class BaseScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.logger = logging.getLogger(f"beismart.{self.__class__.__name__}")

    def _get_headers(self) -> dict:
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
        }

    def _random_delay(self):
        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        self.logger.debug(f"Waiting {delay:.1f}s before next request...")
        time.sleep(delay)

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(FetchError),
        reraise=True,
    )
    def _fetch(self, url: str) -> BeautifulSoup:
        self._random_delay()
        try:
            self.logger.info(f"Fetching: {url}")
            response = self.session.get(url, headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return BeautifulSoup(response.text, "lxml")
            elif response.status_code == 403:
                raise FetchError(f"Access denied (403) for {url}")
            elif response.status_code == 404:
                raise FetchError(f"Page not found (404) for {url}")
            else:
                raise FetchError(f"HTTP {response.status_code} for {url}")
        except requests.exceptions.Timeout:
            raise FetchError(f"Request timed out for {url}")
        except requests.exceptions.ConnectionError:
            raise FetchError(f"Connection error for {url}")
        except requests.exceptions.RequestException as e:
            raise FetchError(f"Request failed for {url}: {e}")

    def scrape(self, query: str) -> list[Product]:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# BASE SCRAPER (Playwright-based, for JS-rendered sites)
# ══════════════════════════════════════════════════════════════════════════════

class PlaywrightBaseScraper:
    """Base scraper for JS-rendered sites using Playwright headless Chromium."""

    def __init__(self):
        self.logger = logging.getLogger(f"beismart.{self.__class__.__name__}")

    def _get_page_html(self, url: str, wait_for: str = None, timeout: int = 15000) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            try:
                page.goto(url, timeout=timeout)
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=timeout)
                else:
                    page.wait_for_load_state("networkidle", timeout=timeout)
                html = page.content()
            except Exception as e:
                self.logger.warning(f"Playwright page load issue: {e}")
                html = page.content()
            finally:
                browser.close()
        return html

    def scrape(self, query: str) -> list[Product]:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# JUMIA SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class JumiaScraper(BaseScraper):
    """Scrapes product listings from Jumia Kenya."""

    def scrape(self, query: str) -> list[Product]:
        url = f"{JUMIA_BASE_URL}/catalog/?q={requests.utils.quote(query)}"
        products = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            self.logger.info(f"Fetching: {url}")
            self._random_delay()
            response = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            soup = BeautifulSoup(response.text, "lxml")
            items = soup.select(JUMIA_SELECTORS["product_card"])

            if not items:
                self.logger.warning(f"Jumia: no products found for '{query}'")
                return []

            self.logger.info(f"Jumia: found {len(items)} raw items for '{query}'")

            for item in items[:MAX_RESULTS_PER_SITE]:
                try:
                    name_el = item.select_one(JUMIA_SELECTORS["name"])
                    name = name_el.get_text(strip=True) if name_el else "Unknown"

                    price_el = item.select_one(JUMIA_SELECTORS["price"])
                    raw_price = price_el.get_text(strip=True) if price_el else ""
                    price, currency = parse_price(raw_price)

                    if price == 0.0:
                        continue

                    if not is_relevant(name, query):
                        continue

                    link_el = item.select_one(JUMIA_SELECTORS["link"])
                    relative_url = link_el.get("href", "") if link_el else ""
                    product_url = (
                        f"{JUMIA_BASE_URL}{relative_url}"
                        if relative_url.startswith("/")
                        else relative_url
                    )

                    img_el = item.select_one(JUMIA_SELECTORS["image"])
                    image_url = (
                        img_el.get("data-src") or img_el.get("src")
                        if img_el else None
                    )

                    products.append(Product(
                        site="Jumia",
                        name=name,
                        price=price,
                        currency=currency,
                        url=product_url,
                        image_url=image_url,
                    ))

                except Exception as e:
                    self.logger.warning(f"Jumia: skipped one item — {e}")
                    continue

        except FetchError as e:
            self.logger.error(f"Jumia fetch failed: {e}")

        self.logger.info(f"Jumia: returned {len(products)} valid products for '{query}'")
        return products


# ══════════════════════════════════════════════════════════════════════════════
# AVECHI SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class AvechiScraper(BaseScraper):
    """Scrapes product listings from Avechi Kenya."""

    def scrape(self, query: str) -> list[Product]:
        url = f"{AVECHI_BASE_URL}/?s={requests.utils.quote(query)}&post_type=product"
        products = []

        try:
            soup = self._fetch(url)
            items = soup.select(AVECHI_SELECTORS["product_card"])

            if not items:
                self.logger.warning(f"Avechi: no products found for '{query}'")
                return []

            self.logger.info(f"Avechi: found {len(items)} raw items for '{query}'")

            for item in items[:MAX_RESULTS_PER_SITE]:
                try:
                    name_el = item.select_one(AVECHI_SELECTORS["name"])
                    name = name_el.get_text(strip=True) if name_el else "Unknown"

                    price_el = item.select_one(AVECHI_SELECTORS["price"])
                    if not price_el:
                        price_el = item.select_one(AVECHI_SELECTORS["price_fallback"])
                    raw_price = price_el.get_text(strip=True) if price_el else ""
                    price, currency = parse_price(raw_price)

                    if price == 0.0:
                        continue

                    if not is_relevant(name, query):
                        continue

                    link_el = item.select_one(AVECHI_SELECTORS["link"])
                    product_url = link_el.get("href", "") if link_el else ""

                    img_el = item.select_one(AVECHI_SELECTORS["image"])
                    image_url = (
                        img_el.get("data-src") or img_el.get("src")
                        if img_el else None
                    )

                    products.append(Product(
                        site="Avechi",
                        name=name,
                        price=price,
                        currency=currency,
                        url=product_url,
                        image_url=image_url,
                    ))

                except Exception as e:
                    self.logger.warning(f"Avechi: skipped one item — {e}")
                    continue

        except FetchError as e:
            self.logger.error(f"Avechi fetch failed: {e}")

        self.logger.info(f"Avechi: returned {len(products)} valid products for '{query}'")
        return products


# ══════════════════════════════════════════════════════════════════════════════
# HOTPOINT SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class HotpointScraper(BaseScraper):
    """Scrapes product listings from Hotpoint Kenya."""

    def scrape(self, query: str) -> list[Product]:
        url = f"{HOTPOINT_BASE_URL}/search/?q={requests.utils.quote(query)}"
        products = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            self.logger.info(f"Fetching: {url}")
            self._random_delay()
            response = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            soup = BeautifulSoup(response.text, "lxml")
            items = soup.select(HOTPOINT_SELECTORS["product_card"])

            if not items:
                self.logger.warning(f"Hotpoint: no products found for '{query}'")
                return []

            self.logger.info(f"Hotpoint: found {len(items)} raw items for '{query}'")

            for item in items[:MAX_RESULTS_PER_SITE]:
                try:
                    name_el = item.select_one(HOTPOINT_SELECTORS["name"])
                    name = name_el.get_text(strip=True) if name_el else "Unknown"

                    price_el = item.select_one(HOTPOINT_SELECTORS["price"])
                    raw_price = price_el.get_text(strip=True) if price_el else ""
                    price, currency = parse_price(raw_price)

                    if price == 0.0:
                        continue

                    if not is_relevant(name, query):
                        continue

                    link_el = item.select_one(HOTPOINT_SELECTORS["link"])
                    relative_url = link_el.get("href", "") if link_el else ""
                    product_url = (
                        f"{HOTPOINT_BASE_URL}{relative_url}"
                        if relative_url.startswith("/")
                        else relative_url
                    )

                    img_el = item.select_one(HOTPOINT_SELECTORS["image"])
                    image_url = None
                    if img_el:
                        image_url = img_el.get("src") or img_el.get("data-src")
                        if image_url and image_url.startswith("/"):
                            image_url = f"{HOTPOINT_BASE_URL}{image_url}"

                    products.append(Product(
                        site="Hotpoint",
                        name=name,
                        price=price,
                        currency=currency,
                        url=product_url,
                        image_url=image_url,
                    ))

                except Exception as e:
                    self.logger.warning(f"Hotpoint: skipped one item — {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Hotpoint fetch failed: {e}")

        self.logger.info(f"Hotpoint: returned {len(products)} valid products for '{query}'")
        return products


# ══════════════════════════════════════════════════════════════════════════════
# QUICKMART SCRAPER (Playwright)
# ══════════════════════════════════════════════════════════════════════════════

class QuickmartScraper(PlaywrightBaseScraper):
    """Scrapes product listings from Quickmart Kenya using Playwright."""

    BASE_URL = "https://www.quickmart.co.ke"
    COOKIES  = [
        {"name": "_ygGeoAddress", "value": "Nairobi%20County%2C%20Kenya", "domain": "www.quickmart.co.ke", "path": "/"},
        {"name": "_ygGeoLat",     "value": "-1.3106691",                  "domain": "www.quickmart.co.ke", "path": "/"},
        {"name": "_ygGeoLng",     "value": "36.8250274",                  "domain": "www.quickmart.co.ke", "path": "/"},
        {"name": "_ygGeoRadius",  "value": "15",                          "domain": "www.quickmart.co.ke", "path": "/"},
        {"name": "_ygShopId",     "value": "44",                          "domain": "www.quickmart.co.ke", "path": "/"},
    ]

    def scrape(self, query: str) -> list[Product]:
        products = []

        try:
            self.logger.info(f"Quickmart: searching for '{query}'")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                # Cookies must be added before any navigation
                context.add_cookies(self.COOKIES)
                page = context.new_page()
                # Quickmart uses a custom URL format (hyphens not =) generated by
                # client-side JS — we must type into the search box and press Enter
                page.goto(f"{self.BASE_URL}/products", timeout=30000)
                page.wait_for_timeout(2000)
                page.fill("input[name='keyword']", query)
                page.press("input[name='keyword']", "Enter")
                try:
                    page.wait_for_selector("div.products.productInfoJs", timeout=20000)
                except Exception:
                    self.logger.warning("Quickmart: timed out waiting for products selector")
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, "lxml")
            cards = soup.select("div.products.productInfoJs")

            if not cards:
                self.logger.warning(f"Quickmart: no products found for '{query}'")
                return []

            self.logger.info(f"Quickmart: found {len(cards)} raw items for '{query}'")

            for card in cards[:MAX_RESULTS_PER_SITE]:
                try:
                    name_el = card.select_one("a.products-title")
                    name = name_el.get_text(strip=True) if name_el else "Unknown"

                    price_el = card.select_one("span.products-price-new")
                    raw_price = price_el.get_text(strip=True) if price_el else ""
                    price, currency = parse_price(raw_price)

                    if price == 0.0:
                        continue

                    if not is_relevant(name, query):
                        continue

                    link_el = card.select_one("div.products-img a")
                    relative_url = link_el.get("href", "") if link_el else ""
                    product_url = (
                        f"{self.BASE_URL}{relative_url}"
                        if relative_url.startswith("/")
                        else relative_url
                    )

                    img_el = card.select_one("div.products-img img")
                    image_url = img_el.get("src") if img_el else None

                    products.append(Product(
                        site="Quickmart",
                        name=name,
                        price=price,
                        currency=currency,
                        url=product_url,
                        image_url=image_url,
                    ))

                except Exception as e:
                    self.logger.warning(f"Quickmart: skipped one item — {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Quickmart fetch failed: {e}")

        self.logger.info(f"Quickmart: returned {len(products)} valid products for '{query}'")
        return products


# ══════════════════════════════════════════════════════════════════════════════
# KILIMALL SCRAPER (Playwright — API requires auth token)
# ══════════════════════════════════════════════════════════════════════════════

class KilimallScraper(PlaywrightBaseScraper):
    """Scrapes Kilimall Kenya using Playwright (their API needs auth tokens)."""

    BASE_URL = "https://www.kilimall.co.ke"

    def scrape(self, query: str) -> list[Product]:
        url = f"{self.BASE_URL}/search?q={requests.utils.quote(query)}&page=1"
        products = []
        try:
            self.logger.info(f"Kilimall (Playwright): fetching '{query}'")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                )
                page = context.new_page()
                page.goto(url, timeout=30000)
                try:
                    page.wait_for_selector("div.product-item", timeout=15000)
                except Exception:
                    self.logger.warning("Kilimall: timed out waiting for product selector")
                page.wait_for_timeout(2500)
                html = page.content()
                browser.close()

            soup  = BeautifulSoup(html, "lxml")
            cards = soup.select("div.product-item")

            if not cards:
                self.logger.warning(f"Kilimall: no product cards found for '{query}'")
                return []

            self.logger.info(f"Kilimall: found {len(cards)} raw cards")

            for card in cards[:MAX_RESULTS_PER_SITE]:
                try:
                    name_el = card.select_one("p.product-title")
                    name = name_el.get_text(strip=True) if name_el else ""
                    if not name or not is_relevant(name, query):
                        continue

                    price_el = card.select_one("div.product-price")
                    if not price_el:
                        continue
                    price_txt = re.sub(r"[^\d.]", "", price_el.get_text(strip=True))
                    price = float(price_txt) if price_txt else 0.0
                    if price == 0.0:
                        continue

                    link_el = card.select_one("a")
                    href    = link_el.get("href", "") if link_el else ""
                    product_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                    img_el    = card.select_one("img")
                    image_url = (img_el.get("data-src") or img_el.get("src")) if img_el else None

                    products.append(Product(
                        site="Kilimall",
                        name=name,
                        price=price,
                        currency="KSh",
                        url=product_url,
                        image_url=image_url,
                    ))
                except Exception as e:
                    self.logger.warning(f"Kilimall: skipped card — {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Kilimall fetch failed: {e}")

        self.logger.info(f"Kilimall: returned {len(products)} valid products for '{query}'")
        return products


# ══════════════════════════════════════════════════════════════════════════════
# CARREFOUR KENYA SCRAPER (Playwright — API returns HTML not JSON)
# ══════════════════════════════════════════════════════════════════════════════

class CarrefourScraper(PlaywrightBaseScraper):
    """Scrapes Carrefour Kenya using Playwright (JS-rendered, API is fake)."""

    BASE_URL = "https://www.carrefour.ke"

    def scrape(self, query: str) -> list[Product]:
        url = f"{self.BASE_URL}/mafken/en/search?keyword={requests.utils.quote(query)}&lang=en&currency=KES"
        products = []
        try:
            self.logger.info(f"Carrefour (Playwright): fetching '{query}'")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-http2",
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                page = context.new_page()
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                try:
                    page.wait_for_selector("[class*='product'], [class*='Product']", timeout=15000)
                except Exception:
                    self.logger.warning("Carrefour: timed out waiting for product selector")
                page.wait_for_timeout(2500)
                html = page.content()
                browser.close()

            soup  = BeautifulSoup(html, "lxml")
            cards = (
                soup.select("div[class*='product-card']")
                or soup.select("div[class*='ProductCard']")
                or soup.select("div[class*='product-item']")
                or soup.select("[class*='css-'][class*='product']")
            )

            if not cards:
                self.logger.warning(f"Carrefour: no product cards found for '{query}'")
                return []

            self.logger.info(f"Carrefour: found {len(cards)} raw cards")

            for card in cards[:MAX_RESULTS_PER_SITE]:
                try:
                    name_el = (
                        card.select_one("[class*='name']")
                        or card.select_one("[class*='title']")
                        or card.select_one("h2")
                        or card.select_one("h3")
                    )
                    name = name_el.get_text(strip=True) if name_el else ""
                    if not name or not is_relevant(name, query):
                        continue

                    price_el = (
                        card.select_one("[class*='price']")
                        or card.select_one("[class*='Price']")
                    )
                    if not price_el:
                        continue
                    price_txt = re.sub(r"[^\d.]", "", price_el.get_text(strip=True))
                    price = float(price_txt) if price_txt else 0.0
                    if price == 0.0:
                        continue

                    link_el = card.select_one("a")
                    href    = link_el.get("href", "") if link_el else ""
                    product_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                    img_el    = card.select_one("img")
                    image_url = img_el.get("src") or img_el.get("data-src") if img_el else None

                    products.append(Product(
                        site="Carrefour",
                        name=name,
                        price=price,
                        currency="KSh",
                        url=product_url,
                        image_url=image_url,
                    ))
                except Exception as e:
                    self.logger.warning(f"Carrefour: skipped card — {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Carrefour fetch failed: {e}")

        self.logger.info(f"Carrefour: returned {len(products)} products for '{query}'")
        return products


# ══════════════════════════════════════════════════════════════════════════════
# AMAZON SCRAPER (Playwright — requests gets CAPTCHA'd)
# ══════════════════════════════════════════════════════════════════════════════

class AmazonScraper(PlaywrightBaseScraper):
    """
    Scrapes Amazon.com using Playwright to bypass basic bot detection.
    Prices are in USD and converted to KSh using the rate in config.py.
    """

    BASE_URL = "https://www.amazon.com"

    def scrape(self, query: str) -> list[Product]:
        url = f"{self.BASE_URL}/s?k={requests.utils.quote(query)}"
        products = []
        try:
            self.logger.info(f"Amazon (Playwright): fetching '{query}'")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                page = context.new_page()
                page.goto(url, timeout=30000)
                try:
                    page.wait_for_selector("div[data-component-type='s-search-result']", timeout=15000)
                except Exception:
                    self.logger.warning("Amazon: timed out waiting for results")
                page.wait_for_timeout(1500)

                if "captcha" in page.url.lower() or "captcha" in page.title().lower():
                    self.logger.warning("Amazon: CAPTCHA page detected — skipping")
                    browser.close()
                    return []

                html = page.content()
                browser.close()

            soup  = BeautifulSoup(html, "lxml")
            cards = soup.select("div[data-component-type='s-search-result']")

            if not cards:
                self.logger.warning(f"Amazon: no product cards found for '{query}'")
                return []

            self.logger.info(f"Amazon: found {len(cards)} raw cards")

            for card in cards[:MAX_RESULTS_PER_SITE]:
                try:
                    name_el = card.select_one("h2 span")
                    name    = name_el.get_text(strip=True) if name_el else ""
                    if not name or not is_relevant(name, query):
                        continue

                    whole_el  = card.select_one("span.a-price-whole")
                    frac_el   = card.select_one("span.a-price-fraction")
                    symbol_el = card.select_one("span.a-price-symbol")
                    if not whole_el:
                        continue

                    symbol    = symbol_el.get_text(strip=True) if symbol_el else ""
                    whole_txt = re.sub(r"[^\d]", "", whole_el.get_text(strip=True))
                    frac_txt  = re.sub(r"[^\d]", "", frac_el.get_text(strip=True)) if frac_el else "00"
                    raw_price = float(f"{whole_txt}.{frac_txt or '00'}")

                    if "KES" in symbol or "KSh" in symbol:
                        final_price = round(raw_price, 2)
                        currency    = "KSh"
                    else:
                        final_price = round(raw_price * USD_TO_KSH, 2)
                        currency    = "KSh*"

                    if final_price == 0.0:
                        continue

                    asin = card.get("data-asin", "")
                    product_url = f"{self.BASE_URL}/dp/{asin}" if asin else ""
                    if not product_url:
                        continue

                    img_el    = card.select_one("img.s-image")
                    image_url = img_el.get("src") if img_el else None

                    products.append(Product(
                        site="Amazon",
                        name=name,
                        price=final_price,
                        currency=currency,
                        url=product_url,
                        image_url=image_url,
                    ))
                except Exception as e:
                    self.logger.warning(f"Amazon: skipped card — {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Amazon fetch failed: {e}")

        self.logger.info(f"Amazon: returned {len(products)} valid products for '{query}'")
        return products


# ══════════════════════════════════════════════════════════════════════════════
# PRICE COMPARISON SCRAPER — FACADE
# ══════════════════════════════════════════════════════════════════════════════

class PriceComparisonScraper:
    """Main entry point. Calls all scrapers, combines and sorts results by price."""

    # Maps category slug → scraper names to include
    CATEGORY_SCRAPERS = {
        "all":         ["Jumia", "Avechi", "Hotpoint", "Quickmart", "Kilimall", "Amazon"],
        "electronics": ["Jumia", "Avechi", "Hotpoint", "Kilimall", "Amazon"],
        "food":        ["Quickmart"],
        "appliances":  ["Jumia", "Hotpoint", "Avechi", "Kilimall"],
        "fashion":     ["Jumia", "Kilimall"],
        "general":     ["Jumia", "Avechi", "Kilimall"],
    }

    def __init__(self):
        self.jumia     = JumiaScraper()
        self.avechi    = AvechiScraper()
        self.hotpoint  = HotpointScraper()
        self.quickmart = QuickmartScraper()
        self.kilimall  = KilimallScraper()
        self.carrefour = CarrefourScraper()
        self.amazon    = AmazonScraper()
        self.logger    = logging.getLogger("beismart.PriceComparisonScraper")

        self._all_scrapers = {
            "Jumia":     self.jumia,
            "Avechi":    self.avechi,
            "Hotpoint":  self.hotpoint,
            "Quickmart": self.quickmart,
            "Kilimall":  self.kilimall,
            # Carrefour disabled — site blocks all automated access from this IP
            "Amazon":    self.amazon,
        }

    def search(self, query: str, category: str = "all") -> list[Product]:
        self.logger.info(f"Starting search for: '{query}' (category: {category})")

        allowed = self.CATEGORY_SCRAPERS.get(category, self.CATEGORY_SCRAPERS["all"])
        scrapers = {name: s for name, s in self._all_scrapers.items() if name in allowed}

        results = {name: [] for name in scrapers}
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(scraper.scrape, query): name
                for name, scraper in scrapers.items()
            }
            try:
                for future in concurrent.futures.as_completed(futures, timeout=35):
                    name = futures[future]
                    try:
                        results[name] = future.result(timeout=30)
                    except Exception as e:
                        self.logger.warning(f"{name} scraper failed: {e}")
                        results[name] = []
            except concurrent.futures.TimeoutError:
                self.logger.warning("Some scrapers did not finish in time — using partial results")
                for future, name in futures.items():
                    if not future.done():
                        self.logger.warning(f"{name}: timed out, skipping")
                        future.cancel()

        combined = []
        for name in scrapers:
            combined.extend(results.get(name, []))
        combined.sort(key=lambda p: p.price)

        self.logger.info(
            "Search complete — " +
            ", ".join(f"{n}: {len(results.get(n, []))}" for n in scrapers) +
            f", Total: {len(combined)}"
        )
        return combined


# ══════════════════════════════════════════════════════════════════════════════
# QUICK TEST — run: py scraper.py
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    scraper = PriceComparisonScraper()
    results = scraper.search("samsung galaxy")

    if results:
        print(f"\n{'='*60}")
        print(f"  Found {len(results)} products")
        print(f"{'='*60}")
        for i, p in enumerate(results, 1):
            print(f"\n[{i}] {p.name[:55]}")
            print(f"    Site  : {p.site}")
            print(f"    Price : {p.currency} {p.price:,.0f}")
            print(f"    URL   : {p.url[:60]}")
    else:
        print("No results found. Check your selectors in config.py.")
