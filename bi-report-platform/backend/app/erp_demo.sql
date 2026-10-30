-- =====================================================================================
-- ERP demo data: CRM, Helpdesk, LMS, Account and Sales.
--
-- Five schemas modelled on the ERP reports in frontend/Template/ERP_Template, so the
-- built-in ERP dashboard templates have something real to run against. Load it with:
--
--     python -m app.erp_demo --connection finance_demo
--
-- Every table is dropped and rebuilt, so running it twice is safe. Only the tables
-- listed here are touched; anything else in the database is left alone.
--
-- The numbers are made up but not random: each row is derived from its own id, so the
-- same data comes back every time it is loaded, and the charts don't move underfoot.
-- Dates run from 2025-01-01 to 2026-10-31, and money is in rupees unless a column says
-- otherwise.
-- =====================================================================================


-- =====================================================================================
-- CRM — leads, opportunities and the customers they belong to
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS crm;
DROP TABLE IF EXISTS crm.opportunities CASCADE;
DROP TABLE IF EXISTS crm.leads CASCADE;
DROP TABLE IF EXISTS crm.customers CASCADE;

CREATE TABLE crm.customers (
    customer_id   integer PRIMARY KEY,
    customer_name text NOT NULL,
    industry      text NOT NULL,
    country       text NOT NULL,
    region        text NOT NULL,
    segment       text NOT NULL,
    account_owner text NOT NULL,
    created_date  date NOT NULL
);

INSERT INTO crm.customers
SELECT g,
       (ARRAY['Infosys','TCS Global','Wipro Tech','HCL Systems','Adani Ports','Reliance Industries',
              'HDFC Bank','Tata Steel','Mahindra Group','NTPC','Larsen & Toubro','Bharti Airtel',
              'Asian Paints','Godrej Consumer','JSW Energy','UltraTech Cement','Hindalco','Dr Reddys',
              'Sun Pharma','Titan Company','Zomato','Swiggy','Paytm','Ola Electric'])[1 + (g % 24)]
         || ' ' || (ARRAY['Ltd','Pvt Ltd','Group','Holdings','International'])[1 + ((g / 24) % 5)],
       (ARRAY['Manufacturing','Banking','Technology','Energy','Retail','Healthcare','Logistics','Education'])[1 + (g % 8)],
       (ARRAY['India','Bangladesh','Nepal','Sri Lanka','Vietnam','Thailand','Singapore','UAE','Saudi Arabia','Germany'])[1 + (g % 10)],
       CASE WHEN g % 10 < 4 THEN 'South Asia' WHEN g % 10 < 7 THEN 'Southeast Asia'
            WHEN g % 10 < 9 THEN 'Middle East' ELSE 'Europe' END,
       (ARRAY['Enterprise','Mid-market','Enterprise','SMB','Mid-market'])[1 + (g % 5)],
       (ARRAY['Priya Sharma','Rahul Kumar','Amit Desai','Neha Gupta','Vikram Rao','Sana Khan'])[1 + (g % 6)],
       DATE '2025-01-01' + ((g * 7) % 560)
FROM generate_series(1, 120) g;

CREATE TABLE crm.leads (
    lead_id       integer PRIMARY KEY,
    lead_name     text NOT NULL,
    company       text NOT NULL,
    source        text NOT NULL,
    campaign      text NOT NULL,
    country       text NOT NULL,
    region        text NOT NULL,
    sales_rep     text NOT NULL,
    status        text NOT NULL,          -- New / Qualified / Converted / Lost
    lost_reason   text,
    created_date  date NOT NULL,
    converted_date date,
    days_to_convert integer,
    estimated_value numeric(14, 2) NOT NULL
);

