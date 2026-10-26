"""
A demo business database to try connections, chat, dashboards and auto-refresh on.

Run from the backend folder (with .venv):

    python -m app.demo_shop                  builds the demo_shop schema and its Connection
    python -m app.demo_shop --add-orders 25  adds 25 new orders dated today, to see auto-refresh pick them up
    python -m app.demo_shop --remove         drops the schema and deletes the Connection

It creates the schema "demo_shop" in the app database (the database in DATABASE_URL), fills it
with about two years of made-up orders for a small retailer ending today, and adds a PostgreSQL
connection called "Demo shop" on the Connections page, limited to these tables.

The connection logs in with the app's own database account, because that account can't create a
separate read-only login. Queries are still checked (one SELECT, demo_shop tables only) and run in
read-only transactions. For real databases, use a read-only account as README Part 9 describes.
Everything here is made up; names use example.com addresses.
"""

import argparse
import datetime as dt
import random

from sqlalchemy import func, select, text

from .connections import crypto
from .connections.engines import ConnSpec, make_engine, run_test
from .database import SessionLocal, engine
from .models import DataConnection

SCHEMA = "demo_shop"
CONNECTION_NAME = "Demo shop"
START = dt.date(2024, 1, 1)
REGIONS = {"North": ["Leeds", "Manchester", "Newcastle"], "South": ["London", "Brighton", "Southampton"],
           "East": ["Norwich", "Cambridge", "Ipswich"], "West": ["Bristol", "Cardiff", "Exeter"]}
SEGMENTS = [("Consumer", 0.6), ("Small business", 0.3), ("Enterprise", 0.1)]
CHANNELS = [("Web", 0.55), ("Store", 0.3), ("Phone", 0.15)]
REPS = ["Asha Patel", "Ben Clarke", "Chen Wei", "Dana Okafor", "Elif Demir", "Farid Khan"]
FIRST = ["Alex", "Sam", "Priya", "Jordan", "Maria", "Tom", "Aisha", "Leo", "Nina", "Omar", "Ruth", "Ivan",
         "Grace", "Kenji", "Lucy", "Mateo", "Zara", "Hugo", "Ines", "Ravi"]
LAST = ["Smith", "Jones", "Khan", "Brown", "Garcia", "Nguyen", "Taylor", "Murphy", "Silva", "Novak",
        "Evans", "Haddad", "Wilson", "Ito", "Kowalski", "Okoro"]
PRODUCTS = [  # name, category, unit price, unit cost
    ("Laptop Pro 14", "Computers", 1299, 950), ("Laptop Air 13", "Computers", 999, 720),
    ("Desktop Tower", "Computers", 849, 610), ("Mini PC", "Computers", 499, 350),
    ("27in Monitor", "Monitors", 329, 230), ("32in 4K Monitor", "Monitors", 549, 400),
    ("Portable Monitor", "Monitors", 199, 130), ("Mechanical Keyboard", "Accessories", 119, 60),
    ("Wireless Mouse", "Accessories", 39, 15), ("USB-C Dock", "Accessories", 159, 90),
    ("Webcam HD", "Accessories", 79, 40), ("Noise-cancelling Headset", "Audio", 229, 140),
    ("Bluetooth Speaker", "Audio", 89, 45), ("Studio Microphone", "Audio", 149, 85),
    ("Office Chair", "Furniture", 289, 170), ("Standing Desk", "Furniture", 499, 320),
    ("Desk Lamp", "Furniture", 49, 22), ("Laser Printer", "Printers", 259, 180),
    ("Ink Bundle", "Printers", 59, 25), ("Support Plan 1yr", "Services", 149, 30),
    ("Setup Service", "Services", 99, 40), ("Cloud Backup 1yr", "Services", 79, 15),
]

