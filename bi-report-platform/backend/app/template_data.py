"""
Template definitions shipped with the app.

BUILTIN_TEMPLATES are created when the API starts (see routers/templates.py).
SAMPLE_TEMPLATES are demo data created by `python -m app.seed`, owned by the demo accounts.
Sample questions only use words the phase 1 query engine understands (revenue, sales,
region, product, Q1 2024, Q4 2023, gross), so every sample builds a working report.
"""

BUILTIN_TEMPLATES = [
    {"name": "Sales performance", "description": "Revenue trend, regions, top products", "color": "#00B4D8",
     "prompt": "Show monthly revenue by region for Q1 2024 and the top 5 products"},
    {"name": "Quarter over quarter", "description": "Q1 2024 net revenue against the previous quarter", "color": "#0D3B66",
     "prompt": "Net revenue by region for Q1 2024 compared with the previous quarter",
     "layout": {"sections": ["kpis", "revenue", "insights"]}},
    {"name": "Gross revenue by region", "description": "Revenue before discounts and refunds", "color": "#F5A623",
     "prompt": "Gross revenue by region for Q1 2024",
     "layout": {"chart": "stacked", "palette": "warm"}},
    {"name": "Product mix", "description": "Which products bring in the most revenue", "color": "#7A8BA3",
     "prompt": "Revenue by product for Q1 2024",
     "layout": {"sections": ["products", "kpis", "revenue"]}},
]

# Built-ins from earlier versions that the phase 1 query engine can't answer,
# mapped to the built-in that replaces them in existing databases.
REPLACED_BUILTINS = {
    "P&L summary": "Quarter over quarter",
    "Budget vs actual": "Gross revenue by region",
    "AR aging": "Product mix",
}

# owner is the demo account email; "shared" templates need a manager as owner.
SAMPLE_TEMPLATES = [
    {"owner": "manager@example.com", "visibility": "shared",
     "name": "Quarterly sales review", "description": "Full review: headline numbers, regions, products, insights",
     "color": "#0D3B66", "prompt": "Show monthly net revenue by region for Q1 2024 and the top 5 products",
     "layout": {"sections": ["kpis", "revenue", "products", "insights"], "chart": "grouped", "palette": "ocean"}},
    {"owner": "manager@example.com", "visibility": "shared",
     "name": "Executive snapshot", "description": "Just the headline numbers and what stands out",
     "color": "#2A9D8F", "prompt": "Net revenue by region for Q1 2024",
     "layout": {"sections": ["kpis", "insights"], "fmt": "short"}},
    {"owner": "manager@example.com", "visibility": "shared",
     "name": "Holiday quarter (gross)", "description": "Q4 2023 gross revenue, stacked by region",
     "color": "#A63D40", "prompt": "Gross revenue by region for Q4 2023",
     "layout": {"sections": ["revenue", "kpis", "insights"], "chart": "stacked", "palette": "warm",
                "fmt": "full", "showValues": True}},
    {"owner": "manager@example.com", "visibility": "shared",
     "name": "Product leaderboard", "description": "Top 3 products with the headline numbers",
     "color": "#6D597A", "prompt": "Top products by revenue for Q1 2024",
     "layout": {"sections": ["products", "kpis"], "palette": "slate", "topN": 3}},
    {"owner": "user@example.com", "visibility": "private",
     "name": "My regional table", "description": "Exact figures per region and month, as a table",
     "color": "#1E7F4F", "prompt": "Sales by region for Q1 2024",
     "layout": {"sections": ["revenue", "kpis"], "chart": "table", "fmt": "full"}},
]