INSERT INTO crm.leads
WITH g AS (SELECT gs AS g, gs % 10 AS ci, (gs * 13) % 100 AS roll FROM generate_series(1, 1400) gs)
SELECT g,
       (ARRAY['Ananya','Rohit','Kavya','Arjun','Meera','Siddharth','Pooja','Karan','Divya','Nikhil'])[1 + (g % 10)]
         || ' ' || (ARRAY['Nair','Iyer','Singh','Bose','Menon','Patel','Reddy','Joshi'])[1 + ((g / 10) % 8)],
       (ARRAY['Infosys','TCS Global','Wipro Tech','HCL Systems','Adani Ports','Reliance Industries',
              'HDFC Bank','Tata Steel','Mahindra Group','NTPC','Larsen & Toubro','Bharti Airtel'])[1 + (g % 12)] || ' Ltd',
       (ARRAY['Website','Cold call','Referral','Email campaign','Trade show','Partner','LinkedIn'])[1 + (g % 7)],
       (ARRAY['Q1 Webinar','Odoo Days','Always-on search','Industry mailer','Customer referral','Regional roadshow'])[1 + (g % 6)],
       (ARRAY['India','Bangladesh','Nepal','Sri Lanka','Vietnam','Thailand','Singapore','UAE','Saudi Arabia','Germany'])[ci + 1],
       CASE WHEN ci < 4 THEN 'South Asia' WHEN ci < 7 THEN 'Southeast Asia'
            WHEN ci < 9 THEN 'Middle East' ELSE 'Europe' END,
       (ARRAY['Priya Sharma','Rahul Kumar','Amit Desai','Neha Gupta','Vikram Rao','Sana Khan'])[1 + (g % 6)],
       -- Referrals convert better than cold calls; the mix lands near a third converted.
       CASE WHEN roll < 26 THEN 'Converted' WHEN roll < 48 THEN 'Lost'
            WHEN roll < 74 THEN 'Qualified' ELSE 'New' END,
       CASE WHEN roll BETWEEN 26 AND 47
            THEN (ARRAY['Price too high','Lost to competitor','No budget','No decision','Bad timing','No response'])[1 + (g % 6)] END,
       DATE '2025-01-01' + ((g * 11) % 660),
       CASE WHEN roll < 26 THEN DATE '2025-01-01' + ((g * 11) % 660) + (5 + (g % 40)) END,
       CASE WHEN roll < 26 THEN 5 + (g % 40) END,
       ((120000 + ((g * 37) % 880000)))::numeric(14, 2)
FROM g;

CREATE TABLE crm.opportunities (
    opportunity_id integer PRIMARY KEY,
    opportunity    text NOT NULL,
    customer_id    integer REFERENCES crm.customers(customer_id),
    customer_name  text NOT NULL,
    sales_rep      text NOT NULL,
    sales_team     text NOT NULL,
    stage          text NOT NULL,         -- New / Qualified / Proposition / Won / Lost
    is_won         boolean NOT NULL,
    is_closed      boolean NOT NULL,
    probability    integer NOT NULL,
    expected_value numeric(14, 2) NOT NULL,
    created_date   date NOT NULL,
    close_date     date NOT NULL,
    sales_cycle_days integer NOT NULL,
    lost_reason    text,
    region         text NOT NULL,
    source         text NOT NULL
);

INSERT INTO crm.opportunities
WITH g AS (SELECT gs AS g, (gs * 17) % 100 AS roll, 1 + (gs % 120) AS cust FROM generate_series(1, 720) gs)
SELECT g,
       (ARRAY['ERP rollout','Support renewal','Cloud migration','Licence upgrade','Analytics project',
              'Implementation phase 2','Managed services','Training programme'])[1 + (g % 8)]
         || ' — ' || c.customer_name,
       c.customer_id, c.customer_name, c.account_owner,
       (ARRAY['Enterprise','Mid-market','Channel'])[1 + (g % 3)],
       CASE WHEN roll < 34 THEN 'Won' WHEN roll < 58 THEN 'Lost' WHEN roll < 74 THEN 'Proposition'
            WHEN roll < 88 THEN 'Qualified' ELSE 'New' END,
       roll < 34,
       roll < 58,
       CASE WHEN roll < 34 THEN 100 WHEN roll < 58 THEN 0 WHEN roll < 74 THEN 60
            WHEN roll < 88 THEN 35 ELSE 10 END,
       ((250000 + ((g * 53) % 3400000)))::numeric(14, 2),
       DATE '2025-01-01' + ((g * 19) % 620),
       DATE '2025-01-01' + ((g * 19) % 620) + (12 + ((g * 7) % 70)),
       12 + ((g * 7) % 70),
       CASE WHEN roll BETWEEN 34 AND 57
            THEN (ARRAY['Price too high','Lost to competitor','No budget','Project cancelled','Bad timing'])[1 + (g % 5)] END,
       c.region,
       (ARRAY['Website','Cold call','Referral','Email campaign','Trade show','Partner','LinkedIn'])[1 + (g % 7)]
FROM g JOIN crm.customers c ON c.customer_id = g.cust;


-- =====================================================================================
-- Helpdesk — tickets, the agents who work them and how they did against SLA
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS helpdesk;
DROP TABLE IF EXISTS helpdesk.tickets CASCADE;
DROP TABLE IF EXISTS helpdesk.agents CASCADE;

