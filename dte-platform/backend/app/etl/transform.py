"""AI transform: map extracted columns onto the target table, coerce types, resolve foreign keys, keep a change log."""
from __future__ import annotations

import difflib
import json
import re

import pandas as pd
from sqlalchemy import inspect, text

from ..connectors import get_engine, introspect
from ..db import DbConnection
from ..llm.providers import LLM
from ..nl2sql import prompts
from ..rag import table_doc

DOC_FIELDS_SYSTEM = """Extract structured fields from a business document (invoice, bill, statement, voucher).
Return JSON: {{"rows": [{{<target column>: <value or null>}}]}} using ONLY these target columns: {columns}.
Dates as YYYY-MM-DD. Amounts as plain numbers without currency symbols or thousands separators.
If the document lists several line items, return one row per line item; otherwise one row."""


def target_tables(conn: DbConnection) -> list[dict]:
    return introspect(conn)


def pick_table(llm: LLM, tables: list[dict], df: pd.DataFrame) -> str:
    cands = "\n".join(f"- {t['table']}({', '.join(c['name'] for c in t['columns'])})" for t in tables)
    try:
        out = llm.complete_json(prompts.ETL_TABLE_PICK_SYSTEM,
                                f"CANDIDATES:\n{cands}\n\nSOURCE COLUMNS: {list(df.columns)}\nSAMPLE: {df.head(3).to_json(orient='records', default_handler=str)}",
                                tier="fast")
        if out.get("table") in {t["table"] for t in tables}:
            return out["table"]
    except Exception:  # noqa: BLE001
        pass
    # fallback: best column-name overlap
    def score(t):
        return sum(max((difflib.SequenceMatcher(None, _norm(c["name"]), _norm(s)).ratio() for s in df.columns), default=0)
                   for c in t["columns"])
    return max(tables, key=score)["table"]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


SYNONYMS = {
    "invoice_no": ["invoice number", "invoice #", "inv no", "bill no", "document no", "number"],
    "invoice_date": ["date", "invoice date", "bill date", "doc date"],
    "due_date": ["due", "due date", "payment due"],
    "total_amount": ["total", "amount", "grand total", "invoice total", "gross amount"],
    "amount_untaxed": ["net", "subtotal", "net amount", "taxable value"],
    "tax_amount": ["tax", "gst", "vat", "tax amount"],
    "party_id": ["customer", "vendor", "supplier", "party", "client", "partner"],
    "account_id": ["account", "gl account", "ledger", "account code"],
    "debit": ["dr", "debit amount"], "credit": ["cr", "credit amount"],
    "entry_date": ["date", "posting date", "voucher date"], "entry_no": ["voucher no", "journal no", "entry number"],
    "payment_date": ["date", "paid on", "receipt date"],
}


def heuristic_mapping(target_cols: list[str], source_cols: list[str]) -> dict:
    mapping, used = {}, set()
    for t in target_cols:
        best, best_score = None, 0.0
        for s in source_cols:
            if s in used:
                continue
            cands = [t] + SYNONYMS.get(t, [])
            sc = max(difflib.SequenceMatcher(None, _norm(c), _norm(s)).ratio() for c in cands)
            if sc > best_score:
                best, best_score = s, sc
        if best and best_score >= 0.72:
            mapping[t] = {"source": best, "transform": "none", "confidence": round(best_score, 2)}
            used.add(best)
        else:
            mapping[t] = {"source": None, "transform": "none", "confidence": 0}
    return mapping


def ai_mapping(llm: LLM, table: dict, df: pd.DataFrame) -> tuple[dict, str]:
    target_cols = [c["name"] for c in table["columns"]]
    try:
        out = llm.complete_json(
            prompts.ETL_MAP_SYSTEM.format(table=table["table"], target=table_doc(table)),
            f"SOURCE COLUMNS: {list(df.columns)}\nSAMPLE ROWS: {df.head(5).to_json(orient='records', default_handler=str)}",
            tier="strong")
        m = out.get("mapping", {})
        mapping = {}
        for t in target_cols:
            v = m.get(t) or {}
            src = v.get("source")
            mapping[t] = {"source": src if src in df.columns else None, "transform": v.get("transform") or "none",
                          "confidence": float(v.get("confidence") or 0)}
        return mapping, out.get("notes", "")
    except Exception as e:  # noqa: BLE001
        return heuristic_mapping(target_cols, list(df.columns)), f"AI mapping unavailable ({str(e)[:80]}); used name matching"


def fields_from_text(llm: LLM, table: dict, text_: str) -> pd.DataFrame:
    """For documents without tables (scanned invoices, letters): let the LLM pull the target fields."""
    cols = [c["name"] for c in table["columns"] if not (c["name"] in table.get("primary_key", []))]
    out = llm.complete_json(DOC_FIELDS_SYSTEM.format(columns=", ".join(cols)), text_[:12000], tier="strong")
    return pd.DataFrame(out.get("rows") or [])


