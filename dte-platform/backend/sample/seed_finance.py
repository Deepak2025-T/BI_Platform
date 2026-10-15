"""Create the finance schema and load 24 months of realistic demo data.
Usage: python sample/seed_finance.py postgresql+psycopg://postgres:postgres@localhost:5432/finance_demo"""
import datetime as dt
import pathlib
import random
import sys

from sqlalchemy import create_engine, text

URL = sys.argv[1] if len(sys.argv) > 1 else "postgresql+psycopg://postgres:postgres@localhost:5432/finance_demo"
rnd = random.Random(42)

ACCOUNTS = [
    ("1000", "Cash at Bank", "asset", "Bank"), ("1100", "Accounts Receivable", "asset", "Receivables"),
    ("2000", "Accounts Payable", "liability", "Payables"), ("2100", "GST Payable", "liability", "Tax"),
    ("3000", "Owner Equity", "equity", "Equity"),
    ("4000", "Consulting Revenue", "revenue", "Services"), ("4100", "Software Licence Revenue", "revenue", "Licences"),
    ("4200", "Training Revenue", "revenue", "Training"),
    ("5000", "Salaries", "expense", "Payroll"), ("5100", "Office Rent", "expense", "Rent"),
    ("5200", "Travel", "expense", "Travel"), ("5300", "Cloud Hosting", "expense", "IT"),
    ("5400", "Marketing", "expense", "Marketing"), ("5500", "Professional Fees", "expense", "Professional Services"),
]
CUSTOMERS = [("GKW Consult", "Europe", "Enterprise"), ("Acme Industries", "North India", "Enterprise"),
             ("Bluewave Retail", "West India", "Mid-market"), ("Nimbus Health", "South India", "Enterprise"),
             ("Orion Logistics", "Middle East", "Mid-market"), ("Pixel Labs", "West India", "SMB"),
             ("Sterling Finance", "Europe", "Enterprise"), ("Vertex Edu", "North India", "SMB"),
             ("Zenith Motors", "South India", "Mid-market"), ("Kite Foods", "East India", "SMB")]
VENDORS = [("AWS India", "IT"), ("WeWork Pune", "Rent"), ("MakeMyTrip Corporate", "Travel"),
           ("Google Ads", "Marketing"), ("Deloitte Advisory", "Professional Services"), ("Payroll Co", "Payroll")]
PRODUCTS = [("SVC-CONS", "Consulting Day", "Services", 45000, "4000"), ("SVC-AUD", "Audit Advisory", "Services", 60000, "4000"),
            ("LIC-GRC", "GRC Suite Licence", "Licences", 250000, "4100"), ("LIC-BI", "BI Platform Licence", "Licences", 180000, "4100"),
            ("TRN-PBI", "Power BI Training", "Training", 35000, "4200")]
VENDOR_ACC = {"IT": "5300", "Rent": "5100", "Travel": "5200", "Marketing": "5400", "Professional Services": "5500", "Payroll": "5000"}
VENDOR_BASE = {"IT": 180000, "Rent": 250000, "Travel": 90000, "Marketing": 120000, "Professional Services": 150000, "Payroll": 1900000}