CREATE TABLE helpdesk.agents (
    agent_id    integer PRIMARY KEY,
    agent_name  text NOT NULL,
    team        text NOT NULL,
    tier        text NOT NULL,
    region      text NOT NULL,
    joined_date date NOT NULL
);

INSERT INTO helpdesk.agents
SELECT g,
       (ARRAY['Sneha','Ravi','Manish','Aisha','Deepak','Tanvi','Harsh','Nisha','Arun','Zoya','Varun','Ishita'])[1 + (g % 12)]
         || ' ' || (ARRAY['Verma','Pillai','Chawla','Das'])[1 + ((g / 12) % 4)],
       (ARRAY['Technical Support','Billing','Onboarding','Field Service'])[1 + (g % 4)],
       (ARRAY['Tier 1','Tier 1','Tier 2','Tier 3'])[1 + (g % 4)],
       (ARRAY['South Asia','Southeast Asia','Middle East','Europe'])[1 + (g % 4)],
       DATE '2024-01-01' + ((g * 23) % 700)
FROM generate_series(1, 24) g;

CREATE TABLE helpdesk.tickets (
    ticket_id        integer PRIMARY KEY,
    ticket_ref       text NOT NULL,
    subject          text NOT NULL,
    customer_name    text NOT NULL,
    category         text NOT NULL,
    channel          text NOT NULL,
    priority         text NOT NULL,       -- Low / Medium / High / Urgent
    status           text NOT NULL,       -- Open / In Progress / Waiting / Resolved / Closed
    team             text NOT NULL,
    agent_id         integer REFERENCES helpdesk.agents(agent_id),
    agent_name       text NOT NULL,
    region           text NOT NULL,
    created_date     date NOT NULL,
    resolved_date    date,
    first_response_hours numeric(6, 2) NOT NULL,
    resolution_hours numeric(8, 2),
    sla_target_hours integer NOT NULL,
    sla_met          boolean NOT NULL,
    reopened         boolean NOT NULL,
    age_days         integer NOT NULL,
    csat_rating      integer              -- 1..5, only on resolved tickets
);

INSERT INTO helpdesk.tickets
WITH g AS (SELECT gs AS g, (gs * 29) % 100 AS roll, (gs * 31) % 100 AS roll2,
                  1 + (gs % 24) AS ag, DATE '2025-01-01' + ((gs * 3) % 668) AS created
           FROM generate_series(1, 2400) gs)
SELECT g,
       'HD/' || to_char(created, 'YYYY') || '/' || lpad(g::text, 5, '0'),
       (ARRAY['Login fails after update','Invoice not generated','Slow report loading','Data import error',
              'Licence activation','Email notifications missing','Payment gateway timeout','User access request',
              'Printer configuration','Mobile app crash'])[1 + (g % 10)],
       (ARRAY['Infosys Ltd','TCS Global Ltd','Wipro Tech Ltd','HCL Systems Ltd','Adani Ports Ltd',
              'Reliance Industries Ltd','HDFC Bank Ltd','Tata Steel Ltd'])[1 + (g % 8)],
       (ARRAY['Technical','Billing','Access','Data','Feature request','Training'])[1 + (g % 6)],
       (ARRAY['Email','Portal','Phone','Chat','Portal'])[1 + (g % 5)],
       CASE WHEN roll < 12 THEN 'Urgent' WHEN roll < 36 THEN 'High'
            WHEN roll < 74 THEN 'Medium' ELSE 'Low' END,
       CASE WHEN roll2 < 58 THEN 'Closed' WHEN roll2 < 72 THEN 'Resolved' WHEN roll2 < 84 THEN 'In Progress'
            WHEN roll2 < 92 THEN 'Waiting' ELSE 'Open' END,
       a.team, a.agent_id, a.agent_name, a.region,
       created,
       CASE WHEN roll2 < 72 THEN created + (1 + (g % 9)) END,
       (round((0.5 + ((g * 7) % 110) / 10.0)::numeric, 2)),
       CASE WHEN roll2 < 72 THEN round((1.5 + ((g * 11) % 460) / 10.0)::numeric, 2) END,
       -- Urgent tickets are held to 4 hours, low priority to two days.
       CASE WHEN roll < 12 THEN 4 WHEN roll < 36 THEN 8 WHEN roll < 74 THEN 24 ELSE 48 END,
       (0.5 + ((g * 7) % 110) / 10.0) <= CASE WHEN roll < 12 THEN 4 WHEN roll < 36 THEN 8
                                              WHEN roll < 74 THEN 24 ELSE 48 END,
       (g % 17) = 0,
       GREATEST(0, (DATE '2026-10-31' - created)),
       CASE WHEN roll2 < 72 THEN (ARRAY[5,4,5,3,4,5,2,4,5,1])[1 + (g % 10)] END
