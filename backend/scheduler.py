# scheduler.py — BeiSmart KE
# Runs in the background, re-scraping watchlist items every 24 hours
# and sending email alerts when prices drop below user thresholds

import smtplib
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from scraper import PriceComparisonScraper
from db import Database
from config import (
    EMAIL_SENDER, EMAIL_PASSWORD,
    SMTP_HOST, SMTP_PORT,
    SCRAPE_INTERVAL_HOURS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("beismart.scheduler")


def send_email_alert(to_email: str, query: str, lowest_price: float, threshold: float, products: list):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"BeiSmart KE Alert: {query} dropped to KSh {lowest_price:,.0f}!"
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email

        product_rows = ""
        for p in sorted(products, key=lambda x: x.price)[:5]:
            product_rows += f"""
            <tr>
                <td style="padding:8px; border-bottom:1px solid #eee;">{p.name[:60]}</td>
                <td style="padding:8px; border-bottom:1px solid #eee;">{p.site}</td>
                <td style="padding:8px; border-bottom:1px solid #eee; color:#f0a500; font-weight:bold;">
                    KSh {p.price:,.0f}
                </td>
                <td style="padding:8px; border-bottom:1px solid #eee;">
                    <a href="{p.url}" style="color:#2E75B6;">View</a>
                </td>
            </tr>
            """

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
            <div style="max-width:600px; margin:0 auto; background:white;
                        border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <div style="background:#1F4E79; padding:24px; text-align:center;">
                    <h1 style="color:white; margin:0; font-size:24px;">BeiSmart KE</h1>
                    <p style="color:#a0c4e8; margin:8px 0 0;">Price Drop Alert</p>
                </div>
                <div style="padding:24px;">
                    <h2 style="color:#1F4E79;">Good news! A price drop was detected.</h2>
                    <p style="color:#555;">
                        You are monitoring: <strong>{query}</strong><br>
                        Your alert threshold: <strong>KSh {threshold:,.0f}</strong><br>
                        Current lowest price: <strong style="color:#f0a500;">KSh {lowest_price:,.0f}</strong>
                    </p>
                    <h3 style="color:#1F4E79; margin-top:24px;">Top Results</h3>
                    <table style="width:100%; border-collapse:collapse; font-size:13px;">
                        <thead>
                            <tr style="background:#f0f4f8;">
                                <th style="padding:8px; text-align:left;">Product</th>
                                <th style="padding:8px; text-align:left;">Site</th>
                                <th style="padding:8px; text-align:left;">Price</th>
                                <th style="padding:8px; text-align:left;">Link</th>
                            </tr>
                        </thead>
                        <tbody>
                            {product_rows}
                        </tbody>
                    </table>
                </div>
                <div style="background:#f0f4f8; padding:16px; text-align:center;">
                    <p style="color:#888; font-size:12px; margin:0;">
                        BeiSmart KE © 2026 — For educational use only.<br>
                        You received this because you added <strong>{query}</strong> to your watchlist.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_email, msg.as_string())

        logger.info(f"Alert email sent to {to_email} for '{query}'")

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Email auth failed for '{EMAIL_SENDER}' — check .env credentials and ensure App Password is correct")
        raise
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send email: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        raise


def run_scrape_job():
    logger.info("=" * 50)
    logger.info(f"Scheduled scrape job started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    db = Database()
    scraper = PriceComparisonScraper()
    watchlist = db.get_watchlist()

    if watchlist.empty:
        logger.info("Watchlist is empty — nothing to scrape.")
        db.close()
        return

    logger.info(f"Found {len(watchlist)} watchlist items to process.")
    alerts_sent = 0

    for _, item in watchlist.iterrows():
        query = item["query"]
        threshold = item["alert_threshold"]
        email = item["email"]

        logger.info(f"Processing: '{query}' (threshold: KSh {threshold:,.0f})")

        try:
            products = scraper.search(query)

            if not products:
                logger.warning(f"No results found for '{query}' — skipping.")
                continue

            db.insert_products(products, query)
            logger.info(f"Saved {len(products)} new price records for '{query}'")

            lowest_price = min(p.price for p in products)
            logger.info(f"Lowest price for '{query}': KSh {lowest_price:,.0f} (threshold: KSh {threshold:,.0f})")

            if lowest_price <= threshold:
                logger.info(f"ALERT triggered for '{query}'! Sending email to {email}")
                send_email_alert(email, query, lowest_price, threshold, products)
                alerts_sent += 1
            else:
                logger.info(f"No alert needed for '{query}' — price above threshold.")

        except Exception as e:
            logger.error(f"Error processing '{query}': {e}")
            continue

    logger.info(f"Scrape job complete. Alerts sent: {alerts_sent}")
    db.close()


class BeiSmartScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.running = False

    def start(self):
        if self.running:
            logger.warning("Scheduler is already running.")
            return

        self.scheduler.add_job(
            func=run_scrape_job,
            trigger=IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS),
            id="beismart_scrape_job",
            name="BeiSmart KE Scheduled Scrape",
            replace_existing=True,
        )
        self.scheduler.start()
        self.running = True
        logger.info(f"Scheduler started — scraping every {SCRAPE_INTERVAL_HOURS} hours.")

    def stop(self):
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Scheduler stopped.")

    def get_next_run(self) -> str:
        jobs = self.scheduler.get_jobs()
        if jobs:
            next_run = jobs[0].next_run_time
            return next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else "Unknown"
        return "Not scheduled"

    def run_now(self):
        logger.info("Manual scrape triggered.")
        thread = threading.Thread(target=run_scrape_job, daemon=True)
        thread.start()


if __name__ == "__main__":
    import time
    print("Running one immediate scrape job...")
    print("Make sure you have items in your watchlist first\n")
    run_scrape_job()
    print("\nStarting scheduler...")
    scheduler = BeiSmartScheduler()
    scheduler.start()
    print(f"Next run: {scheduler.get_next_run()}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("Scheduler stopped.")