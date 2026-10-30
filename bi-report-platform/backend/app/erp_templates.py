"""
Built-in dashboard templates for ERP data on a PostgreSQL connection.

Each one builds a whole dashboard of ready-written SQL from a single click, so nothing depends on
an AI model — the same arrangement as the OpenPages templates, against the CRM, Helpdesk, LMS,
Account and Sales schemas that `python -m app.erp_demo` creates.

They are modelled on the production ERP reports in frontend/Template/ERP_Template: the same
headline numbers, the same cuts of the data, the same registers at the bottom. Charts whose tables
aren't shared on the connection are left out when the dashboard is built, and the person is told
which, so a connection holding only some of the schemas still gets a dashboard.

The SQL is plain PostgreSQL and goes through the same read-only check as everything else.
"""

# Schemas these templates read. A connection that shares none of a template's tables gets nothing
# from it, which the build endpoint reports as "skipped".
CRM, HD, LMS, ACC, SLS = "crm", "helpdesk", "lms", "account", "sales"

# Bar charts whose labels are long enough to read better down the side.
LONG_LABELS = {"Top sales reps by won value", "Tickets by category", "Top courses by enrolment",
               "Top vendors by outstanding liability", "Top expense heads by pending amount",
               "Top products by revenue", "Top projects by open receivable", "Skills by completion rate",
               "Top agents by satisfaction"}


def _kpi(title: str, sql: str, size: str = "quarter", style: dict | None = None, question: str = "") -> dict:
    w = {"title": title, "question": question or title, "sql": sql, "size": size,
         "chart": {"type": "kpi", "x": "", "y": []}}
    if style:
        w["style"] = style
    return w


def _chart(title: str, sql: str, chart: str, x: str, y: list[str], size: str = "half",
           style: dict | None = None, question: str = "") -> dict:
    w = {"title": title, "question": question or title, "sql": sql, "size": size,
         "chart": {"type": chart, "x": x, "y": y}}
    merged = dict(style or {})
    if title in LONG_LABELS:
        merged = {"horizontal": True, "showValues": True, **merged}
    if merged:
        w["style"] = merged
    return w


def _table(title: str, sql: str, size: str = "full", question: str = "") -> dict:
    return {"title": title, "question": question or title, "sql": sql, "size": size,
            "chart": {"type": "table", "x": "", "y": []}}


def _heading(title: str, text: str = "") -> dict:
    return {"kind": "text", "title": title, "text": text, "question": "", "sql": "", "size": "full",
            "chart": {"type": "table", "x": "", "y": []}}


def _filter(label: str, table: str, field: str, kind: str = "category") -> dict:
    return {"label": label, "table": table, "field": field, "kind": kind}