FROM g JOIN helpdesk.agents a ON a.agent_id = g.ag;


-- =====================================================================================
-- LMS — courses, learners and what they finished
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS lms;
DROP TABLE IF EXISTS lms.enrollments CASCADE;
DROP TABLE IF EXISTS lms.learners CASCADE;
DROP TABLE IF EXISTS lms.courses CASCADE;

CREATE TABLE lms.courses (
    course_id       integer PRIMARY KEY,
    course_title    text NOT NULL,
    category        text NOT NULL,
    level           text NOT NULL,        -- Beginner / Intermediate / Advanced
    instructor      text NOT NULL,
    duration_hours  numeric(5, 1) NOT NULL,
    gives_certificate boolean NOT NULL,
    published_date  date NOT NULL
);

INSERT INTO lms.courses
SELECT g,
       (ARRAY['Odoo ERP','Financial Accounting','Data Analytics','Project Management','Cyber Security',
              'Power BI','SQL for Analysts','Leadership','Customer Service','Supply Chain'])[1 + (g % 10)]
         || ' — ' || (ARRAY['Foundations','Practitioner','Masterclass','Certification Track'])[1 + ((g / 10) % 4)],
       (ARRAY['Technology','Finance','Compliance','Soft skills','Operations'])[1 + (g % 5)],
       (ARRAY['Beginner','Intermediate','Advanced','Intermediate'])[1 + (g % 4)],
       (ARRAY['Dr A Menon','S Krishnan','R Bhatt','L Fernandes','P Oberoi'])[1 + (g % 5)],
       (ARRAY[4.0,6.0,8.0,10.0,12.0,16.0])[1 + (g % 6)],
       (g % 3) <> 2,
       DATE '2024-06-01' + ((g * 13) % 500)
FROM generate_series(1, 40) g;

CREATE TABLE lms.learners (
    learner_id   integer PRIMARY KEY,
    learner_name text NOT NULL,
    department   text NOT NULL,
    region       text NOT NULL,
    country      text NOT NULL,
    job_level    text NOT NULL,
    joined_date  date NOT NULL
);

INSERT INTO lms.learners
WITH g AS (SELECT gs AS g, gs % 10 AS ci FROM generate_series(1, 600) gs)
SELECT g,
       (ARRAY['Aditya','Shreya','Mohit','Rhea','Gaurav','Ira','Kabir','Naina','Dev','Tara'])[1 + (g % 10)]
         || ' ' || (ARRAY['Kapoor','Shetty','Banerjee','Malhotra','Saxena','Thakur'])[1 + ((g / 10) % 6)],
       (ARRAY['Engineering','Finance','Sales','Operations','HR','Support'])[1 + (g % 6)],
       CASE WHEN ci < 4 THEN 'South Asia' WHEN ci < 7 THEN 'Southeast Asia'
            WHEN ci < 9 THEN 'Middle East' ELSE 'Europe' END,
       (ARRAY['India','Bangladesh','Nepal','Sri Lanka','Vietnam','Thailand','Singapore','UAE','Saudi Arabia','Germany'])[ci + 1],
       (ARRAY['Associate','Executive','Manager','Senior Manager'])[1 + (g % 4)],
       DATE '2024-01-01' + ((g * 3) % 900)
FROM g;

CREATE TABLE lms.enrollments (
    enrollment_id  integer PRIMARY KEY,
    learner_id     integer REFERENCES lms.learners(learner_id),
    course_id      integer REFERENCES lms.courses(course_id),
    learner_name   text NOT NULL,
    department     text NOT NULL,
    region         text NOT NULL,
    course_title   text NOT NULL,
    category       text NOT NULL,
    level          text NOT NULL,
    enrolled_date  date NOT NULL,
    completed_date date,
    status         text NOT NULL,         -- Completed / In progress / Dropped / Not started
    progress_pct   integer NOT NULL,
    quiz_score     integer,
    passed         boolean NOT NULL,
    certified      boolean NOT NULL,
    hours_spent    numeric(6, 1) NOT NULL
);

INSERT INTO lms.enrollments
WITH g AS (SELECT gs AS g, (gs * 41) % 100 AS roll, 1 + (gs % 600) AS lrn, 1 + (gs % 40) AS crs,
                  DATE '2025-01-01' + ((gs * 5) % 650) AS enrolled
           FROM generate_series(1, 4200) gs)
