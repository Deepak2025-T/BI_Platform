"""Validation rules and loaders (direct SQL or REST API)."""
from __future__ import annotations

import json

import httpx
import pandas as pd
from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..connectors import get_engine
from ..db import DbConnection


def validate_rows(conn: DbConnection, table: dict, df: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    if df.empty:
        return [{"severity": "error", "message": "No rows to load"}]
    pk = set(table.get("primary_key", []))
    # required columns (NOT NULL, not serial PK)
    for c in table["columns"]:
        if c["name"] in pk or c.get("nullable", True):
            continue
        if c["name"] not in df.columns:
            issues.append({"severity": "error", "column": c["name"], "message": "Required column is not mapped"})
        else:
            n = int(df[c["name"]].isna().sum())
            if n:
                issues.append({"severity": "error", "column": c["name"], "message": f"{n} row(s) missing a required value"})
    # duplicates within file and against DB for unique columns
    eng = get_engine(conn)
    insp = inspect(eng)
    uniques = [u["column_names"] for u in insp.get_unique_constraints(table["table"])]
    for cols in uniques:
        if not set(cols) <= set(df.columns):
            continue
        dup = int(df.duplicated(subset=cols).sum())
        if dup:
            issues.append({"severity": "error", "column": ",".join(cols), "message": f"{dup} duplicate row(s) inside the file"})
        if len(cols) == 1:
            t = Table(table["table"], MetaData(), autoload_with=eng)
            vals = [v for v in df[cols[0]].dropna().unique().tolist()]
            if vals:
                with eng.connect() as c:
                    existing = c.execute(select(t.c[cols[0]]).where(t.c[cols[0]].in_(vals))).scalars().all()
                if existing:
                    issues.append({"severity": "warning", "column": cols[0],
                                   "message": f"{len(existing)} row(s) already exist (use upsert to update): {', '.join(map(str, existing[:5]))}"})
    # finance rules
    cols = set(df.columns)
    if {"debit", "credit"} <= cols:
        d, c_ = pd.to_numeric(df["debit"]).fillna(0), pd.to_numeric(df["credit"]).fillna(0)
        if "entry_id" in cols:
            g = pd.DataFrame({"e": df["entry_id"], "d": d, "c": c_}).groupby("e").sum()
            bad = g[(g.d - g.c).abs() > 0.01]
            if len(bad):
                issues.append({"severity": "error", "message": f"{len(bad)} journal entr(ies) do not balance (debit ≠ credit)"})
        elif abs(d.sum() - c_.sum()) > 0.01:
            issues.append({"severity": "warning", "message": f"Total debit {d.sum():,.2f} ≠ total credit {c_.sum():,.2f}"})
    if {"amount_untaxed", "tax_amount", "total_amount"} <= cols:
        diff = (pd.to_numeric(df.amount_untaxed).fillna(0) + pd.to_numeric(df.tax_amount).fillna(0) - pd.to_numeric(df.total_amount).fillna(0)).abs()
        n = int((diff > 1).sum())
        if n:
            issues.append({"severity": "warning", "message": f"{n} invoice(s) where untaxed + tax ≠ total"})
    if {"amount_paid", "total_amount"} <= cols:
        n = int((pd.to_numeric(df.amount_paid).fillna(0) > pd.to_numeric(df.total_amount).fillna(0) + 0.01).sum())
        if n:
            issues.append({"severity": "error", "message": f"{n} row(s) with amount_paid greater than total_amount"})
    return issues


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))


def load_direct(conn: DbConnection, table_name: str, df: pd.DataFrame, mode: str = "append") -> int:
    eng = get_engine(conn)
    t = Table(table_name, MetaData(), autoload_with=eng)
    recs = [{k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in r.items()}
            for r in df.astype(object).where(pd.notna(df), None).to_dict(orient="records")]
    if not recs:
        return 0
    with eng.begin() as c:  # single transaction → full rollback on any error
        if mode == "replace":
            c.execute(t.delete())
        if mode == "upsert" and conn.dialect == "postgres":
            insp = inspect(eng)
            keys = next((u["column_names"] for u in insp.get_unique_constraints(table_name)
                         if set(u["column_names"]) <= set(df.columns)), None) \
                or [k for k in insp.get_pk_constraint(table_name)["constrained_columns"] if k in df.columns]
            if not keys:
                raise ValueError("Upsert needs a unique or primary-key column in the mapped data")
            stmt = pg_insert(t).values(recs)
            update_cols = {c_.name: stmt.excluded[c_.name] for c_ in t.columns if c_.name in df.columns and c_.name not in keys}
            stmt = stmt.on_conflict_do_update(index_elements=keys, set_=update_cols) if update_cols else stmt.on_conflict_do_nothing(index_elements=keys)
            c.execute(stmt)
        else:
            c.execute(t.insert(), recs)
    return len(recs)


def load_via_api(url: str, table_name: str, df: pd.DataFrame, headers: dict | None = None, batch: int = 500) -> int:
    """Push rows to an external REST endpoint (e.g. an ERP import API) in JSON batches."""
    recs = _records(df)
    sent = 0
    with httpx.Client(timeout=60, headers=headers or {}) as client:
        for i in range(0, len(recs), batch):
            r = client.post(url, json={"table": table_name, "records": recs[i:i + batch]})
            r.raise_for_status()
            sent += len(recs[i:i + batch])
    return sent
