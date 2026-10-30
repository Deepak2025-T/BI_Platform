"""
Loads the ERP demo data (erp_demo.sql) into one of the saved connections, and shares its
tables so reports can use them.

    python -m app.erp_demo --connection finance_demo
    python -m app.erp_demo --connection finance_demo --no-share   # load only

The connection must be a PostgreSQL one, and the account it uses has to be allowed to
create schemas — unlike the read-only account reports should normally run with. Only the
tables in erp_demo.sql are dropped and recreated; nothing else in the database is touched.
"""

import argparse
from pathlib import Path

from sqlalchemy import select, text

from .connections import connection_spec
from .connections.engines import dispose_engine, make_engine
from .database import SessionLocal
from .models import DataConnection

SQL_FILE = Path(__file__).with_name("erp_demo.sql")

# What the script creates, in the order the templates read them.
TABLES = [
    "crm.customers", "crm.leads", "crm.opportunities",
    "helpdesk.agents", "helpdesk.tickets",
    "lms.courses", "lms.learners", "lms.enrollments",
    "account.vendors", "account.ap_invoices", "account.ar_invoices", "account.cash_collections",
    "sales.products", "sales.sales_orders", "sales.order_lines", "sales.targets",
]


def load(connection_name: str, share: bool = True) -> None:
    db = SessionLocal()
    try:
        conn = db.scalar(select(DataConnection).where(DataConnection.name == connection_name))
        if conn is None:
            names = ", ".join(c.name for c in db.scalars(select(DataConnection)).all()) or "none saved"
            raise SystemExit(f'No connection called "{connection_name}". Saved connections: {names}')
        if conn.db_type != "postgresql":
            raise SystemExit(f'"{connection_name}" is {conn.db_type}; this data is written for PostgreSQL.')

        engine = make_engine(connection_spec(conn), pooled=False)
        try:
            # Straight to the driver, with no parameters: the script is full of % (modulo), and
            # anything that takes parameters reads those as placeholders. One transaction, so a
            # failure half way leaves nothing behind.
            raw = engine.raw_connection()
            try:
                with raw.cursor() as cur:
                    cur.execute(SQL_FILE.read_text(encoding="utf-8"))
                raw.commit()
            finally:
                raw.close()
            with engine.connect() as cx:
                for table in TABLES:
                    count = cx.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                    print(f"  {table:<28} {count:>6} rows")
        finally:
            engine.dispose()

        if share:
            # Reports can only read tables a manager has shared, so add them to the list.
            allowed = list(conn.allowed_tables or [])
            added = [t for t in TABLES if t not in allowed]
            conn.allowed_tables = allowed + added
            dispose_engine(conn.id)  # the next query re-reads the connection
            db.commit()
            print(f"\nShared {len(added)} new table(s) on {conn.name}; {len(conn.allowed_tables)} in total.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the ERP demo data into a saved connection.")
    parser.add_argument("--connection", default="finance_demo", help="name of the saved connection")
    parser.add_argument("--no-share", action="store_true", help="load the data but don't share the tables")
    args = parser.parse_args()
    print(f"Loading {SQL_FILE.name} into {args.connection} …")
    load(args.connection, share=not args.no_share)


if __name__ == "__main__":
    main()
