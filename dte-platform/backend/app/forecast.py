"""Finance auto-forecasting: monthly revenue, expense and net cash with Holt-Winters (fallback: linear trend)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sqlalchemy import inspect, text

from .connectors import get_engine
from .db import DbConnection

METRICS = {
    "revenue": ("Monthly revenue (sales invoices, untaxed)",
                "SELECT date_trunc('month', invoice_date)::date AS period, SUM(amount_untaxed) AS value "
                "FROM invoices WHERE invoice_type='sales' AND status<>'cancelled' GROUP BY 1 ORDER BY 1"),
    "expense": ("Monthly expense (vendor bills)",
                "SELECT date_trunc('month', invoice_date)::date AS period, SUM(amount_untaxed) AS value "
                "FROM invoices WHERE invoice_type='purchase' AND status<>'cancelled' GROUP BY 1 ORDER BY 1"),
    "net_cash": ("Monthly net cash flow (receipts − payments)",
                 "SELECT date_trunc('month', payment_date)::date AS period, "
                 "SUM(CASE WHEN payment_type='inbound' THEN amount ELSE -amount END) AS value "
                 "FROM payments GROUP BY 1 ORDER BY 1"),
}


def load_series(conn: DbConnection, metric: str | None = None, sql: str | None = None) -> pd.Series:
    q = sql or METRICS[metric][1]
    with get_engine(conn).connect() as c:
        df = pd.read_sql(text(q), c)
    df["period"] = pd.to_datetime(df["period"])
    s = df.set_index("period")["value"].astype(float).asfreq("MS").fillna(0.0)
    return s


def forecast_series(s: pd.Series, horizon: int = 6) -> tuple[pd.DataFrame, str]:
    s = s.astype(float)
    idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    model_name = "linear"
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            seasonal = 12 if len(s) >= 24 else None
            m = ExponentialSmoothing(s, trend="add", seasonal="add" if seasonal else None,
                                     seasonal_periods=seasonal, damped_trend=True).fit(optimized=True)
            pred = m.forecast(horizon).values
            resid = (s - m.fittedvalues).std()
            model_name = "holt_winters" + ("_seasonal" if seasonal else "")
    except Exception:  # noqa: BLE001
        x = np.arange(len(s))
        a, b = np.polyfit(x, s.values, 1)
        pred = a * np.arange(len(s), len(s) + horizon) + b
        resid = (s.values - (a * x + b)).std()
    width = 1.96 * resid * np.sqrt(np.arange(1, horizon + 1))
    out = pd.DataFrame({"period": idx, "value": pred, "lower": pred - width, "upper": pred + width})
    return out, model_name


def run_forecast(conn: DbConnection, metric: str, horizon: int = 6, sql: str | None = None, store: bool = True) -> dict:
    s = load_series(conn, metric, sql)
    if len(s) < 6:
        raise ValueError("Need at least 6 months of history to forecast")
    fc, model = forecast_series(s, horizon)
    if store and conn.dialect == "postgres" and "forecasts" in inspect(get_engine(conn)).get_table_names():
        with get_engine(conn).begin() as c:
            c.execute(text("DELETE FROM forecasts WHERE metric=:m"), {"m": metric})
            for r in fc.itertuples():
                c.execute(text("INSERT INTO forecasts(metric,period,value,lower_bound,upper_bound,model) VALUES (:m,:p,:v,:l,:u,:mo)"),
                          dict(m=metric, p=r.period.date(), v=round(r.value, 2), l=round(r.lower, 2), u=round(r.upper, 2), mo=model))
    return {
        "metric": metric, "label": METRICS.get(metric, (metric,))[0], "model": model,
        "history": [{"period": p.date().isoformat(), "value": round(v, 2)} for p, v in s.items()],
        "forecast": [{"period": r.period.date().isoformat(), "value": round(r.value, 2), "lower": round(r.lower, 2),
                      "upper": round(r.upper, 2)} for r in fc.itertuples()],
    }
