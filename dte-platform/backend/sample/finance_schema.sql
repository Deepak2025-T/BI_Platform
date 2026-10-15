-- ERP Accounts / Finance target schema (PostgreSQL). Comments are indexed into pgvector for RAG.
CREATE TABLE IF NOT EXISTS accounts (
    account_id   SERIAL PRIMARY KEY,
    code         VARCHAR(20) UNIQUE NOT NULL,
    name         VARCHAR(150) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('asset','liability','equity','revenue','expense')),
    category     VARCHAR(80),
    parent_code  VARCHAR(20)
);
COMMENT ON TABLE accounts IS 'Chart of accounts (general ledger accounts)';
COMMENT ON COLUMN accounts.account_type IS 'asset, liability, equity, revenue or expense';
COMMENT ON COLUMN accounts.category IS 'Reporting group e.g. Sales, Payroll, Rent, Travel, Bank';

CREATE TABLE IF NOT EXISTS parties (
    party_id   SERIAL PRIMARY KEY,
    name       VARCHAR(150) UNIQUE NOT NULL,
    party_type VARCHAR(20) NOT NULL CHECK (party_type IN ('customer','vendor')),
    region     VARCHAR(60),
    segment    VARCHAR(60),
    email      VARCHAR(150)
);
COMMENT ON TABLE parties IS 'Customers and vendors (business partners)';

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    sku        VARCHAR(40) UNIQUE NOT NULL,
    name       VARCHAR(150) NOT NULL,
    category   VARCHAR(80),
    unit_price NUMERIC(14,2)
);
COMMENT ON TABLE products IS 'Products and services sold or purchased';

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id     SERIAL PRIMARY KEY,
    invoice_no     VARCHAR(40) UNIQUE NOT NULL,
    invoice_type   VARCHAR(20) NOT NULL CHECK (invoice_type IN ('sales','purchase')),
    party_id       INT REFERENCES parties(party_id),
    invoice_date   DATE NOT NULL,
    due_date       DATE,
    currency       VARCHAR(3) DEFAULT 'INR',
    amount_untaxed NUMERIC(14,2) DEFAULT 0,
    tax_amount     NUMERIC(14,2) DEFAULT 0,
    total_amount   NUMERIC(14,2) NOT NULL,
    amount_paid    NUMERIC(14,2) DEFAULT 0,
    status         VARCHAR(20) DEFAULT 'posted' CHECK (status IN ('draft','posted','paid','cancelled'))
);
COMMENT ON TABLE invoices IS 'Customer invoices (sales = accounts receivable / revenue) and vendor bills (purchase = accounts payable / expense)';
COMMENT ON COLUMN invoices.total_amount IS 'Invoice total including tax';
COMMENT ON COLUMN invoices.amount_paid IS 'Amount settled so far; outstanding = total_amount - amount_paid';

CREATE TABLE IF NOT EXISTS invoice_lines (
    line_id     SERIAL PRIMARY KEY,
    invoice_id  INT REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    product_id  INT REFERENCES products(product_id),
    account_id  INT REFERENCES accounts(account_id),
    description VARCHAR(255),
    quantity    NUMERIC(12,2) DEFAULT 1,
    unit_price  NUMERIC(14,2) DEFAULT 0,
    line_total  NUMERIC(14,2) NOT NULL
);
COMMENT ON TABLE invoice_lines IS 'Invoice line items with product and GL account';

CREATE TABLE IF NOT EXISTS journal_entries (
    entry_id   SERIAL PRIMARY KEY,
    entry_no   VARCHAR(40) UNIQUE NOT NULL,
    entry_date DATE NOT NULL,
    reference  VARCHAR(120),
    source     VARCHAR(30) DEFAULT 'manual',
    status     VARCHAR(20) DEFAULT 'posted'
);
COMMENT ON TABLE journal_entries IS 'General ledger journal entry headers';

CREATE TABLE IF NOT EXISTS journal_lines (
    line_id     SERIAL PRIMARY KEY,
    entry_id    INT REFERENCES journal_entries(entry_id) ON DELETE CASCADE,
    account_id  INT REFERENCES accounts(account_id),
    party_id    INT REFERENCES parties(party_id),
    debit       NUMERIC(14,2) DEFAULT 0,
    credit      NUMERIC(14,2) DEFAULT 0,
    description VARCHAR(255)
);
COMMENT ON TABLE journal_lines IS 'Journal entry lines. Revenue = credit - debit on revenue accounts; expense = debit - credit on expense accounts';

CREATE TABLE IF NOT EXISTS payments (
    payment_id   SERIAL PRIMARY KEY,
    payment_no   VARCHAR(40) UNIQUE NOT NULL,
    payment_type VARCHAR(20) NOT NULL CHECK (payment_type IN ('inbound','outbound')),
    party_id     INT REFERENCES parties(party_id),
    invoice_id   INT REFERENCES invoices(invoice_id),
    payment_date DATE NOT NULL,
    amount       NUMERIC(14,2) NOT NULL,
    method       VARCHAR(30)
);
COMMENT ON TABLE payments IS 'Cash receipts from customers (inbound) and payments to vendors (outbound)';

CREATE TABLE IF NOT EXISTS forecasts (
    forecast_id SERIAL PRIMARY KEY,
    metric      VARCHAR(60) NOT NULL,
    period      DATE NOT NULL,
    value       NUMERIC(16,2),
    lower_bound NUMERIC(16,2),
    upper_bound NUMERIC(16,2),
    model       VARCHAR(40),
    created_at  TIMESTAMP DEFAULT now()
);
COMMENT ON TABLE forecasts IS 'Auto-generated finance forecasts (monthly revenue, expense, net cash)';
