# db.py
# Handles all database operations for BeiSmart KE
# Uses SQLite - a lightweight database stored as a single file

import sqlite3
import pandas as pd
from datetime import datetime
from config import DB_NAME


class Database:
    """
    Manages all interactions with the SQLite database.
    Handles creating tables, inserting products, and querying history.
    """

    def __init__(self):
        """Connect to the database and create tables if they don't exist."""
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Create the products and watchlist tables if they don't exist."""

        # Products table - stores every scraped product with a timestamp
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL,
                site      TEXT    NOT NULL,
                price     REAL    NOT NULL,
                currency  TEXT    NOT NULL DEFAULT 'KSh',
                url       TEXT,
                image_url TEXT,
                query     TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Watchlist table - stores items the user wants to monitor
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                query           TEXT    NOT NULL,
                alert_threshold REAL,
                email           TEXT,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()

    def insert_products(self, products: list, query: str):
        """
        Save a list of scraped products to the database.

        Args:
            products: List of Product dataclass objects from scraper.py
            query: The search term used to find these products
        """
        for product in products:
            self.cursor.execute('''
                INSERT INTO products (name, site, price, currency, url, image_url, query)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                product.name,
                product.site,
                product.price,
                product.currency,
                product.url,
                product.image_url,
                query
            ))
        self.conn.commit()

    def get_results(self, query: str) -> pd.DataFrame:
        """
        Get the most recent scraped results for a search query.

        Args:
            query: The product search term

        Returns:
            DataFrame of the latest results sorted by price (lowest first)
        """
        sql = '''
            SELECT name, site, price, currency, url, image_url, timestamp
            FROM products
            WHERE query LIKE ?
            AND timestamp >= (
                SELECT MAX(timestamp) FROM products WHERE query LIKE ?
            )
            ORDER BY price ASC
        '''
        df = pd.read_sql_query(sql, self.conn, params=(f"%{query}%", f"%{query}%"))
        return df

    def get_price_history(self, query: str) -> pd.DataFrame:
        """
        Get full price history for a product query (for trend charts).

        Args:
            query: The product search term

        Returns:
            DataFrame with price history ordered by timestamp
        """
        sql = '''
            SELECT name, site, price, currency, timestamp
            FROM products
            WHERE query LIKE ?
            ORDER BY timestamp ASC
        '''
        df = pd.read_sql_query(sql, self.conn, params=(f"%{query}%",))
        return df

    def add_to_watchlist(self, query: str, threshold: float, email: str):
        """
        Add a product query to the watchlist for price monitoring.

        Args:
            query: Product search term to watch
            threshold: Alert when price drops below this value (KSh)
            email: Email address to send alerts to
        """
        self.cursor.execute('''
            INSERT INTO watchlist (query, alert_threshold, email)
            VALUES (?, ?, ?)
        ''', (query, threshold, email))
        self.conn.commit()

    def get_watchlist(self) -> pd.DataFrame:
        """
        Retrieve all items currently on the watchlist.

        Returns:
            DataFrame of all watchlist entries
        """
        return pd.read_sql_query(
            "SELECT * FROM watchlist ORDER BY created_at DESC",
            self.conn
        )

    def remove_from_watchlist(self, watchlist_id: int):
        """
        Remove an item from the watchlist by its ID.

        Args:
            watchlist_id: The ID of the watchlist entry to remove
        """
        self.cursor.execute(
            "DELETE FROM watchlist WHERE id = ?", (watchlist_id,)
        )
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()


if __name__ == "__main__":
    # Quick test - run this file directly to verify the DB is working
    db = Database()
    print("✅ Database connected successfully!")
    print(f"✅ Tables created in '{DB_NAME}'")
    db.close()