SELECT g, l.learner_id, c.course_id, l.learner_name, l.department, l.region,
       c.course_title, c.category, c.level,
       enrolled,
       CASE WHEN roll < 62 THEN enrolled + (7 + (g % 50)) END,
       CASE WHEN roll < 62 THEN 'Completed' WHEN roll < 84 THEN 'In progress'
            WHEN roll < 93 THEN 'Dropped' ELSE 'Not started' END,
       CASE WHEN roll < 62 THEN 100 WHEN roll < 84 THEN 20 + ((g * 7) % 70)
            WHEN roll < 93 THEN 5 + ((g * 3) % 40) ELSE 0 END,
       CASE WHEN roll < 62 THEN 45 + ((g * 13) % 55) END,
       roll < 62 AND (45 + ((g * 13) % 55)) >= 60,
       roll < 62 AND c.gives_certificate AND (45 + ((g * 13) % 55)) >= 60,
       round((c.duration_hours * (CASE WHEN roll < 62 THEN 1.0 WHEN roll < 84 THEN 0.5 ELSE 0.1 END))::numeric, 1)
FROM g JOIN lms.learners l ON l.learner_id = g.lrn JOIN lms.courses c ON c.course_id = g.crs;


-- =====================================================================================
-- Account — payables, receivables and the cash that came in
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS account;
DROP TABLE IF EXISTS account.cash_collections CASCADE;
DROP TABLE IF EXISTS account.ar_invoices CASCADE;
DROP TABLE IF EXISTS account.ap_invoices CASCADE;
DROP TABLE IF EXISTS account.vendors CASCADE;

CREATE TABLE account.vendors (
    vendor_id    integer PRIMARY KEY,
    vendor_name  text NOT NULL,
    vendor_type  text NOT NULL,
    country      text NOT NULL,
    region       text NOT NULL,
    payment_terms_days integer NOT NULL
);

INSERT INTO account.vendors
SELECT g,
       (ARRAY['Siemens','ABB India','Voltas','Blue Star','Kirloskar','Thermax','Cummins','Schneider',
              'Honeywell','Emerson','Bosch Rexroth','Grundfos','Atlas Copco','SKF India','Timken'])[1 + (g % 15)]
         || ' ' || (ARRAY['Engineering','Services','Supplies','Consulting'])[1 + ((g / 15) % 4)],
       (ARRAY['Subcontractor','Equipment','Professional services','Facilities','Travel'])[1 + (g % 5)],
       (ARRAY['India','India','India','Germany','Singapore','UAE'])[1 + (g % 6)],
       CASE WHEN g % 6 < 3 THEN 'India' ELSE 'Other Asia' END,
       (ARRAY[30, 45, 60, 90])[1 + (g % 4)]
FROM generate_series(1, 60) g;

CREATE TABLE account.ap_invoices (
    invoice_id       integer PRIMARY KEY,
    invoice_no       text NOT NULL,
    vendor_id        integer REFERENCES account.vendors(vendor_id),
    vendor_name      text NOT NULL,
    project          text NOT NULL,
    department       text NOT NULL,       -- PMU1 / PMU2 / GDC / BD / Admin
    expenditure_head text NOT NULL,
    region           text NOT NULL,       -- India / Other Asia
    invoice_date     date NOT NULL,
    due_date         date NOT NULL,
    amount_payable   numeric(14, 2) NOT NULL,
    amount_paid      numeric(14, 2) NOT NULL,
    amount_pending   numeric(14, 2) NOT NULL,
    status           text NOT NULL,       -- Paid / Pending / Part Payment
    days_pending     integer NOT NULL,
    ageing_bucket    text NOT NULL        -- 0-30 / 31-60 / 61-90 / 91-180 / 180+
);

INSERT INTO account.ap_invoices
WITH g AS (SELECT gs AS g, (gs * 43) % 100 AS roll, 1 + (gs % 60) AS vnd,
                  DATE '2025-06-01' + ((gs * 3) % 480) AS inv_date,
                  (400000 + ((gs * 977) % 9600000))::numeric(14, 2) AS amount
           FROM generate_series(1, 168) gs),
     s AS (SELECT g.*, v.vendor_name, v.region, v.payment_terms_days,
                  CASE WHEN roll < 72 THEN 'Paid' WHEN roll < 96 THEN 'Pending' ELSE 'Part Payment' END AS status,
                  GREATEST(0, DATE '2026-10-31' - (g.inv_date + v.payment_terms_days)) AS overdue_days
           FROM g JOIN account.vendors v ON v.vendor_id = g.vnd)