def main():
    eng = create_engine(URL, future=True)
    ddl = (pathlib.Path(__file__).parent / "finance_schema.sql").read_text()
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS forecasts, payments, journal_lines, journal_entries, invoice_lines, invoices, products, parties, accounts CASCADE"))
        c.exec_driver_sql(ddl)
        acc = {}
        for code, name, typ, cat in ACCOUNTS:
            acc[code] = c.execute(text("INSERT INTO accounts(code,name,account_type,category) VALUES (:a,:b,:c,:d) RETURNING account_id"),
                                  dict(a=code, b=name, c=typ, d=cat)).scalar()
        cust, vend, prod = {}, {}, {}
        for n, r, s in CUSTOMERS:
            cust[n] = c.execute(text("INSERT INTO parties(name,party_type,region,segment) VALUES (:n,'customer',:r,:s) RETURNING party_id"), dict(n=n, r=r, s=s)).scalar()
        for n, cat in VENDORS:
            vend[n] = (c.execute(text("INSERT INTO parties(name,party_type,region,segment) VALUES (:n,'vendor','India',:s) RETURNING party_id"), dict(n=n, s=cat)).scalar(), cat)
        for sku, n, cat, price, accode in PRODUCTS:
            prod[sku] = (c.execute(text("INSERT INTO products(sku,name,category,unit_price) VALUES (:a,:b,:c,:d) RETURNING product_id"), dict(a=sku, b=n, c=cat, d=price)).scalar(), price, accode)

        today = dt.date(2026, 9, 30)
        start = dt.date(2024, 10, 1)
        inv_no = je_no = pay_no = 0
        month = start
        m_index = 0
        while month <= today:
            growth = 1 + 0.025 * m_index
            season = 1.15 if month.month in (3, 12) else (0.85 if month.month in (5, 8) else 1.0)
            # ---- sales invoices
            for _ in range(rnd.randint(8, 14)):
                inv_no += 1
                cname = rnd.choices(list(cust), weights=[6, 5, 3, 4, 2, 1, 4, 1, 2, 1])[0]
                d = month + dt.timedelta(days=rnd.randint(0, 27))
                lines = []
                for sku in rnd.sample(list(prod), rnd.randint(1, 2)):
                    pid, price, accode = prod[sku]
                    qty = rnd.randint(1, 6) if sku.startswith("SVC") or sku.startswith("TRN") else 1
                    lt = round(price * qty * growth * season * rnd.uniform(0.85, 1.15), 2)
                    lines.append((pid, acc[accode], sku, qty, round(lt / qty, 2), lt))
                untaxed = round(sum(x[5] for x in lines), 2)
                tax = round(untaxed * 0.18, 2)
                total = untaxed + tax
                due = d + dt.timedelta(days=30)
                age = (today - due).days
                paid = total if age > 45 or rnd.random() < 0.55 else (round(total * 0.5, 2) if rnd.random() < 0.3 else 0)
                status = "paid" if paid >= total else "posted"
                iid = c.execute(text("""INSERT INTO invoices(invoice_no,invoice_type,party_id,invoice_date,due_date,amount_untaxed,tax_amount,total_amount,amount_paid,status)
                    VALUES (:no,'sales',:p,:d,:due,:u,:t,:tot,:paid,:st) RETURNING invoice_id"""),
                    dict(no=f"INV/{d.year}/{inv_no:05d}", p=cust[cname], d=d, due=due, u=untaxed, t=tax, tot=total, paid=paid, st=status)).scalar()
                for pid, aid, sku, qty, up, lt in lines:
                    c.execute(text("INSERT INTO invoice_lines(invoice_id,product_id,account_id,description,quantity,unit_price,line_total) VALUES (:i,:p,:a,:d,:q,:u,:l)"),
                              dict(i=iid, p=pid, a=aid, d=sku, q=qty, u=up, l=lt))
                je_no += 1
                eid = c.execute(text("INSERT INTO journal_entries(entry_no,entry_date,reference,source) VALUES (:n,:d,:r,'sales') RETURNING entry_id"),
                                dict(n=f"JE/{je_no:06d}", d=d, r=f"INV/{d.year}/{inv_no:05d}")).scalar()
                c.execute(text("INSERT INTO journal_lines(entry_id,account_id,party_id,debit,credit) VALUES (:e,:a,:p,:v,0)"), dict(e=eid, a=acc["1100"], p=cust[cname], v=total))
                for pid, aid, sku, qty, up, lt in lines:
                    c.execute(text("INSERT INTO journal_lines(entry_id,account_id,party_id,debit,credit) VALUES (:e,:a,:p,0,:v)"), dict(e=eid, a=aid, p=cust[cname], v=lt))
                c.execute(text("INSERT INTO journal_lines(entry_id,account_id,debit,credit) VALUES (:e,:a,0,:v)"), dict(e=eid, a=acc["2100"], v=tax))
                if paid:
                    pay_no += 1
                    pd_ = min(today, due + dt.timedelta(days=rnd.randint(-10, 20)))
                    c.execute(text("INSERT INTO payments(payment_no,payment_type,party_id,invoice_id,payment_date,amount,method) VALUES (:n,'inbound',:p,:i,:d,:a,:m)"),
                              dict(n=f"PAY/{pay_no:06d}", p=cust[cname], i=iid, d=pd_, a=paid, m=rnd.choice(["NEFT", "RTGS", "Wire"])))
            # ---- vendor bills
            for vname, (vid, cat) in vend.items():
                inv_no += 1
                d = month + dt.timedelta(days=rnd.randint(0, 10))
                amt = round(VENDOR_BASE[cat] * (1 + 0.015 * m_index) * rnd.uniform(0.8, 1.25) * (season if cat in ("Travel", "Marketing") else 1), 2)
                due = d + dt.timedelta(days=15)
                paid = amt if (today - due).days > 20 or rnd.random() < 0.6 else 0
                iid = c.execute(text("""INSERT INTO invoices(invoice_no,invoice_type,party_id,invoice_date,due_date,amount_untaxed,tax_amount,total_amount,amount_paid,status)
                    VALUES (:no,'purchase',:p,:d,:due,:u,0,:u,:paid,:st) RETURNING invoice_id"""),
                    dict(no=f"BILL/{d.year}/{inv_no:05d}", p=vid, d=d, due=due, u=amt, paid=paid, st="paid" if paid else "posted")).scalar()
                c.execute(text("INSERT INTO invoice_lines(invoice_id,account_id,description,quantity,unit_price,line_total) VALUES (:i,:a,:d,1,:u,:u)"),
                          dict(i=iid, a=acc[VENDOR_ACC[cat]], d=cat, u=amt))
                je_no += 1
                eid = c.execute(text("INSERT INTO journal_entries(entry_no,entry_date,reference,source) VALUES (:n,:d,:r,'purchase') RETURNING entry_id"),
                                dict(n=f"JE/{je_no:06d}", d=d, r=f"BILL/{d.year}/{inv_no:05d}")).scalar()
                c.execute(text("INSERT INTO journal_lines(entry_id,account_id,party_id,debit,credit) VALUES (:e,:a,:p,:v,0)"), dict(e=eid, a=acc[VENDOR_ACC[cat]], p=vid, v=amt))
                c.execute(text("INSERT INTO journal_lines(entry_id,account_id,party_id,debit,credit) VALUES (:e,:a,:p,0,:v)"), dict(e=eid, a=acc["2000"], p=vid, v=amt))
                if paid:
                    pay_no += 1
                    c.execute(text("INSERT INTO payments(payment_no,payment_type,party_id,invoice_id,payment_date,amount,method) VALUES (:n,'outbound',:p,:i,:d,:a,'NEFT')"),
                              dict(n=f"PAY/{pay_no:06d}", p=vid, i=iid, d=min(today, due), a=paid))
            m_index += 1
            month = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    print(f"Seeded {inv_no} invoices, {je_no} journal entries, {pay_no} payments into {URL.split('@')[-1]}")


if __name__ == "__main__":
    main()
