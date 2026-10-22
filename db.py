import os
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "company_bi.db"


def init_database(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Initializes and seeds a realistic enterprise e-commerce / retail database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Drop existing tables
    cur.executescript(
        """
        DROP TABLE IF EXISTS returns;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            tier TEXT CHECK(tier IN ('Standard', 'Silver', 'Gold', 'Platinum')) NOT NULL,
            joined_date DATE NOT NULL
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_cost REAL NOT NULL,
            unit_price REAL NOT NULL,
            stock_quantity INTEGER NOT NULL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date DATE NOT NULL,
            status TEXT CHECK(status IN ('Delivered', 'Shipped', 'Processing', 'Cancelled')) NOT NULL,
            payment_method TEXT NOT NULL,
            shipping_city TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount_pct REAL DEFAULT 0.0,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );

        CREATE TABLE returns (
            return_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            return_date DATE NOT NULL,
            reason TEXT NOT NULL,
            refund_amount REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """
    )

    # Seed Customers
    cities = [
        ("Pune", "Maharashtra"),
        ("Mumbai", "Maharashtra"),
        ("Bengaluru", "Karnataka"),
        ("Hyderabad", "Telangana"),
        ("Delhi", "Delhi"),
        ("Chennai", "Tamil Nadu"),
    ]
    tiers = ["Standard", "Silver", "Gold", "Platinum"]
    first_names = ["Aarav", "Ananya", "Rohan", "Pooja", "Vikram", "Neha", "Rahul", "Priya", "Aditya", "Sneha", "Karan", "Tanvi"]
    last_names = ["Sharma", "Patil", "Deshmukh", "Verma", "Kulkarni", "Iyer", "Mehta", "Reddy", "Joshi", "Nair"]

    customers_data = []
    for i in range(1, 41):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
        city, state = random.choice(cities)
        tier = random.choice(tiers)
        join_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")
        customers_data.append((name, email, city, state, tier, join_date))

    cur.executemany(
        "INSERT INTO customers (full_name, email, city, state, tier, joined_date) VALUES (?, ?, ?, ?, ?, ?)",
        customers_data,
    )

    # Seed Products
    products_raw = [
        ("Aura Noise-Cancelling Headphones", "Electronics", 4500.0, 8999.0, 120),
        ("ErgoPro Mesh Office Chair", "Furniture", 6200.0, 12499.0, 45),
        ("UltraView 27-inch 4K Monitor", "Electronics", 14000.0, 24999.0, 35),
        ("HydroSteel Thermal Flask 1L", "Home & Kitchen", 350.0, 899.0, 300),
        ("Apex Mechanical Keyboard (RGB)", "Electronics", 2100.0, 4499.0, 80),
        ("Bamboo Standing Desk Converter", "Furniture", 3800.0, 7999.0, 25),
        ("SmartFit Active Smartwatch", "Wearables", 1800.0, 3799.0, 150),
        ("ColdBrew Artisan Coffee Maker", "Home & Kitchen", 850.0, 1999.0, 90),
        ("CloudRest Memory Foam Pillow", "Bedding", 600.0, 1499.0, 110),
        ("SoundPulse Bluetooth Speaker", "Electronics", 1100.0, 2599.0, 140),
    ]
    cur.executemany(
        "INSERT INTO products (product_name, category, unit_cost, unit_price, stock_quantity) VALUES (?, ?, ?, ?, ?)",
        products_raw,
    )

    # Seed Orders & Order Items
    order_statuses = ["Delivered", "Delivered", "Delivered", "Shipped", "Processing", "Cancelled"]
    pay_methods = ["UPI", "Credit Card", "Debit Card", "Net Banking"]

    orders_data = []
    order_items_data = []
    returns_data = []

    order_id_counter = 1
    for o_idx in range(1, 91):
        cust_id = random.randint(1, 40)
        c_city, _ = random.choice(cities)
        o_date = (datetime(2025, 1, 1) + timedelta(days=random.randint(0, 280))).strftime("%Y-%m-%d")
        status = random.choice(order_statuses)
        pay_method = random.choice(pay_methods)

        orders_data.append((cust_id, o_date, status, pay_method, c_city))

        # Add 1-3 items per order
        num_items = random.randint(1, 3)
        chosen_prods = random.sample(range(1, 11), num_items)
        for p_id in chosen_prods:
            qty = random.randint(1, 3)
            # Fetch price from products_raw (p_id is 1-indexed)
            price = products_raw[p_id - 1][3]
            disc = random.choice([0.0, 0.05, 0.10, 0.15])
            order_items_data.append((order_id_counter, p_id, qty, price, disc))

            # Small chance of return if delivered
            if status == "Delivered" and random.random() < 0.12:
                r_date = (datetime.strptime(o_date, "%Y-%m-%d") + timedelta(days=random.randint(2, 10))).strftime("%Y-%m-%d")
                reason = random.choice(["Defective item", "Changed mind", "Performance below expectations", "Wrong size/variant"])
                refund = qty * price * (1.0 - disc)
                returns_data.append((order_id_counter, p_id, r_date, reason, round(refund, 2)))

        order_id_counter += 1

    cur.executemany(
        "INSERT INTO orders (customer_id, order_date, status, payment_method, shipping_city) VALUES (?, ?, ?, ?, ?)",
        orders_data,
    )

    cur.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_pct) VALUES (?, ?, ?, ?, ?)",
        order_items_data,
    )

    cur.executemany(
        "INSERT INTO returns (order_id, product_id, return_date, reason, refund_amount) VALUES (?, ?, ?, ?, ?)",
        returns_data,
    )

    conn.commit()
    return conn


def get_schema_summary(conn: sqlite3.Connection) -> str:
    """Generates an LLM-friendly database schema summary with table names, column types, and sample data."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]

    schema_lines = []
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        col_desc = ", ".join([f"{c[1]} ({c[2]})" for c in cols])
        schema_lines.append(f"Table: {t}")
        schema_lines.append(f"  Columns: {col_desc}")

        # Fetch sample rows
        cur.execute(f"SELECT * FROM {t} LIMIT 2")
        samples = cur.fetchall()
        if samples:
            schema_lines.append(f"  Sample Row: {samples[0]}")
        schema_lines.append("")

    return "\n".join(schema_lines)


def ensure_db():
    """Ensures that the SQLite warehouse is seeded on first startup."""
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        init_database(DB_PATH)

ensure_db()

if __name__ == "__main__":
    conn = init_database()
    print(f"Database successfully seeded at: {DB_PATH}")
    print("\n--- SCHEMA SUMMARY ---")
    print(get_schema_summary(conn))
    conn.close()