SELECT g, 'AP/' || to_char(inv_date, 'YYYYMM') || '/' || lpad(g::text, 4, '0'),
       vnd, vendor_name,
       (ARRAY['Ganga Rejuvenation','Metro Rail Phase 3','Smart City Indore','Water Supply Dhaka',
              'Highway NH-48','Power Grid East','Port Modernisation','Irrigation Vidarbha',
              'Urban Transport Hanoi','Sanitation Colombo'])[1 + (g % 10)],
       (ARRAY['PMU1','PMU2','GDC','BD','Admin'])[1 + (g % 5)],
       (ARRAY['Subcontract works','Equipment hire','Professional fees','Travel & conveyance',
              'Office running','Insurance','Software licences'])[1 + (g % 7)],
       region, inv_date, inv_date + payment_terms_days, amount,
       CASE status WHEN 'Paid' THEN amount WHEN 'Part Payment' THEN round(amount * 0.4, 2) ELSE 0 END,
       CASE status WHEN 'Paid' THEN 0 WHEN 'Part Payment' THEN round(amount * 0.6, 2) ELSE amount END,
       status,
       CASE status WHEN 'Paid' THEN 0 ELSE overdue_days END,
       CASE WHEN status = 'Paid' THEN '0-30'
            WHEN overdue_days <= 30 THEN '0-30' WHEN overdue_days <= 60 THEN '31-60'
            WHEN overdue_days <= 90 THEN '61-90' WHEN overdue_days <= 180 THEN '91-180' ELSE '180+' END
FROM s;

CREATE TABLE account.ar_invoices (
    invoice_id      integer PRIMARY KEY,
    invoice_no      text NOT NULL,
    customer_name   text NOT NULL,
    project         text NOT NULL,
    pmu             text NOT NULL,
    region          text NOT NULL,
    funding_agency  text NOT NULL,
    invoice_date    date NOT NULL,
    due_date        date NOT NULL,
    amount_invoiced numeric(14, 2) NOT NULL,
    amount_received numeric(14, 2) NOT NULL,
    amount_outstanding numeric(14, 2) NOT NULL,
    ageing_days     integer NOT NULL,
    ageing_bucket   text NOT NULL,        -- 0-30 / 31-60 / 61-90 / 91-180 / 180+
    status          text NOT NULL         -- Settled / Part settled / Open
);

INSERT INTO account.ar_invoices
WITH g AS (SELECT gs AS g, (gs * 47) % 100 AS roll,
                  DATE '2025-04-01' + ((gs * 3) % 540) AS inv_date,
                  (900000 + ((gs * 1361) % 14000000))::numeric(14, 2) AS amount
           FROM generate_series(1, 240) gs),
     s AS (SELECT g.*,
                  CASE WHEN roll < 34 THEN 'Settled' WHEN roll < 56 THEN 'Part settled' ELSE 'Open' END AS status,
                  GREATEST(0, DATE '2026-10-31' - (inv_date + 45)) AS ageing
           FROM g)
SELECT g, 'AR/' || to_char(inv_date, 'YYYYMM') || '/' || lpad(g::text, 4, '0'),
       (ARRAY['Ministry of Jal Shakti','Dhaka WASA','Colombo Municipal','Hanoi Transport Authority',
              'NHAI','Power Grid Corporation','Indore Smart City','Maharashtra Irrigation'])[1 + (g % 8)],
       (ARRAY['Ganga Rejuvenation','Metro Rail Phase 3','Smart City Indore','Water Supply Dhaka',
              'Highway NH-48','Power Grid East','Port Modernisation','Irrigation Vidarbha',
              'Urban Transport Hanoi','Sanitation Colombo'])[1 + (g % 10)],
       (ARRAY['PMU-1','PMU-2','GDC','HO'])[1 + (g % 4)],
       CASE WHEN g % 6 < 3 THEN 'India' ELSE 'Other Asia' END,
       (ARRAY['ADB','World Bank','JICA','AFD','KfW','GIZ','GOI','NDB','Private'])[1 + (g % 9)],
       inv_date, inv_date + 45, amount,
       CASE status WHEN 'Settled' THEN amount WHEN 'Part settled' THEN round(amount * 0.55, 2) ELSE 0 END,
       CASE status WHEN 'Settled' THEN 0 WHEN 'Part settled' THEN round(amount * 0.45, 2) ELSE amount END,
       CASE status WHEN 'Settled' THEN 0 ELSE ageing END,
       CASE WHEN status = 'Settled' THEN '0-30'
            WHEN ageing <= 30 THEN '0-30' WHEN ageing <= 60 THEN '31-60'
            WHEN ageing <= 90 THEN '61-90' WHEN ageing <= 180 THEN '91-180' ELSE '180+' END,
       status
