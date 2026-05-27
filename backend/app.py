# app.py — BeiSmart KE
# Flask backend — serves frontend and exposes scraper as API

import os
import sys

# Allow backend/ imports to resolve when run from project root
sys.path.insert(0, os.path.dirname(__file__))

import json
import queue
import concurrent.futures
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from scraper import PriceComparisonScraper
from db import Database
from scheduler import BeiSmartScheduler
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("beismart.app")

# Resolve paths relative to the project root (one level up from backend/)
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_TEMPLATES = os.path.join(_ROOT, "frontend", "templates")
_STATIC    = os.path.join(_ROOT, "frontend", "static")

app = Flask(__name__, template_folder=_TEMPLATES, static_folder=_STATIC)
db = Database()
scheduler = BeiSmartScheduler()
scheduler.start()


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/search")
def index():
    return render_template("index.html")

@app.route("/history")
def history():
    return render_template("history.html")

@app.route("/watchlist")
def watchlist():
    return render_template("watchlist.html")


# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/search")
def api_search():
    query    = request.args.get("q", "").strip()
    category = request.args.get("category", "all").strip().lower()
    if not query:
        return jsonify({"error": "No query provided"}), 400
    try:
        scraper = PriceComparisonScraper()
        products = scraper.search(query, category)
        if products:
            db.insert_products(products, query)
        results = db.get_results(query)
        return jsonify({
            "query": query,
            "count": len(results),
            "products": results.to_dict(orient="records")
        })
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
def api_history():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "No query provided"}), 400
    try:
        df = db.get_price_history(query)
        if df.empty:
            return jsonify({"query": query, "history": []})
        df["timestamp"] = df["timestamp"].astype(str)
        return jsonify({
            "query": query,
            "history": df.to_dict(orient="records")
        })
    except Exception as e:
        logger.error(f"History error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist", methods=["GET"])
def api_watchlist_get():
    try:
        df = db.get_watchlist()
        if df.empty:
            return jsonify({"watchlist": []})
        df["created_at"] = df["created_at"].astype(str)
        return jsonify({"watchlist": df.to_dict(orient="records")})
    except Exception as e:
        logger.error(f"Watchlist get error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist", methods=["POST"])
def api_watchlist_add():
    data = request.get_json()
    query = data.get("query", "").strip()
    threshold = data.get("threshold", 0)
    email = data.get("email", "").strip()
    if not query or not email:
        return jsonify({"error": "Query and email are required"}), 400
    try:
        db.add_to_watchlist(query, float(threshold), email)
        return jsonify({"success": True, "message": f"'{query}' added to watchlist"})
    except Exception as e:
        logger.error(f"Watchlist add error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist/<int:item_id>", methods=["DELETE"])
def api_watchlist_delete(item_id):
    try:
        db.remove_from_watchlist(item_id)
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Watchlist delete error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/check-prices", methods=["POST"])
def api_check_prices():
    try:
        scheduler.run_now()
        return jsonify({"success": True, "message": "Price check triggered"})
    except Exception as e:
        logger.error(f"Price check error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/search/stream")
def api_search_stream():
    query    = request.args.get("q", "").strip()
    category = request.args.get("category", "all").strip().lower()
    if not query:
        return jsonify({"error": "No query provided"}), 400

    scraper_facade = PriceComparisonScraper()
    allowed = scraper_facade.CATEGORY_SCRAPERS.get(category, scraper_facade.CATEGORY_SCRAPERS["all"])
    scrapers = {name: s for name, s in scraper_facade._all_scrapers.items() if name in allowed}

    result_queue = queue.Queue()

    def run_scraper(name, scraper):
        try:
            products = scraper.scrape(query)
            result_queue.put((name, products))
        except Exception as e:
            logger.warning(f"{name} stream scraper failed: {e}")
            result_queue.put((name, []))

    def generate():
        all_products = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = {executor.submit(run_scraper, name, s): name for name, s in scrapers.items()}
            finished = 0
            total = len(scrapers)
            deadline = 35

            import time
            start = time.time()

            while finished < total:
                elapsed = time.time() - start
                remaining = max(0.5, deadline - elapsed)
                try:
                    name, products = result_queue.get(timeout=remaining)
                    finished += 1
                    all_products.extend(products)
                    chunk = {
                        "event": "chunk",
                        "site": name,
                        "count": len(products),
                        "products": [
                            {
                                "name":      p.name,
                                "price":     p.price,
                                "site":      p.site,
                                "url":       p.url,
                                "image_url": p.image_url,
                                "currency":  p.currency,
                            } for p in products
                        ],
                        "done": finished == total,
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                except queue.Empty:
                    logger.warning("Stream: deadline reached, closing")
                    break

        if all_products:
            try:
                db.insert_products(all_products, query)
            except Exception as e:
                logger.warning(f"Stream: DB insert failed: {e}")

        yield f"data: {json.dumps({'event': 'done', 'total': len(all_products)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/api/status")
def api_status():
    return jsonify({
        "status": "running",
        "next_scrape": scheduler.get_next_run()
    })


@app.route("/api/test-email", methods=["POST"])
def api_test_email():
    data = request.get_json()
    to_email = data.get("email", "").strip()
    if not to_email:
        return jsonify({"error": "email is required"}), 400
    try:
        from scheduler import send_email_alert
        from scraper import Product
        dummy = [Product(
            name="Samsung 55\" QLED TV",
            price=49999,
            site="Jumia",
            url="https://www.jumia.co.ke",
            image_url="",
            currency="KSh"
        )]
        send_email_alert(to_email, "Samsung TV", 49999, 55000, dummy)
        return jsonify({"success": True, "message": f"Test email sent to {to_email}"})
    except Exception as e:
        logger.error(f"Test email error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
