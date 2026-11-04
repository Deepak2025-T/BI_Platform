"""
Creates two demo accounts, sample sales data, templates and categories.
Run from the backend folder, after creating the tables with `alembic upgrade head`:
    python -m app.seed
"""

from datetime import date, timedelta

from sqlalchemy import func, select

from .database import SessionLocal, schema_missing_message
from .models import ReportCategory, ReportTemplate, Sale, User
from .routers.templates import ensure_builtin_templates
from .security import hash_password
from .template_data import SAMPLE_TEMPLATES

DEMO_USERS = [
    ("manager@example.com", "Demo Manager", "Manager@123", "manager"),
    ("user@example.com", "Demo User", "User@123", "user"),
]

SAMPLE_CATEGORIES = [
    ("Sales", "Revenue, regions and products", "#00B4D8"),
    ("Finance", "Profit, costs and budgets", "#0D3B66"),
    ("Executive", "Short summaries for leadership", "#A63D40"),
]

# Net revenue per region per month for Q1 2024, in thousands
Q1_NET = {"North": [380, 420, 486], "South": [310, 330, 352],
          "East": [240, 236, 258], "West": [352, 398, 438]}
PRODUCT_SHARE = {"Pro License": 1520, "Enterprise": 1310, "Starter": 620, "Team": 440, "Add-ons": 310}
Q4_FACTOR = 0.847  # Q4 2023 is about 18% lower than Q1 2024


def seed():
    if (problem := schema_missing_message()):
        raise SystemExit(problem)
    db = SessionLocal()
    try:
        for email, name, pw, role in DEMO_USERS:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, full_name=name, password_hash=hash_password(pw), role=role))
                print(f"  created {role}: {email} / {pw}")

        if db.scalar(select(func.count(Sale.id))) == 0:
            share_total = sum(PRODUCT_SHARE.values())
            months = [(date(2023, 10, 1), date(2024, 1, 1), Q4_FACTOR),
                      (date(2023, 11, 1), date(2024, 2, 1), Q4_FACTOR),
                      (date(2023, 12, 1), date(2024, 3, 1), Q4_FACTOR),
                      (date(2024, 1, 1), date(2024, 1, 1), 1.0),
                      (date(2024, 2, 1), date(2024, 2, 1), 1.0),
                      (date(2024, 3, 1), date(2024, 3, 1), 1.0)]
            rows = 0
            for month_start, q1_month, factor in months:
                idx = q1_month.month - 1
                for region, values in Q1_NET.items():
                    net_month = values[idx] * 1000 * factor
                    for product, share in PRODUCT_SHARE.items():
                        net = net_month * share / share_total
                        # Two sales per month per product so the data looks realistic
                        for day, part in ((8, 0.45), (21, 0.55)):
                            n = round(net * part, 2)
                            sale_day = month_start.replace(day=day)
                            db.add(Sale(sale_date=sale_day, invoice_date=sale_day + timedelta(days=12),
                                        region=region, product=product,
                                        revenue=round(n * 1.075, 2), discount=round(n * 0.06, 2),
                                        refund_amount=round(n * 0.015, 2)))
                            rows += 1
            print(f"  inserted {rows} sample sales rows")
        db.commit()
        ensure_builtin_templates(db)
        seed_sample_templates(db)
        seed_sample_categories(db)
        print("Seed complete.")
    finally:
        db.close()


def seed_sample_templates(db):
    """Adds each sample template unless its owner already has one with the same name."""
    added = 0
    for t in SAMPLE_TEMPLATES:
        owner = db.scalar(select(User).where(User.email == t["owner"]))
        if owner is None:
            continue
        exists = db.scalar(select(ReportTemplate.id).where(ReportTemplate.owner_id == owner.id,
                                                           ReportTemplate.name == t["name"]))
        if exists is None:
            db.add(ReportTemplate(owner_id=owner.id, **{k: v for k, v in t.items() if k != "owner"}))
            added += 1
    db.commit()
    if added:
        print(f"  created {added} sample templates")


def seed_sample_categories(db):
    """Adds the sample report categories that don't exist yet."""
    manager = db.scalar(select(User).where(User.role == "manager").order_by(User.id))
    added = 0
    for name, description, color in SAMPLE_CATEGORIES:
        if db.scalar(select(ReportCategory.id).where(func.lower(ReportCategory.name) == name.lower())) is None:
            db.add(ReportCategory(name=name, description=description, color=color,
                                  created_by=manager.id if manager else None))
            added += 1
    db.commit()
    if added:
        print(f"  created {added} sample report categories")


if __name__ == "__main__":
    seed()