FROM s;

CREATE TABLE account.cash_collections (
    collection_id  integer PRIMARY KEY,
    posting_date   date NOT NULL,
    account_name   text NOT NULL,
    account_code   text NOT NULL,
    department     text NOT NULL,
    project        text NOT NULL,
    region         text NOT NULL,
    payment_method text NOT NULL,
    debit          numeric(14, 2) NOT NULL,
    credit         numeric(14, 2) NOT NULL,
    amount_collected numeric(14, 2) NOT NULL
);

INSERT INTO account.cash_collections
WITH g AS (SELECT gs AS g, DATE '2025-01-01' + ((gs * 2) % 668) AS posted,
                  (150000 + ((gs * 613) % 5200000))::numeric(14, 2) AS amount
           FROM generate_series(1, 600) gs)
SELECT g, posted,
       (ARRAY['Indian Oversea Bank A/C 290','Debtors','Cash with Finance','Mobilization advances',
              'HDFC Current A/C 118','Retention money'])[1 + (g % 6)],
       (ARRAY['10041001','10041002','10051000','10061200','10041003','10071100'])[1 + (g % 6)],
       (ARRAY['PMU-1','PMU-2','GDC','HO'])[1 + (g % 4)],
       (ARRAY['Ganga Rejuvenation','Metro Rail Phase 3','Smart City Indore','Water Supply Dhaka',
              'Highway NH-48','Power Grid East'])[1 + (g % 6)],
       CASE WHEN g % 6 < 3 THEN 'India' ELSE 'Other Asia' END,
       (ARRAY['Bank transfer','Cheque','RTGS','NEFT'])[1 + (g % 4)],
       amount, 0::numeric(14, 2), amount
FROM g;


-- =====================================================================================
-- Sales — orders, what was on them, and the targets they were measured against
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS sales;
DROP TABLE IF EXISTS sales.order_lines CASCADE;
DROP TABLE IF EXISTS sales.sales_orders CASCADE;
DROP TABLE IF EXISTS sales.targets CASCADE;
DROP TABLE IF EXISTS sales.products CASCADE;

CREATE TABLE sales.products (
    product_id   integer PRIMARY KEY,
    product_name text NOT NULL,
    category     text NOT NULL,
    unit_price   numeric(12, 2) NOT NULL,
    unit_cost    numeric(12, 2) NOT NULL
);

INSERT INTO sales.products
SELECT g,
       (ARRAY['Implementation','Licence','Support plan','Training','Hardware kit','Cloud hosting',
              'Data migration','Custom module','Audit service','Managed service'])[1 + (g % 10)]
         || ' ' || (ARRAY['Standard','Professional','Enterprise','Premium'])[1 + ((g / 10) % 4)],
       (ARRAY['Consulting','Software','Hardware','Support'])[1 + (g % 4)],
       (24000 + ((g * 311) % 420000))::numeric(12, 2),
       round(((24000 + ((g * 311) % 420000)) * (0.52 + ((g % 7) / 50.0)))::numeric, 2)
FROM generate_series(1, 36) g;

CREATE TABLE sales.sales_orders (
    order_id        integer PRIMARY KEY,
    order_no        text NOT NULL,
    customer_id     integer,
    customer_name   text NOT NULL,
    sales_rep       text NOT NULL,
    department      text NOT NULL,
    channel         text NOT NULL,        -- Direct / Partner / Online / Tender
    funding_agency  text NOT NULL,
    region          text NOT NULL,
    country         text NOT NULL,
    order_date      date NOT NULL,
    delivery_date   date,
    contract_end    date,
    status          text NOT NULL,        -- Draft / Confirmed / Invoiced / Delivered / Cancelled
    contract_value  numeric(14, 2) NOT NULL,
    invoiced_value  numeric(14, 2) NOT NULL,
    order_stock     numeric(14, 2) NOT NULL,   -- contract value not yet invoiced
    margin_pct      numeric(5, 2) NOT NULL
);

INSERT INTO sales.sales_orders
WITH g AS (SELECT gs AS g, (gs * 59) % 100 AS roll, 1 + (gs % 120) AS cust,
                  DATE '2025-01-01' + ((gs * 3) % 668) AS ordered,
                  (300000 + ((gs * 1117) % 11000000))::numeric(14, 2) AS value
           FROM generate_series(1, 900) gs),
     s AS (SELECT g.*, c.customer_name, c.country, c.region, c.account_owner,
                  CASE WHEN roll < 46 THEN 'Confirmed' WHEN roll < 62 THEN 'Invoiced'
                       WHEN roll < 88 THEN 'Delivered' WHEN roll < 94 THEN 'Cancelled' ELSE 'Draft' END AS status
           FROM g JOIN crm.customers c ON c.customer_id = g.cust)