def _to_number(s: pd.Series) -> pd.Series:
    def conv(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        if isinstance(v, (int, float)):
            return v
        t = str(v).strip()
        neg = t.startswith("(") and t.endswith(")") or t.endswith("-") or t.upper().endswith(" DR")
        t = re.sub(r"[^0-9.\-]", "", t.replace(",", ""))
        try:
            n = float(t)
            return -abs(n) if neg else n
        except ValueError:
            return None
    return s.map(conv)


def _to_date(s: pd.Series) -> pd.Series:
    out = pd.to_datetime(s, errors="coerce", dayfirst=False, format="mixed")
    # retry ambiguous failures day-first (e.g. 31/01/2026)
    mask = out.isna() & s.notna()
    if mask.any():
        out[mask] = pd.to_datetime(s[mask], errors="coerce", dayfirst=True, format="mixed")
    return out.dt.date


def apply_mapping(conn: DbConnection, table: dict, df: pd.DataFrame, mapping: dict) -> tuple[pd.DataFrame, list[str], list[dict]]:
    log, issues = [], []
    out = pd.DataFrame(index=df.index)
    coltypes = {c["name"]: c["type"].upper() for c in table["columns"]}
    for tcol, m in mapping.items():
        src = m.get("source")
        if not src or src not in df.columns:
            continue
        s = df[src].copy()
        tr = m.get("transform") or "none"
        if tr == "strip" or s.dtype == object:
            s = s.map(lambda v: v.strip() if isinstance(v, str) else v).replace("", None)
        if tr == "upper":
            s = s.str.upper()
        elif tr == "lower":
            s = s.str.lower()
        typ = coltypes.get(tcol, "")
        if tr == "to_date" or "DATE" in typ or "TIMESTAMP" in typ:
            before = s.notna().sum()
            s = _to_date(s)
            bad = before - pd.Series(s).notna().sum()
            if bad:
                issues.append({"severity": "error", "column": tcol, "message": f"{bad} value(s) could not be parsed as dates"})
            log.append(f"{tcol}: parsed dates from '{src}'")
        elif tr in ("to_number", "negate", "abs") or any(k in typ for k in ("NUMERIC", "DECIMAL", "INT", "FLOAT", "DOUBLE", "REAL")):
            fk = next((fk for fk in table["foreign_keys"] if tcol in fk["columns"]), None)
            if fk and s.dropna().map(lambda v: not re.fullmatch(r"\d+", str(v).strip())).any():
                s, unresolved = resolve_fk(conn, fk, s)
                log.append(f"{tcol}: looked up {fk['ref_table']} by name/code from '{src}'")
                if unresolved:
                    issues.append({"severity": "error", "column": tcol,
                                   "message": f"{len(unresolved)} value(s) not found in {fk['ref_table']}: {', '.join(map(str, unresolved[:5]))}"})
            else:
                before = s.notna().sum()
                s = _to_number(s)
                bad = before - s.notna().sum()
                if bad:
                    issues.append({"severity": "error", "column": tcol, "message": f"{bad} value(s) are not numbers"})
                if tr == "negate":
                    s = -s
                elif tr == "abs":
                    s = s.abs()
                log.append(f"{tcol}: numeric from '{src}'" + (f" ({tr})" if tr not in ("none", "to_number") else ""))
        else:
            log.append(f"{tcol}: copied from '{src}'")
        out[tcol] = s
    dropped = len(out) - len(out.dropna(how="all"))
    out = out.dropna(how="all")
    if dropped:
        log.append(f"dropped {dropped} empty row(s)")
    return out.reset_index(drop=True), log, issues


def resolve_fk(conn: DbConnection, fk: dict, s: pd.Series) -> tuple[pd.Series, list]:
    eng = get_engine(conn)
    insp = inspect(eng)
    ref = fk["ref_table"]
    ref_pk = fk["ref_columns"][0]
    cols = [c["name"] for c in insp.get_columns(ref)]
    label_cols = [c for c in ("name", "code", "sku", "invoice_no", "entry_no", "payment_no") if c in cols]
    lookup = {}
    with eng.connect() as c:
        for lc in label_cols:
            for k, v in c.execute(text(f'SELECT "{lc}", "{ref_pk}" FROM "{ref}"')):
                lookup[_norm(k)] = v
    resolved, missing = [], []
    for v in s:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            resolved.append(None)
        elif re.fullmatch(r"\d+", str(v).strip()) and _norm(v) not in lookup:
            resolved.append(int(str(v).strip()))
        else:
            hit = lookup.get(_norm(v))
            if hit is None:
                # fuzzy fallback
                close = difflib.get_close_matches(_norm(v), list(lookup), n=1, cutoff=0.85)
                hit = lookup[close[0]] if close else None
            if hit is None:
                missing.append(v)
            resolved.append(hit)
    return pd.Series(resolved, index=s.index, dtype="object"), sorted(set(map(str, missing)))


def preview(df: pd.DataFrame, n: int = 20) -> dict:
    head = df.head(n).copy()
    for c in head.columns:
        head[c] = head[c].map(lambda v: v.isoformat() if hasattr(v, "isoformat") and not isinstance(v, str) else v)
    return {"columns": list(df.columns), "rows": json.loads(head.to_json(orient="records", default_handler=str)),
            "row_count": int(len(df))}