DDL = f"""
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.customers (
    id INTEGER PRIMARY KEY, name VARCHAR(80) NOT NULL, email VARCHAR(120) NOT NULL,
    city VARCHAR(40) NOT NULL, region VARCHAR(20) NOT NULL, segment VARCHAR(20) NOT NULL, signup_date DATE NOT NULL);
CREATE TABLE {SCHEMA}.products (
    id INTEGER PRIMARY KEY, name VARCHAR(60) NOT NULL, category VARCHAR(30) NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL, unit_cost NUMERIC(10, 2) NOT NULL);
CREATE TABLE {SCHEMA}.orders (
    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES {SCHEMA}.customers(id),
    order_date DATE NOT NULL, status VARCHAR(12) NOT NULL, channel VARCHAR(10) NOT NULL, sales_rep VARCHAR(40) NOT NULL);
CREATE TABLE {SCHEMA}.order_items (
    id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES {SCHEMA}.orders(id),
    product_id INTEGER NOT NULL REFERENCES {SCHEMA}.products(id), quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL, discount NUMERIC(10, 2) NOT NULL);
CREATE TABLE {SCHEMA}.monthly_targets (
    month DATE NOT NULL, region VARCHAR(20) NOT NULL, target_revenue NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (month, region));
CREATE INDEX ON {SCHEMA}.orders (order_date);
CREATE INDEX ON {SCHEMA}.order_items (order_id);
COMMENT ON TABLE {SCHEMA}.orders IS 'One row per order. Only completed orders count as sales.';
COMMENT ON COLUMN {SCHEMA}.orders.status IS 'completed, cancelled or refunded. Revenue and order counts use completed orders only.';
COMMENT ON COLUMN {SCHEMA}.order_items.quantity IS 'Units sold on this line.';
COMMENT ON COLUMN {SCHEMA}.order_items.unit_price IS 'Price of one unit when sold, in GBP.';
COMMENT ON COLUMN {SCHEMA}.order_items.discount IS 'Discount for the whole line as a money amount in GBP, not a percentage. Line revenue = quantity * unit_price - discount.';
COMMENT ON COLUMN {SCHEMA}.products.unit_cost IS 'What one unit costs us, in GBP. Profit = revenue - quantity * unit_cost.';
COMMENT ON COLUMN {SCHEMA}.monthly_targets.month IS 'First day of the month.';
COMMENT ON COLUMN {SCHEMA}.monthly_targets.target_revenue IS 'Revenue target for the region and month, in GBP after discounts. Compare with completed orders of customers in that region.';
COMMENT ON SCHEMA {SCHEMA} IS 'Demo data for BI Report Platform. Safe to drop: python -m app.demo_shop --remove';
"""

TABLES = ["customers", "products", "orders", "order_items", "monthly_targets"]


