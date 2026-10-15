"""Turn a result DataFrame into a chart spec + KPI values. Chart *styling* lives in the frontend designer."""
from __future__ import annotations

import datetime as dt
import decimal
import math

import pandas as pd

CHART_TYPES = ["kpi", "line", "area", "column", "bar", "stacked_column", "pie", "donut", "table", "scatter"]
TIME_HINTS = ("date", "month", "period", "year", "quarter", "week", "day", "time")


def roles(df: pd.DataFrame) -> dict:
    time, measures, dims = [], [], []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s) or (len(s.dropna()) and isinstance(s.dropna().iloc[0], (dt.date, dt.datetime))):
            time.append(c)
        elif pd.api.types.is_numeric_dtype(s) or (len(s.dropna()) and isinstance(s.dropna().iloc[0], decimal.Decimal)):
            if any(h in c.lower() for h in ("year", "month", "quarter")) and s.dropna().between(1, 3000).all() and not c.lower().startswith(("total", "sum", "avg")):
                time.append(c)
            elif c.lower().endswith("_id") or c.lower() == "id":
                dims.append(c)
            else:
                measures.append(c)
        else:
            (time if any(h == c.lower() or c.lower().endswith("_" + h) for h in TIME_HINTS) else dims).append(c)
    return {"time": time, "measures": measures, "dimensions": dims}


def infer_chart(df: pd.DataFrame, hint: dict | None = None, preferred: str | None = None) -> dict:
    r = roles(df)
    hint = hint or {}
    cols = list(df.columns)

    def ok(c):
        return c in cols

    x = hint.get("x") if ok(hint.get("x")) else None
    y = [c for c in (hint.get("y") or []) if ok(c)]
    series = hint.get("series") if ok(hint.get("series")) else None
    ctype = preferred or hint.get("type")

    if not y:
        y = r["measures"][:3]
    if not x:
        x = (r["time"] or r["dimensions"] or [None])[0]
    if series is None and len(r["dimensions"]) + len(r["time"]) >= 2 and len(y) == 1:
        others = [c for c in r["time"] + r["dimensions"] if c != x]
        series = others[0] if others else None

    if ctype not in CHART_TYPES:
        if len(df) == 1 and y and not x:
            ctype = "kpi"
        elif not y:
            ctype = "table"
        elif x in r["time"]:
            ctype = "stacked_column" if series else "line"
        elif series:
            ctype = "stacked_column"
        elif x and df[x].nunique() <= 6 and len(y) == 1:
            ctype = "donut"
        elif x:
            ctype = "column" if df[x].nunique() <= 15 else "bar"
        else:
            ctype = "table"
    if ctype in ("pie", "donut") and len(y) > 1:
        y = y[:1]
    return {"type": ctype, "x": x, "y": y, "series": series, "roles": r}


def kpis(df: pd.DataFrame, spec: dict) -> list[dict]:
    """Headline numbers: single-row results → value; time series → latest vs previous period."""
    out = []
    if df.empty:
        return out
    x = spec.get("x")
    for m in spec.get("y", [])[:4]:
        s = pd.to_numeric(df[m], errors="coerce")
        if len(df) == 1 or not x:
            out.append({"measure": m, "value": _num(s.sum() if len(df) > 1 else s.iloc[0])})
        elif x in spec.get("roles", {}).get("time", []) and not spec.get("series"):
            ordered = df.sort_values(x)
            s2 = pd.to_numeric(ordered[m], errors="coerce")
            cur, prev = s2.iloc[-1], (s2.iloc[-2] if len(s2) > 1 else None)
            change = None if prev in (None, 0) or pd.isna(prev) else (cur - prev) / abs(prev) * 100
            out.append({"measure": m, "value": _num(cur), "previous": _num(prev), "change_pct": _num(change),
                        "total": _num(s2.sum()), "period": str(ordered[x].iloc[-1])})
        else:
            out.append({"measure": m, "value": _num(s.sum()), "label": "total"})
    return out


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


def to_records(df: pd.DataFrame) -> list[dict]:
    def conv(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        if isinstance(v, decimal.Decimal):
            return float(v)
        if isinstance(v, (pd.Timestamp, dt.datetime)):
            return v.isoformat()[:19] if (v.hour or v.minute) else v.date().isoformat()
        if isinstance(v, dt.date):
            return v.isoformat()
        if hasattr(v, "item"):
            return v.item()
        return v
    return [{k: conv(v) for k, v in row.items()} for row in df.to_dict(orient="records")]
