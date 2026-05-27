from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

QUICKMART_COOKIES = [
    {"name": "_ygGeoAddress", "value": "Nairobi%2C%20Kenya", "domain": "www.quickmart.co.ke", "path": "/"},
    {"name": "_ygGeoLat",     "value": "-1.2920659",          "domain": "www.quickmart.co.ke", "path": "/"},
    {"name": "_ygGeoLng",     "value": "36.8219462",          "domain": "www.quickmart.co.ke", "path": "/"},
    {"name": "_ygGeoRadius",  "value": "7",                   "domain": "www.quickmart.co.ke", "path": "/"},
    {"name": "_ygShopId",     "value": "58",                  "domain": "www.quickmart.co.ke", "path": "/"},
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    context.add_cookies(QUICKMART_COOKIES)
    page = context.new_page()
    page.goto("https://www.quickmart.co.ke/products/search?keyword=milk&pagesize=30")
    page.wait_for_selector("div.product-listing", timeout=20000)
    page.wait_for_timeout(2000)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "lxml")
listing = soup.select_one("div.product-listing")
print(listing.prettify()[:3000])