SELECT g, 'SO/' || to_char(ordered, 'YYYY') || '/' || lpad(g::text, 5, '0'),
       cust, customer_name, account_owner,
       (ARRAY['PMU-1','PMU-2','GDC','HO'])[1 + (g % 4)],
       (ARRAY['Direct','Partner','Online','Tender'])[1 + (g % 4)],
       (ARRAY['ADB','World Bank','JICA','AFD','KfW','GIZ','GOI','NDB','Private'])[1 + (g % 9)],
       region, country,
       ordered,
       CASE WHEN status IN ('Delivered','Invoiced') THEN ordered + (20 + (g % 90)) END,
       ordered + (180 + (g % 540)),
       status, value,
       CASE status WHEN 'Invoiced' THEN value WHEN 'Delivered' THEN round(value * 0.7, 2)
                   WHEN 'Confirmed' THEN round(value * 0.3, 2) ELSE 0 END,
       value - CASE status WHEN 'Invoiced' THEN value WHEN 'Delivered' THEN round(value * 0.7, 2)
                           WHEN 'Confirmed' THEN round(value * 0.3, 2) ELSE 0 END,
       round((28 + ((g * 7) % 24))::numeric, 2)
FROM s;

CREATE TABLE sales.order_lines (
    line_id      integer PRIMARY KEY,
    order_id     integer REFERENCES sales.sales_orders(order_id),
    order_no     text NOT NULL,
    product_id   integer REFERENCES sales.products(product_id),
    product_name text NOT NULL,
    category     text NOT NULL,
    region       text NOT NULL,
    order_date   date NOT NULL,
    quantity     integer NOT NULL,
    unit_price   numeric(12, 2) NOT NULL,
    revenue      numeric(14, 2) NOT NULL,
    cost         numeric(14, 2) NOT NULL,
    margin       numeric(14, 2) NOT NULL
);

INSERT INTO sales.order_lines
WITH g AS (SELECT gs AS g, 1 + (gs % 900) AS ord, 1 + ((gs * 7) % 36) AS prd, 1 + (gs % 6) AS qty
           FROM generate_series(1, 2800) gs)
SELECT g, o.order_id, o.order_no, p.product_id, p.product_name, p.category, o.region, o.order_date,
       qty, p.unit_price,
       round((qty * p.unit_price)::numeric, 2),
       round((qty * p.unit_cost)::numeric, 2),
       round((qty * (p.unit_price - p.unit_cost))::numeric, 2)
FROM g JOIN sales.sales_orders o ON o.order_id = g.ord JOIN sales.products p ON p.product_id = g.prd;

CREATE TABLE sales.targets (
    target_id     integer PRIMARY KEY,
    period_month  date NOT NULL,          -- first day of the month
    region        text NOT NULL,
    sales_rep     text NOT NULL,
    target_amount numeric(14, 2) NOT NULL
);

INSERT INTO sales.targets
WITH m AS (SELECT generate_series(DATE '2025-01-01', DATE '2026-10-01', INTERVAL '1 month')::date AS period_month),
     r AS (SELECT unnest(ARRAY['South Asia','Southeast Asia','Middle East','Europe']) AS region,
                  unnest(ARRAY['Priya Sharma','Rahul Kumar','Amit Desai','Neha Gupta']) AS sales_rep)
SELECT row_number() OVER (ORDER BY m.period_month, r.region)::int,
       m.period_month, r.region, r.sales_rep,
       (18000000 + (extract(month FROM m.period_month)::int * 400000)
                 + (length(r.region) * 250000))::numeric(14, 2)
FROM m CROSS JOIN r;


-- =====================================================================================
-- Read-only indexes the dashboards lean on
-- =====================================================================================

CREATE INDEX ON crm.opportunities (close_date);
CREATE INDEX ON crm.leads (created_date);
CREATE INDEX ON helpdesk.tickets (created_date);
CREATE INDEX ON lms.enrollments (enrolled_date);
CREATE INDEX ON account.ap_invoices (invoice_date);
CREATE INDEX ON account.ar_invoices (invoice_date);
CREATE INDEX ON account.cash_collections (posting_date);
CREATE INDEX ON sales.sales_orders (order_date);
CREATE INDEX ON sales.order_lines (order_date);