def _pick(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    return rng.choices([v for v, _ in weighted], [w for _, w in weighted])[0]


def _orders_for_day(rng: random.Random, day: dt.date) -> int:
    """Busier on weekdays, in Nov to Dec, and growing about 25% a year."""
    years = (day - START).days / 365
    seasonal = 1.45 if day.month in (11, 12) else 0.8 if day.month in (1, 8) else 1.0
    weekday = 0.6 if day.weekday() >= 5 else 1.1
    return max(0, int(rng.gauss(7 * (1 + 0.25 * years) * seasonal * weekday, 2)))


def build(today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    rng = random.Random(2024)  # same data every time
    customers, orders, items = [], [], []
    for i in range(1, 451):
        region = rng.choice(list(REGIONS))
        first, last = rng.choice(FIRST), rng.choice(LAST)
        customers.append({"id": i, "name": f"{first} {last}", "email": f"{first}.{last}{i}@example.com".lower(),
                          "city": rng.choice(REGIONS[region]), "region": region, "segment": _pick(rng, SEGMENTS),
                          "signup_date": START + dt.timedelta(days=rng.randint(-400, (today - START).days - 30))})
    products = [{"id": i, "name": n, "category": c, "unit_price": p, "unit_cost": cost}
                for i, (n, c, p, cost) in enumerate(PRODUCTS, start=1)]
    day, order_id, item_id = START, 0, 0
    while day <= today:
        for _ in range(_orders_for_day(rng, day)):
            order_id += 1
            cust = rng.choice(customers)
            orders.append({"id": order_id, "customer_id": cust["id"], "order_date": day,
                           "status": _pick(rng, [("completed", 0.9), ("cancelled", 0.06), ("refunded", 0.04)]),
                           "channel": _pick(rng, CHANNELS), "sales_rep": rng.choice(REPS)})
            for _ in range(rng.choices([1, 2, 3, 4], [0.5, 0.3, 0.15, 0.05])[0]):
                item_id += 1
                p = rng.choice(products)
                qty = rng.choices([1, 2, 3, 5, 10], [0.6, 0.2, 0.1, 0.06, 0.04])[0] * (3 if cust["segment"] == "Enterprise" else 1)
                items.append({"id": item_id, "order_id": order_id, "product_id": p["id"], "quantity": qty,
                              "unit_price": p["unit_price"],
                              "discount": round(p["unit_price"] * qty * rng.choice([0, 0, 0, 0.05, 0.1]), 2)})
        day += dt.timedelta(days=1)
    targets = []
    month = START
    while month <= today:
        for region in REGIONS:
            targets.append({"month": month, "region": region,
                            "target_revenue": round(rng.uniform(55000, 75000) * (1 + 0.25 * (month - START).days / 365), -2)})
        month = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return {"customers": customers, "products": products, "orders": orders, "order_items": items, "monthly_targets": targets}


def _insert(conn, table: str, rows: list[dict]):
    if rows:
        cols = list(rows[0])
        conn.execute(text(f"INSERT INTO {SCHEMA}.{table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"), rows)


def create():
    if engine.dialect.name != "postgresql":
        raise SystemExit("The demo shop needs PostgreSQL (DATABASE_URL in backend/.env).")
    data = build()
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        conn.exec_driver_sql(DDL)
        for table in TABLES:
            _insert(conn, table, data[table])
    print(f"Built schema {SCHEMA}: " + ", ".join(f"{len(data[t])} {t}" for t in TABLES) + ".")
    connect()


def connect():
    """Adds or updates the "Demo shop" connection, limited to the demo tables, and tests it."""
    url = engine.url  # the app database; the password stays inside the program
    spec = ConnSpec(db_type="postgresql", host=url.host or "localhost", port=url.port, database=url.database,
                    username=url.username or "", password=url.password or "", options={})
    allowed = [f"{SCHEMA}.{t}" for t in TABLES]
    with SessionLocal() as db:
        c = db.scalar(select(DataConnection).where(func.lower(DataConnection.name) == CONNECTION_NAME.lower()))
        if c is None:
            c = DataConnection(name=CONNECTION_NAME, db_type="postgresql")
            db.add(c)
        c.host, c.port, c.database, c.username = spec.host, spec.port, spec.database, spec.username
        c.password_encrypted = crypto.encrypt(spec.password)  # needs CONNECTIONS_KEY
        c.schemas, c.allowed_tables, c.options = [SCHEMA], allowed, {}
        test_engine = make_engine(spec, pooled=False)
        try:
            result = run_test(test_engine, spec, [SCHEMA])
            c.status, c.last_error = "ok", ""
            note = f"connected, {result['table_count']} tables"
        except Exception as err:
            c.status, c.last_error, note = "error", str(err)[:500], f"test failed: {err}"
        finally:
            test_engine.dispose()
        c.last_tested_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
        print(f'Connection "{CONNECTION_NAME}" is ready ({note}). Users can query: {", ".join(allowed)}.')


def add_orders(n: int):
    """Adds n completed orders dated today, as if new sales came in."""
    rng = random.Random()
    with engine.begin() as conn:
        next_order = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {SCHEMA}.orders")).scalar()
        next_item = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {SCHEMA}.order_items")).scalar()
        customers = conn.execute(text(f"SELECT id FROM {SCHEMA}.customers")).scalars().all()
        products = conn.execute(text(f"SELECT id, unit_price FROM {SCHEMA}.products")).all()
        orders, items = [], []
        for i in range(n):
            orders.append({"id": next_order + i, "customer_id": rng.choice(customers), "order_date": dt.date.today(),
                           "status": "completed", "channel": _pick(rng, CHANNELS), "sales_rep": rng.choice(REPS)})
            pid, price = rng.choice(products)
            items.append({"id": next_item + i, "order_id": next_order + i, "product_id": pid,
                          "quantity": rng.randint(1, 3), "unit_price": price, "discount": 0})
        _insert(conn, "orders", orders)
        _insert(conn, "order_items", items)
        total = sum(float(it["unit_price"]) * it["quantity"] for it in items)
    print(f"Added {n} orders dated today, worth {total:,.2f} in total.")


def remove():
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    with SessionLocal() as db:
        c = db.scalar(select(DataConnection).where(func.lower(DataConnection.name) == CONNECTION_NAME.lower()))
        if c is not None:
            db.delete(c)
            db.commit()
    print(f'Removed schema {SCHEMA} and the "{CONNECTION_NAME}" connection.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo business data for BI Report Platform.")
    parser.add_argument("--add-orders", type=int, metavar="N", help="add N orders dated today")
    parser.add_argument("--remove", action="store_true", help="drop the demo schema and its connection")
    args = parser.parse_args()
    if args.remove:
        remove()
    elif args.add_orders:
        add_orders(args.add_orders)
    else:
        create()