# A KPI tile reads the first number of the first row, so each one is a single aggregate.
ERP_TEMPLATES = [
    {
        "name": "ERP: CRM pipeline",
        "description": "Pipeline value, win rate, lead sources and the opportunities still open",
        "color": "#00D4AA",
        "category": "ERP",
        "prompt": "How is the sales pipeline doing, and which opportunities are still open?",
        "widgets": [
            _kpi("Pipeline value", f"SELECT SUM(expected_value) AS pipeline_value FROM {CRM}.opportunities "
                                   "WHERE NOT is_closed"),
            _kpi("Active leads", f"SELECT COUNT(*) AS active_leads FROM {CRM}.leads "
                                 "WHERE status IN ('New', 'Qualified')"),
            _kpi("Win rate %", "SELECT ROUND(100.0 * SUM(CASE WHEN is_won THEN 1 ELSE 0 END) / "
                               "NULLIF(SUM(CASE WHEN is_closed THEN 1 ELSE 0 END), 0), 1) AS win_rate_pct "
                               f"FROM {CRM}.opportunities"),
            _kpi("Average deal size", f"SELECT ROUND(AVG(expected_value), 0) AS avg_deal_size FROM {CRM}.opportunities "
                                      "WHERE is_won"),
            _heading("Pipeline", "Where the open work sits, and how leads turn into opportunities."),
            _chart("Opportunities by stage",
                   f"SELECT stage, COUNT(*) AS opportunities, SUM(expected_value) AS value "
                   f"FROM {CRM}.opportunities GROUP BY stage ORDER BY value DESC",
                   "bar", "stage", ["opportunities"], size="half"),
            _chart("Leads by status",
                   f"SELECT status, COUNT(*) AS leads FROM {CRM}.leads GROUP BY status ORDER BY leads DESC",
                   "bar", "status", ["leads"], size="half"),
            _chart("Won value by month",
                   "SELECT to_char(date_trunc('month', close_date), 'YYYY-MM') AS month, "
                   f"SUM(expected_value) AS won_value FROM {CRM}.opportunities WHERE is_won "
                   "GROUP BY 1 ORDER BY 1",
                   "line", "month", ["won_value"], size="full"),
            _chart("Leads by source",
                   f"SELECT source, COUNT(*) AS leads FROM {CRM}.leads GROUP BY source ORDER BY leads DESC",
                   "pie", "source", ["leads"], size="third"),
            _chart("Pipeline by region",
                   f"SELECT region, SUM(expected_value) AS pipeline_value FROM {CRM}.opportunities "
                   "WHERE NOT is_closed GROUP BY region ORDER BY pipeline_value DESC",
                   "bar", "region", ["pipeline_value"], size="third"),
            _chart("Why deals were lost",
                   f"SELECT lost_reason, COUNT(*) AS deals FROM {CRM}.opportunities "
                   "WHERE lost_reason IS NOT NULL GROUP BY lost_reason ORDER BY deals DESC",
                   "pie", "lost_reason", ["deals"], size="third"),
            _chart("Top sales reps by won value",
                   f"SELECT sales_rep, SUM(expected_value) AS won_value FROM {CRM}.opportunities "
                   "WHERE is_won GROUP BY sales_rep ORDER BY won_value DESC",
                   "bar", "sales_rep", ["won_value"], size="half"),
            _chart("Won against lost by region",
                   "SELECT region, SUM(CASE WHEN is_won THEN expected_value ELSE 0 END) AS won, "
                   "SUM(CASE WHEN is_closed AND NOT is_won THEN expected_value ELSE 0 END) AS lost "
                   f"FROM {CRM}.opportunities GROUP BY region ORDER BY won DESC",
                   "bar", "region", ["won", "lost"], size="half", style={"stackMode": "stacked"}),
            _heading("Still open", "Everything that hasn't closed yet, largest first."),
            _table("Open opportunities",
                   "SELECT opportunity, customer_name, sales_rep, stage, probability, "
                   f"expected_value, close_date FROM {CRM}.opportunities WHERE NOT is_closed "
                   "ORDER BY expected_value DESC"),
        ],
        "filters": [_filter("Region", f"{CRM}.opportunities", "region"),
                    _filter("Sales rep", f"{CRM}.opportunities", "sales_rep")],
    },
    {
        "name": "ERP: Helpdesk operations",
        "description": "Ticket load, SLA compliance, resolution times, satisfaction and the open queue",
        "color": "#DC2626",
        "category": "ERP",
        "prompt": "How is support doing against SLA, and what is still open?",
        "widgets": [
            _kpi("Open tickets", f"SELECT COUNT(*) AS open_tickets FROM {HD}.tickets "
                                 "WHERE status IN ('Open', 'In Progress', 'Waiting')"),
            _kpi("Resolved tickets", f"SELECT COUNT(*) AS resolved FROM {HD}.tickets "
                                     "WHERE status IN ('Resolved', 'Closed')"),
            _kpi("SLA compliance %", "SELECT ROUND(100.0 * SUM(CASE WHEN sla_met THEN 1 ELSE 0 END) / "
                                     f"NULLIF(COUNT(*), 0), 1) AS sla_pct FROM {HD}.tickets",
                 style={"goodWhen": "up"}),
            _kpi("Average resolution (hours)",
                 f"SELECT ROUND(AVG(resolution_hours), 1) AS avg_hours FROM {HD}.tickets "
                 "WHERE resolution_hours IS NOT NULL", style={"goodWhen": "down"}),
            _heading("Load and compliance", "What is coming in, and whether it is answered in time."),
            _chart("Tickets by priority",
                   f"SELECT priority, COUNT(*) AS tickets FROM {HD}.tickets GROUP BY priority "
                   "ORDER BY tickets DESC",
                   "pie", "priority", ["tickets"], size="third"),
            _chart("Tickets by status",
                   f"SELECT status, COUNT(*) AS tickets FROM {HD}.tickets GROUP BY status ORDER BY tickets DESC",
                   "donut", "status", ["tickets"], size="third"),
            _chart("Tickets by channel",
                   f"SELECT channel, COUNT(*) AS tickets FROM {HD}.tickets GROUP BY channel ORDER BY tickets DESC",
                   "pie", "channel", ["tickets"], size="third"),
            _chart("Opened against resolved by month",
                   "SELECT to_char(date_trunc('month', created_date), 'YYYY-MM') AS month, "
                   "COUNT(*) AS opened, "
                   "SUM(CASE WHEN status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) AS resolved "
                   f"FROM {HD}.tickets GROUP BY 1 ORDER BY 1",
                   "line", "month", ["opened", "resolved"], size="full"),
            _chart("Tickets by category",
                   f"SELECT category, COUNT(*) AS tickets FROM {HD}.tickets GROUP BY category "
                   "ORDER BY tickets DESC",
                   "bar", "category", ["tickets"], size="half"),
            _chart("SLA met against missed by team",
                   "SELECT team, SUM(CASE WHEN sla_met THEN 1 ELSE 0 END) AS met, "
                   "SUM(CASE WHEN sla_met THEN 0 ELSE 1 END) AS missed "
                   f"FROM {HD}.tickets GROUP BY team ORDER BY missed DESC",
                   "bar", "team", ["met", "missed"], size="half", style={"stackMode": "stacked"}),
            _chart("Average resolution hours by team",
                   f"SELECT team, ROUND(AVG(resolution_hours), 1) AS avg_hours FROM {HD}.tickets "
                   "WHERE resolution_hours IS NOT NULL GROUP BY team ORDER BY avg_hours DESC",
                   "bar", "team", ["avg_hours"], size="half"),
            _chart("Top agents by satisfaction",
                   f"SELECT agent_name, ROUND(AVG(csat_rating), 2) AS csat, COUNT(*) AS rated "
                   f"FROM {HD}.tickets WHERE csat_rating IS NOT NULL GROUP BY agent_name "
                   "HAVING COUNT(*) >= 20 ORDER BY csat DESC",
                   "bar", "agent_name", ["csat"], size="half"),
            _heading("The queue", "Open tickets, most urgent and oldest first."),
            _table("Open ticket queue",
                   "SELECT ticket_ref, subject, customer_name, priority, status, agent_name, "
                   f"age_days, first_response_hours FROM {HD}.tickets "
                   "WHERE status IN ('Open', 'In Progress', 'Waiting') "
                   "ORDER BY CASE priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 "
                   "WHEN 'Medium' THEN 3 ELSE 4 END, age_days DESC"),
        ],
        "filters": [_filter("Team", f"{HD}.tickets", "team"),
                    _filter("Priority", f"{HD}.tickets", "priority")],
    },
    {
        "name": "ERP: Learning and development",
        "description": "Enrolments, completion rates, quiz scores, certifications and the top courses",
        "color": "#8B5CF6",
        "category": "ERP",
        "prompt": "How much training is being completed, and which courses work?",
        "widgets": [
            _kpi("Active learners", f"SELECT COUNT(DISTINCT learner_id) AS learners FROM {LMS}.enrollments "
                                    "WHERE status IN ('Completed', 'In progress')"),
            _kpi("Completions", f"SELECT COUNT(*) AS completions FROM {LMS}.enrollments WHERE status = 'Completed'"),
            _kpi("Completion rate %", "SELECT ROUND(100.0 * SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) / "
                                      f"NULLIF(COUNT(*), 0), 1) AS completion_pct FROM {LMS}.enrollments"),
            _kpi("Certifications issued", f"SELECT COUNT(*) AS certifications FROM {LMS}.enrollments WHERE certified"),
            _heading("Take-up", "Who is learning, and how far they get."),
            _chart("Enrolments by month",
                   "SELECT to_char(date_trunc('month', enrolled_date), 'YYYY-MM') AS month, "
                   "COUNT(*) AS enrolments, "
                   "SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completions "
                   f"FROM {LMS}.enrollments GROUP BY 1 ORDER BY 1",
                   "area", "month", ["enrolments", "completions"], size="full"),
            _chart("Enrolments by status",
                   f"SELECT status, COUNT(*) AS enrolments FROM {LMS}.enrollments GROUP BY status "
                   "ORDER BY enrolments DESC",
                   "donut", "status", ["enrolments"], size="third"),
            _chart("Learners by region",
                   f"SELECT region, COUNT(DISTINCT learner_id) AS learners FROM {LMS}.enrollments "
                   "GROUP BY region ORDER BY learners DESC",
                   "pie", "region", ["learners"], size="third"),
            _chart("Enrolments by course category",
                   f"SELECT category, COUNT(*) AS enrolments FROM {LMS}.enrollments GROUP BY category "
                   "ORDER BY enrolments DESC",
                   "bar", "category", ["enrolments"], size="third"),
            _chart("Top courses by enrolment",
                   f"SELECT course_title, COUNT(*) AS enrolments FROM {LMS}.enrollments "
                   "GROUP BY course_title ORDER BY enrolments DESC LIMIT 12",
                   "bar", "course_title", ["enrolments"], size="half"),
            _chart("Completion rate by department",
                   "SELECT department, ROUND(100.0 * SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) / "
                   f"NULLIF(COUNT(*), 0), 1) AS completion_pct FROM {LMS}.enrollments "
                   "GROUP BY department ORDER BY completion_pct DESC",
                   "bar", "department", ["completion_pct"], size="half"),
            _chart("Average quiz score by category",
                   f"SELECT category, ROUND(AVG(quiz_score), 1) AS avg_score FROM {LMS}.enrollments "
                   "WHERE quiz_score IS NOT NULL GROUP BY category ORDER BY avg_score DESC",
                   "bar", "category", ["avg_score"], size="half"),
            _chart("Hours spent by level",
                   f"SELECT level, ROUND(SUM(hours_spent), 0) AS hours FROM {LMS}.enrollments "
                   "GROUP BY level ORDER BY hours DESC",
                   "bar", "level", ["hours"], size="half"),
            _heading("Course by course", "Enrolment, completion and score for every course."),
            _table("Courses — enrolment and completion",
                   "SELECT course_title, category, level, COUNT(*) AS enrolled, "
                   "SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed, "
                   "ROUND(AVG(quiz_score), 1) AS avg_score, "
                   f"SUM(CASE WHEN certified THEN 1 ELSE 0 END) AS certified FROM {LMS}.enrollments "
                   "GROUP BY course_title, category, level ORDER BY enrolled DESC"),
        ],
        "filters": [_filter("Department", f"{LMS}.enrollments", "department"),
                    _filter("Course category", f"{LMS}.enrollments", "category")],
    },
    {
        "name": "ERP: Payables, receivables and cash",
        "description": "AP ageing and vendors, AR ageing and projects, and the cash that came in",
        "color": "#F59E0B",
        "category": "ERP",
        "prompt": "What do we owe, what are we owed, and how much cash came in?",
        "widgets": [
            _kpi("Total payable", f"SELECT SUM(amount_payable) AS total_payable FROM {ACC}.ap_invoices"),
            _kpi("Payable outstanding", f"SELECT SUM(amount_pending) AS pending FROM {ACC}.ap_invoices",
                 style={"goodWhen": "down"}),
            _kpi("Receivable outstanding", f"SELECT SUM(amount_outstanding) AS outstanding FROM {ACC}.ar_invoices",
                 style={"goodWhen": "down"}),
            _kpi("Cash collected", f"SELECT SUM(amount_collected) AS collected FROM {ACC}.cash_collections"),
            _heading("What we owe", "Payables by age, status, vendor and department."),
            _chart("Payables by ageing bucket",
                   "SELECT ageing_bucket, SUM(amount_pending) AS pending "
                   f"FROM {ACC}.ap_invoices WHERE amount_pending > 0 GROUP BY ageing_bucket ORDER BY ageing_bucket",
                   "bar", "ageing_bucket", ["pending"], size="half"),
            _chart("Invoice payment status",
                   f"SELECT status, COUNT(*) AS invoices FROM {ACC}.ap_invoices GROUP BY status "
                   "ORDER BY invoices DESC",
                   "donut", "status", ["invoices"], size="half"),
            _chart("Top vendors by outstanding liability",
                   f"SELECT vendor_name, SUM(amount_pending) AS pending FROM {ACC}.ap_invoices "
                   "GROUP BY vendor_name HAVING SUM(amount_pending) > 0 ORDER BY pending DESC LIMIT 12",
                   "bar", "vendor_name", ["pending"], size="half"),
            _chart("Payables by department",
                   f"SELECT department, SUM(amount_pending) AS pending, SUM(amount_paid) AS paid "
                   f"FROM {ACC}.ap_invoices GROUP BY department ORDER BY pending DESC",
                   "bar", "department", ["pending", "paid"], size="half", style={"stackMode": "stacked"}),
            _chart("Top expense heads by pending amount",
                   f"SELECT expenditure_head, SUM(amount_pending) AS pending FROM {ACC}.ap_invoices "
                   "GROUP BY expenditure_head ORDER BY pending DESC",
                   "bar", "expenditure_head", ["pending"], size="half"),
            _chart("Payables by region",
                   f"SELECT region, SUM(amount_payable) AS payable FROM {ACC}.ap_invoices "
                   "GROUP BY region ORDER BY payable DESC",
                   "pie", "region", ["payable"], size="half"),
            _heading("What we are owed", "Receivables by age, agency and project."),
            _chart("Receivables by ageing bucket",
                   "SELECT ageing_bucket, SUM(amount_outstanding) AS outstanding "
                   f"FROM {ACC}.ar_invoices WHERE amount_outstanding > 0 GROUP BY ageing_bucket "
                   "ORDER BY ageing_bucket",
                   "bar", "ageing_bucket", ["outstanding"], size="half"),
            _chart("Receivables by funding agency",
                   f"SELECT funding_agency, SUM(amount_outstanding) AS outstanding FROM {ACC}.ar_invoices "
                   "GROUP BY funding_agency ORDER BY outstanding DESC",
                   "bar", "funding_agency", ["outstanding"], size="half"),
            _chart("Top projects by open receivable",
                   f"SELECT project, SUM(amount_outstanding) AS outstanding FROM {ACC}.ar_invoices "
                   "GROUP BY project ORDER BY outstanding DESC LIMIT 10",
                   "bar", "project", ["outstanding"], size="half"),
            _chart("Invoiced against received by month",
                   "SELECT to_char(date_trunc('month', invoice_date), 'YYYY-MM') AS month, "
                   "SUM(amount_invoiced) AS invoiced, SUM(amount_received) AS received "
                   f"FROM {ACC}.ar_invoices GROUP BY 1 ORDER BY 1",
                   "bar", "month", ["invoiced", "received"], size="half"),
            _heading("Cash", "What actually came in, and through which account."),
            _chart("Cash collected by month",
                   "SELECT to_char(date_trunc('month', posting_date), 'YYYY-MM') AS month, "
                   f"SUM(amount_collected) AS collected FROM {ACC}.cash_collections GROUP BY 1 ORDER BY 1",
                   "line", "month", ["collected"], size="full"),
            _chart("Cash collected by account",
                   f"SELECT account_name, SUM(amount_collected) AS collected FROM {ACC}.cash_collections "
                   "GROUP BY account_name ORDER BY collected DESC",
                   "donut", "account_name", ["collected"], size="half"),
            _chart("Cash collected by department",
                   f"SELECT department, SUM(amount_collected) AS collected FROM {ACC}.cash_collections "
                   "GROUP BY department ORDER BY collected DESC",
                   "bar", "department", ["collected"], size="half"),
            _heading("Registers", "The invoices behind the numbers above."),
            _table("Outstanding payables",
                   "SELECT invoice_no, vendor_name, project, department, expenditure_head, "
                   f"amount_payable, amount_pending, days_pending, status FROM {ACC}.ap_invoices "
                   "WHERE amount_pending > 0 ORDER BY amount_pending DESC"),
            _table("Outstanding receivables",
                   "SELECT invoice_no, customer_name, project, pmu, funding_agency, "
                   f"amount_invoiced, amount_outstanding, ageing_days, ageing_bucket FROM {ACC}.ar_invoices "
                   "WHERE amount_outstanding > 0 ORDER BY amount_outstanding DESC"),
        ],
        "filters": [_filter("Region", f"{ACC}.ap_invoices", "region"),
                    _filter("Department", f"{ACC}.ap_invoices", "department")],
    },
    {
        "name": "ERP: Sales performance",
        "description": "Orders against target, channels, products, regions and the order book",
        "color": "#2563EB",
        "category": "ERP",
        "prompt": "How are sales tracking against target, and what is still to be invoiced?",
        "widgets": [
            _kpi("Contract value", f"SELECT SUM(contract_value) AS contract_value FROM {SLS}.sales_orders "
                                   "WHERE status <> 'Cancelled'"),
            _kpi("Invoiced", f"SELECT SUM(invoiced_value) AS invoiced FROM {SLS}.sales_orders "
                             "WHERE status <> 'Cancelled'"),
            _kpi("Order stock", f"SELECT SUM(order_stock) AS order_stock FROM {SLS}.sales_orders "
                                "WHERE status <> 'Cancelled'",
                 question="Contract value that hasn't been invoiced yet"),
            _kpi("Average order value", f"SELECT ROUND(AVG(contract_value), 0) AS avg_order FROM {SLS}.sales_orders "
                                        "WHERE status <> 'Cancelled'"),
            _heading("Against target", "Monthly orders next to what was planned."),
            _chart("Orders against target by month",
                   "WITH orders AS (SELECT to_char(date_trunc('month', order_date), 'YYYY-MM') AS month, "
                   f"SUM(contract_value) AS ordered FROM {SLS}.sales_orders WHERE status <> 'Cancelled' "
                   "GROUP BY 1), "
                   "goals AS (SELECT to_char(period_month, 'YYYY-MM') AS month, SUM(target_amount) AS target "
                   f"FROM {SLS}.targets GROUP BY 1) "
                   "SELECT g.month, o.ordered, g.target FROM goals g LEFT JOIN orders o ON o.month = g.month "
                   "ORDER BY g.month",
                   "line", "month", ["ordered", "target"], size="full"),
            _chart("Sales by channel",
                   f"SELECT channel, SUM(contract_value) AS contract_value FROM {SLS}.sales_orders "
                   "WHERE status <> 'Cancelled' GROUP BY channel ORDER BY contract_value DESC",
                   "donut", "channel", ["contract_value"], size="third"),
            _chart("Orders by status",
                   f"SELECT status, COUNT(*) AS orders FROM {SLS}.sales_orders GROUP BY status "
                   "ORDER BY orders DESC",
                   "pie", "status", ["orders"], size="third"),
            _chart("Sales by region",
                   f"SELECT region, SUM(contract_value) AS contract_value FROM {SLS}.sales_orders "
                   "WHERE status <> 'Cancelled' GROUP BY region ORDER BY contract_value DESC",
                   "bar", "region", ["contract_value"], size="third"),
            _chart("Invoiced against order stock by region",
                   "SELECT region, SUM(invoiced_value) AS invoiced, SUM(order_stock) AS order_stock "
                   f"FROM {SLS}.sales_orders WHERE status <> 'Cancelled' GROUP BY region "
                   "ORDER BY invoiced DESC",
                   "bar", "region", ["invoiced", "order_stock"], size="half", style={"stackMode": "stacked"}),
            _chart("Order stock by funding agency",
                   f"SELECT funding_agency, SUM(order_stock) AS order_stock FROM {SLS}.sales_orders "
                   "WHERE status <> 'Cancelled' GROUP BY funding_agency ORDER BY order_stock DESC",
                   "bar", "funding_agency", ["order_stock"], size="half"),
            _chart("Top products by revenue",
                   f"SELECT product_name, SUM(revenue) AS revenue FROM {SLS}.order_lines "
                   "GROUP BY product_name ORDER BY revenue DESC LIMIT 12",
                   "bar", "product_name", ["revenue"], size="half"),
            _chart("Revenue by product category",
                   f"SELECT category, SUM(revenue) AS revenue, SUM(margin) AS margin FROM {SLS}.order_lines "
                   "GROUP BY category ORDER BY revenue DESC",
                   "bar", "category", ["revenue", "margin"], size="half"),
            _chart("Sales by rep",
                   f"SELECT sales_rep, SUM(contract_value) AS contract_value FROM {SLS}.sales_orders "
                   "WHERE status <> 'Cancelled' GROUP BY sales_rep ORDER BY contract_value DESC",
                   "bar", "sales_rep", ["contract_value"], size="half"),
            _chart("Revenue by month",
                   "SELECT to_char(date_trunc('month', order_date), 'YYYY-MM') AS month, "
                   f"SUM(revenue) AS revenue FROM {SLS}.order_lines GROUP BY 1 ORDER BY 1",
                   "area", "month", ["revenue"], size="half"),
            _heading("The order book", "Every live order, largest first."),
            _table("Sales orders",
                   "SELECT order_no, customer_name, sales_rep, channel, funding_agency, region, "
                   f"order_date, status, contract_value, invoiced_value, order_stock FROM {SLS}.sales_orders "
                   "WHERE status <> 'Cancelled' ORDER BY contract_value DESC"),
        ],
        "filters": [_filter("Region", f"{SLS}.sales_orders", "region"),
                    _filter("Funding agency", f"{SLS}.sales_orders", "funding_agency")],
    },
    {
        "name": "ERP: Executive overview",
        "description": "One page across CRM, Helpdesk, LMS, Sales and finance",
        "color": "#0F172A",
        "category": "ERP",
        "prompt": "Give me one page across sales, support, learning and finance",
        "widgets": [
            _kpi("Contract value", f"SELECT SUM(contract_value) AS contract_value FROM {SLS}.sales_orders "
                                   "WHERE status <> 'Cancelled'"),
            _kpi("Pipeline value", f"SELECT SUM(expected_value) AS pipeline_value FROM {CRM}.opportunities "
                                   "WHERE NOT is_closed"),
            _kpi("SLA compliance %", "SELECT ROUND(100.0 * SUM(CASE WHEN sla_met THEN 1 ELSE 0 END) / "
                                     f"NULLIF(COUNT(*), 0), 1) AS sla_pct FROM {HD}.tickets"),
            _kpi("Active learners", f"SELECT COUNT(DISTINCT learner_id) AS learners FROM {LMS}.enrollments "
                                    "WHERE status IN ('Completed', 'In progress')"),
            _heading("Sales and pipeline", "What has been sold, and what might be."),
            _chart("Contract value by month",
                   "SELECT to_char(date_trunc('month', order_date), 'YYYY-MM') AS month, "
                   f"SUM(contract_value) AS contract_value FROM {SLS}.sales_orders "
                   "WHERE status <> 'Cancelled' GROUP BY 1 ORDER BY 1",
                   "area", "month", ["contract_value"], size="half"),
            _chart("Opportunities by stage",
                   f"SELECT stage, SUM(expected_value) AS value FROM {CRM}.opportunities "
                   "GROUP BY stage ORDER BY value DESC",
                   "bar", "stage", ["value"], size="half"),
            _heading("Support and learning", "How the service and the training are holding up."),
            _chart("Tickets by month",
                   "SELECT to_char(date_trunc('month', created_date), 'YYYY-MM') AS month, "
                   "COUNT(*) AS opened, "
                   "SUM(CASE WHEN sla_met THEN 0 ELSE 1 END) AS sla_missed "
                   f"FROM {HD}.tickets GROUP BY 1 ORDER BY 1",
                   "line", "month", ["opened", "sla_missed"], size="half"),
            _chart("Completions by month",
                   "SELECT to_char(date_trunc('month', completed_date), 'YYYY-MM') AS month, "
                   f"COUNT(*) AS completions FROM {LMS}.enrollments WHERE completed_date IS NOT NULL "
                   "GROUP BY 1 ORDER BY 1",
                   "area", "month", ["completions"], size="half"),
            _heading("Money in and out", "Receivables against the cash that actually arrived."),
            _chart("Cash collected by month",
                   "SELECT to_char(date_trunc('month', posting_date), 'YYYY-MM') AS month, "
                   f"SUM(amount_collected) AS collected FROM {ACC}.cash_collections GROUP BY 1 ORDER BY 1",
                   "line", "month", ["collected"], size="half"),
            _chart("Receivables by ageing bucket",
                   "SELECT ageing_bucket, SUM(amount_outstanding) AS outstanding "
                   f"FROM {ACC}.ar_invoices WHERE amount_outstanding > 0 GROUP BY ageing_bucket "
                   "ORDER BY ageing_bucket",
                   "bar", "ageing_bucket", ["outstanding"], size="half"),
        ],
        "filters": [_filter("Region", f"{SLS}.sales_orders", "region")],
    },
]


def template_rows() -> list[dict]:
    """The templates as rows for report_templates (layout holds the dashboard)."""
    return [{"name": t["name"], "description": t["description"], "color": t["color"], "prompt": t["prompt"],
             "category": t["category"],
             "layout": {"kind": "dashboard", "source_type": "postgresql", "widgets": t["widgets"],
                        "filters": t["filters"]}}
            for t in ERP_TEMPLATES]
