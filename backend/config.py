# config.py
# Central configuration file for BeiSmart KE

import os
from dotenv import load_dotenv

# Load .env from the project root (one level up from backend/)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_ROOT, ".env"))

# ── Database ──────────────────────────────────────────────
DB_NAME = os.path.join(_ROOT, "beismart.db")

# ── Scraper settings ──────────────────────────────────────
MIN_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 5.0
MAX_RESULTS_PER_SITE = 10
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3

# ── Site URLs ─────────────────────────────────────────────
JUMIA_BASE_URL = "https://www.jumia.co.ke"
AVECHI_BASE_URL = "https://avechi.co.ke"

# ── Jumia CSS selectors ───────────────────────────────────
JUMIA_SELECTORS = {
    "product_card": "article.prd",
    "name": "h3.name",
    "price": ".prc",
    "link": "a.core",
    "image": "img",
}

# ── Avechi CSS selectors ──────────────────────────────────
AVECHI_SELECTORS = {
    "product_card": "div.product",
    "name": "h3.text-clamp a",
    "price": "span.price ins .woocommerce-Price-amount bdi",
    "price_fallback": "span.price .woocommerce-Price-amount bdi",
    "link": "figure a",
    "image": "figure img",
}

# ── Email alert settings (loaded from .env) ───────────────
EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")
SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))

# ── Scheduler settings ────────────────────────────────────
SCRAPE_INTERVAL_HOURS = 24

HOTPOINT_BASE_URL = "https://www.hotpoint.co.ke"
HOTPOINT_SELECTORS = {
    "product_card": "div.product-item",
    "name": "h5.product-card-name",
    "price": "span.stockrecord-price-current",
    "link": "a",
    "image": "img.product-card-img",
}

# ── Kilimall (internal JSON API) ──────────────────────────────────────────────
KILIMALL_API_URL = "https://www.kilimall.co.ke/api/product/search"

# ── Carrefour Kenya ───────────────────────────────────────────────────────────
CARREFOUR_BASE_URL = "https://www.carrefour.ke"
CARREFOUR_API_URL  = "https://www.carrefour.ke/api/rest/v2/products/search"

# ── Amazon ────────────────────────────────────────────────────────────────────
AMAZON_BASE_URL = "https://www.amazon.com"
AMAZON_SELECTORS = {
    "product_card": "div[data-component-type='s-search-result']",
    "name":         "h2 span.a-text-normal",
    "price_whole":  "span.a-price-whole",
    "price_frac":   "span.a-price-fraction",
    "link":         "h2 a.a-link-normal",
    "image":        "img.s-image",
}
# Approximate USD → KSh conversion rate (update periodically)
USD_TO_KSH = 129.0