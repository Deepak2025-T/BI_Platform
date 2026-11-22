"""
What to ask next: context-aware suggestions for chat and for reports.

One function, `suggest`, serves three places:

- "starter"  - the empty chat, before the first question: questions this database can answer,
               from its own tables and columns and from what this person asked of it before.
- "followup" - under a chat answer: where to go from this result, from the question, the answer,
               the result's columns and a few of its rows, the schema and the earlier turns.
- "report"   - beside a report or dashboard: more insights to explore, from its charts, their
               SQL and the numbers it last showed.

The AI model (providers.complete_json) writes the suggestions when one is available. Whatever it
writes is checked before anyone sees it:

- grounded: a suggestion naming a table or column the source does not share is dropped. The model
  lists what each suggestion uses, and the text itself is scanned for anything that looks like an
  identifier (snake_case, dotted, [bracketed], `quoted`); both have to be real.
- new: a suggestion already shown, a question already asked, or a near-copy of another suggestion
  in the same list is dropped.

When no model is chosen, the model fails, or too little of what it wrote survives the checks, the
gaps are filled by suggestions worked out from the columns alone - so the list is never empty
because a model was slow, and never wrong because a model guessed.

Nothing here runs SQL. A suggestion is a sentence; it runs a query only when someone clicks it and
it goes through chat (or "add a chart by asking") like anything typed.
"""

import logging
import re
import time
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai.providers import ModelSpec, complete_json
from .datasources import DataSource, describe, table_columns
from .models import ChatConversation, ChatMessage, Report, User
from .prompt_ideas import (_FREE_TEXT, _GROUP_WORDS, _MEASURE_WORDS, _NUMBER_TYPES, _SKIP, _label,
                           _OP_GENERAL, _openpages_ideas, _pick)

log = logging.getLogger("uvicorn.error")

KINDS = ("starter", "followup", "report")
CATEGORIES = ("basic", "analytical", "advanced", "recent")
# Columns of more tables than this are not read: a big connection would mean a request per table.
MAX_TABLES = 25
SAMPLE_ROWS = 5
CELL_CHARS = 80
TEXT_CHARS = 160
# Two suggestions sharing this much of their meaningful words are the same suggestion.
SIMILAR = 0.75
STARTER_CACHE_SECONDS = 600
_DATE_TYPES = ("date", "time", "year")
_TEXT_TYPES = ("char", "text", "string", "enum")
_DATE_NAME = re.compile(r"(date|month|year|period|quarter|week|day|_at$|_on$|time)", re.I)
_STOP = set("""a an and are as at be by can do does each for from has have how i in is it its me
my of on or our show the their them there this to was we what when where which who why with
you your please give list tell want need get""".split())

_starter_cache: dict[tuple, tuple[float, dict]] = {}


@dataclass
class Suggestion:
    id: str
    text: str
    # basic / analytical / advanced, or "recent" for one of the person's own past questions.
    category: str
    # "question" asks it in chat; "chart" adds it to a report as a chart by asking.
    kind: str = "question"


# ---------------------------------------------------------------------------
# What the source really holds
# ---------------------------------------------------------------------------

@dataclass
class Schema:
    tables: dict[str, list[tuple[str, str]]]   # "schema.table" -> [(column, type)]
    known: set[str]                             # every table and column name, lowercased

    def columns_of(self, tables: list[str]) -> list[tuple[str, str]]:
        out = []
        for t in tables:
            out.extend(self.tables.get(t, []))
        return out


def read_schema(source: DataSource, extra: list[str] | None = None) -> Schema:
    """The tables and columns a suggestion may name. `extra` adds a result's own column names,
    which include computed aliases such as "total" that exist nowhere in the schema."""
    tables: dict[str, list[tuple[str, str]]] = {}
    known: set[str] = set()
    for t in list(source.tables)[:MAX_TABLES]:
        cols = table_columns(source, t)
        tables[t] = cols
        bare = t.rpartition(".")[2]
        known.update({t.lower(), bare.lower(), _label(bare)})
        if "." in t:     # the schema name, so "demo_shop.orders.status" reads as real
            known.add(t.rpartition(".")[0].lower())
        if source.is_openpages:
            known.add(source.op_type(t).lower())
        for name, _ in cols:
            known.update({name.lower(), _label(name)})
    for name in extra or []:
        known.update({str(name).lower(), _label(str(name))})
    return Schema(tables=tables, known=known)


def tables_in_sql(source: DataSource, sql: str) -> list[str]:
    """The shared tables a query reads, matched by name. Never parsed further than that."""
    text = (sql or "").lower()
    out = []
    for t in source.tables:
        bare = t.rpartition(".")[2].lower()
        if re.search(rf"(?<![a-z0-9_]){re.escape(bare)}(?![a-z0-9_])", text):
            out.append(t)
    return out


# Anything in a sentence that looks like a name rather than a word.
_IDENT = re.compile(r"\[([^\]]{1,120})\]|`([^`]{1,120})`|\"([^\"]{1,120})\"|"
                    r"\b([A-Za-z][A-Za-z0-9]*(?:[_.][A-Za-z0-9]+)+)\b")


def _is_known(name: str, schema: Schema) -> bool:
    n = name.strip().lower()
    if not n:
        return True
    if n in schema.known or _label(n) in schema.known:
        return True
    # "orders.amount" or "main.orders": every part has to exist.
    if "." in n:
        return all(p in schema.known or _label(p) in schema.known for p in n.split(".") if p)
    return False


def grounded(text: str, uses: list[str], schema: Schema) -> bool:
    """Whether a suggestion names only tables and columns that exist."""
    for name in uses or []:
        if isinstance(name, str) and not _is_known(name, schema):
            return False
    for match in _IDENT.finditer(text):
        name = next(g for g in match.groups() if g)
        # A quoted phrase is usually a value ("Open", "North"), not a name; only quoted text that
        # is written like an identifier has to be one.
        if match.group(3) and not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:[_.][A-Za-z0-9]+)+", name):
            continue
        if not _is_known(name, schema):
            return False
    return True


# ---------------------------------------------------------------------------
# Never the same thing twice
# ---------------------------------------------------------------------------

def _key(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower())) - _STOP


def _same(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return a == b
    return len(a & b) / len(a | b) >= SIMILAR


class Picker:
    """Collects suggestions, refusing repeats of what was shown, asked or already picked."""

    def __init__(self, seen: list[str], limit: int):
        self.seen = [_key(s) for s in seen if s]
        self.out: list[Suggestion] = []
        self.limit = limit

    def add(self, text: str, category: str, kind: str = "question") -> bool:
        text = " ".join(str(text or "").split())[:TEXT_CHARS].strip()
        if len(text) < 6 or len(self.out) >= self.limit:
            return False
        key = _key(text)
        if any(_same(key, s) for s in self.seen):
            return False
        self.seen.append(key)
        category = category if category in CATEGORIES else "analytical"
        self.out.append(Suggestion(id=f"s{len(self.out)}", text=text, category=category,
                                   kind=kind if kind in ("question", "chart") else "question"))
        return True

    @property
    def full(self) -> bool:
        return len(self.out) >= self.limit


# ---------------------------------------------------------------------------
# Suggestions worked out from the columns alone
# ---------------------------------------------------------------------------

def _roles(columns: list[tuple[str, str]]) -> dict:
    """The column worth adding up, the ones worth grouping by and the date, for one table."""
    number = _pick(columns, _NUMBER_TYPES, _MEASURE_WORDS)
    group = _pick(columns, _TEXT_TYPES, _GROUP_WORDS, avoid=_FREE_TEXT)
    second = _pick([c for c in columns if c[0] != group], _TEXT_TYPES, _GROUP_WORDS, avoid=_FREE_TEXT)
    date = _pick(columns, _DATE_TYPES, ("date", "created", "posted", "order", "invoice"))
    if not date:   # SQLite and friends often type dates as text; the name gives them away
        date = next((n for n, _ in columns if _DATE_NAME.search(n) and not _SKIP.search(n)), "")
    return {"number": number, "group": group, "second": second if second != group else "", "date": date}


def _plural(word: str) -> str:
    """"region" -> "regions", "category" -> "categories"; a name already plural stays as it is."""
    if not word or word.endswith(("s", "x")):
        return word
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


# A past "question" that was really a request for a report or a dashboard (however it is spelt:
# "genrate a risk report" is still one). Those belong to Build a report, not to chat.
_NOT_A_QUESTION = re.compile(r"\b(reports?|dashboards?)\b", re.I)
# A follow-up that only made sense after the answer before it: "these risks", "a pie chart for this".
_NEEDS_CONTEXT = re.compile(r"\b(these|those|them|it|same)\b|\b(this|that)\s*[?.!]*$", re.I)
# Words about a chart's shape rather than the data: a question made only of these is a styling
# request ("crate pie chart"), not something to ask again.
_CHART_WORDS = {"pie", "bar", "bars", "line", "donut", "chart", "charts", "graph", "table", "crate",
                "create", "make", "draw", "change", "convert", "into", "as"}

# OpenPages questions, sorted into levels by what they ask: a breakdown is basic, a question about
# what is overdue, failing or out of line is analytical, one across object types is advanced.
_OP_ANALYTICAL = re.compile(r"overdue|ineffective|breach|against|due for|without|falling due|"
                            r"how complete|accepted|monthly|each month|in scope", re.I)


def _openpages_levels(source: DataSource) -> dict[str, list[str]]:
    general = set(_OP_GENERAL)
    out: dict[str, list[str]] = {"basic": [], "analytical": [], "advanced": []}
    for q in _openpages_ideas(source):
        if q not in general:
            out["analytical" if _OP_ANALYTICAL.search(q) else "basic"].append(q)
    # The questions across object types are always offered, even when the per-type list is long.
    out["advanced"] = list(_OP_GENERAL)
    return out


def _starter_for_table(table: str, columns: list[tuple[str, str]]) -> dict[str, list[str]]:
    thing = _label(table.rpartition(".")[2])
    r = _roles(columns)
    num, grp, sec, date = (_label(r[k]) if r[k] else "" for k in ("number", "group", "second", "date"))
    grps = _plural(grp)
    basic, analytical, advanced = [], [], []
    if grp:
        basic.append(f"How many {thing} are there by {grp}?")
    if num and grp:
        basic.append(f"Total {num} by {grp} in {thing}")
        analytical.append(f"Top 10 {grps} by {num}")
        analytical.append(f"Average {num} per {grp} in {thing}")
        advanced.append(f"What share of total {num} comes from the top 5 {grps}?")
        advanced.append(f"Which {grps} are above the average {num}?")
    if num and date:
        analytical.append(f"Monthly {num} in {thing} over the last 12 months")
        if grp:
            advanced.append(f"{num.capitalize()} by {grp}, this year against last year")
    elif date:
        analytical.append(f"How many {thing} were added each month?")
    if grp and sec:
        advanced.append(f"{thing.capitalize()} by {grp} and {sec}")
    if num and not grp:
        basic.append(f"Total and average {num} in {thing}")
    return {"basic": basic, "analytical": analytical, "advanced": advanced}


def past_questions(db: Session, user: User, source: DataSource, limit: int = 20) -> list[str]:
    """This person's own recent chat questions on this source, newest first, without repeats."""
    chats = db.scalars(select(ChatConversation.id).where(ChatConversation.user_id == user.id,
                                                         ChatConversation.source_id == source.id)
                       .order_by(ChatConversation.updated_at.desc()).limit(40)).all()
    if not chats:
        return []
    rows = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id.in_(chats),
                                                ChatMessage.status == "ok")
                      .order_by(ChatMessage.id.desc()).limit(80)).all()
    out, keys = [], []
    for m in rows:
        q = " ".join((m.question or "").split())
        if not 12 <= len(q) <= TEXT_CHARS or _NOT_A_QUESTION.search(q) or _NEEDS_CONTEXT.search(q):
            continue
        k = _key(q)
        if len(k) < 3 or len(k - _CHART_WORDS) < 2:   # "give pie charts": nothing to ask again
            continue
        if any(_same(k, s) for s in keys):
            continue
        keys.append(k)
        out.append(q)
        if len(out) >= limit:
            break
    return out


def fallback_starters(source: DataSource, schema: Schema, history: list[str], picker: Picker):
    for q in history[:2]:
        picker.add(q, "recent")
    if source.is_openpages:
        levels = _openpages_levels(source)
        # Round robin, so even a short list shows every level.
        for rank in range(max(len(v) for v in levels.values())):
            for category in ("basic", "analytical", "advanced"):
                if rank < len(levels[category]):
                    picker.add(levels[category][rank], category)
        return
    per_table = [_starter_for_table(t, cols) for t, cols in schema.tables.items() if cols]
    # A mix: a basic, an analytical and an advanced question from each table in turn, so a
    # connection of many tables suggests breadth and every level of question shows up.
    for rank in range(4):
        for ideas in per_table:
            for category in ("basic", "analytical", "advanced"):
                if rank < len(ideas[category]):
                    picker.add(ideas[category][rank], category)


def _numeric_columns(columns: list[str], rows: list[list]) -> list[str]:
    out = []
    for i, c in enumerate(columns):
        vals = [r[i] for r in rows if i < len(r) and r[i] is not None]
        if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            out.append(c)
    return out


def _looks_like_date(columns: list[str], rows: list[list], i: int) -> bool:
    if _DATE_NAME.search(columns[i]):
        return True
    vals = [str(r[i]) for r in rows if i < len(r) and r[i] is not None][:5]
    return bool(vals) and all(re.match(r"^\d{4}(-\d{2})?(-\d{2})?|^\d{4}-Q\d", v) for v in vals)


def result_roles(columns: list[str], rows: list[list]) -> dict:
    nums = [c for c in _numeric_columns(columns, rows) if not _SKIP.search(c)]
    date = next((c for i, c in enumerate(columns) if c not in nums and _looks_like_date(columns, rows, i)), "")
    cat = next((c for c in columns if c not in nums and c != date and not _SKIP.search(c)), "")
    return {"numbers": nums, "date": date, "category": cat}


def has_date(source: DataSource, schema: Schema, columns: list[str], rows: list[list], sql: str) -> bool:
    """Whether "compare with the previous period" means anything for this answer."""
    if result_roles(columns, rows)["date"]:
        return True
    return bool(_roles(schema.columns_of(tables_in_sql(source, sql)))["date"])


def fallback_followups(source: DataSource, schema: Schema, ctx: dict, picker: Picker):
    columns, rows = ctx["columns"], ctx["rows"]
    roles = result_roles(columns, rows)
    num = _label(roles["numbers"][0]) if roles["numbers"] else ""
    cat = _plural(_label(roles["category"])) if roles["category"] else ""
    used = {c.lower() for c in columns}
    table_cols = schema.columns_of(tables_in_sql(source, ctx["sql"]))
    t = _roles(table_cols)
    # Another column of the same tables to break the answer down by.
    other = next((n for n, typ in table_cols
                  if any(x in str(typ).lower() for x in _TEXT_TYPES) and n.lower() not in used
                  and not _SKIP.search(n) and not _FREE_TEXT.search(n)), "")
    other = _label(other) if other else ""
    top = ""
    if roles["category"] and rows:
        i = columns.index(roles["category"])
        top = str(rows[0][i])[:40] if rows[0][i] is not None else ""

    one = _label(roles["category"]) if roles["category"] else ""
    if num and cat:
        picker.add(f"Which {cat} are above the average {num}?", "analytical")
        picker.add(f"What share of the total {num} does each {one} make up?", "analytical")
        if top and other:
            picker.add(f"Break down {num} for {top} by {other}", "advanced")
        if other:
            picker.add(f"{num.capitalize()} by {one} and {other}", "advanced")
        picker.add(f"Show only the top 5 {cat} by {num}", "basic")
        picker.add(f"Which {cat} have the lowest {num}?", "basic")
    if roles["date"] and num:
        picker.add(f"Which period had the biggest change in {num}?", "analytical")
        picker.add(f"Compare the latest period's {num} with the one before", "analytical")
        picker.add(f"Show the running total of {num} over time", "advanced")
    elif t["date"] and num:
        picker.add(f"How has {num} changed month by month over the last year?", "analytical")
        if one:
            picker.add(f"Compare {num} by {one} this year with last year", "advanced")
    if not num and one:
        picker.add(f"How many rows are there for each {one}?", "basic")
        if t["number"]:
            picker.add(f"Total {_label(t['number'])} by {one}", "analytical")
    if num and not cat and not roles["date"]:
        if t["group"]:
            picker.add(f"Break {num} down by {_label(t['group'])}", "analytical")
        if t["date"]:
            picker.add(f"Show {num} by month for the last 12 months", "analytical")
    # Whatever is left is filled from what the database can answer in general.
    if not picker.full:
        fallback_starters(source, schema, [], picker)


def fallback_report(source: DataSource, schema: Schema, ctx: dict, picker: Picker):
    widgets = ctx["widgets"]
    has_line = any(w["chart"] in ("line", "area") for w in widgets)
    has_kpi = any(w["chart"] == "kpi" for w in widgets)
    used_cols = {c.lower() for w in widgets for c in w["columns"]}
    for w in widgets[:6]:
        cols = schema.columns_of(tables_in_sql(source, w["sql"]))
        r = _roles(cols)
        y = _label(w["y"]) if w["y"] else (_label(r["number"]) if r["number"] else "")
        x = _plural(_label(w["x"])) if w["x"] else ""
        other = next((n for n, typ in cols if any(t in str(typ).lower() for t in _TEXT_TYPES)
                      and n.lower() not in used_cols and not _SKIP.search(n) and not _FREE_TEXT.search(n)), "")
        if w["top"] and x:
            picker.add(f"What is behind {w['top']} in {w['title']}?", "analytical")
        if y and other:
            picker.add(f"{y.capitalize()} by {_label(other)}", "advanced", kind="chart")
        if r["date"] and y and not has_line:
            picker.add(f"Monthly {y} over the last 12 months", "analytical", kind="chart")
        if r["number"] and not has_kpi:
            picker.add(f"Total {_label(r['number'])} as a KPI card", "basic", kind="chart")
        if r["date"] and w["title"]:
            picker.add(f"How does {w['title']} compare with the same period last year?", "advanced")
        if x and y:
            picker.add(f"Which {x} have the lowest {y}?", "basic")
    if not picker.full:
        fallback_starters(source, schema, [], picker)


# ---------------------------------------------------------------------------
# The AI model
# ---------------------------------------------------------------------------

_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "category": {"type": "string", "enum": ["basic", "analytical", "advanced"]},
                    "kind": {"type": "string", "enum": ["question", "chart"]},
                    "uses": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "category", "kind", "uses"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}

_RULES = """Rules:
- Name only tables and columns listed in the schema or the result columns. Never invent a table,
  a column or a metric the data does not hold (no "profit" unless a profit column exists).
- In "uses", list every table and column each suggestion relies on, spelled exactly as listed.
- Write each suggestion as a short question or request a business user would type (under 15 words),
  in plain words: "Total amount by region", not SQL.
- Mix levels: "basic" (a count, a total, a list), "analytical" (ranking, trend, average, share),
  "advanced" (comparison across periods or two groupings, outliers, drivers).
- Do not repeat or rephrase anything under "Already shown" or "Already asked".
- Never suggest changing data."""


def _sample(columns: list[str], rows: list[list]) -> str:
    lines = [" | ".join(columns)]
    for r in rows[:SAMPLE_ROWS]:
        lines.append(" | ".join(str(v)[:CELL_CHARS] if v is not None else "" for v in r))
    return "\n".join(lines)


def _ai_prompt(kind: str, source: DataSource, ctx: dict, limit: int) -> tuple[str, str]:
    focus = ctx.get("question") or ctx.get("title") or ""
    schema_text = describe(source, focus)
    head = f"You suggest what to ask next in a BI tool, about the database {source.name} ({source.type_label})."
    if kind == "starter":
        task = (f"Suggest {limit} first questions someone could ask of this database, useful to a business "
                "user who has not asked anything yet. Base them on the tables and columns below.")
        body = ""
        if ctx["history"]:
            body = "This person asked these before (suggest related but new questions):\n- " + "\n- ".join(ctx["history"][:8])
    elif kind == "followup":
        task = f"Suggest {limit} follow-up questions to the answer below, each going one step further."
        body = (f"Question: {ctx['question']}\nAnswer: {ctx['answer'][:1200]}\n"
                f"Result ({ctx['row_count']} rows), first rows:\n{_sample(ctx['columns'], ctx['rows'])}")
        if ctx["history"]:
            body += "\nEarlier questions in this chat:\n- " + "\n- ".join(ctx["history"][-6:])
    else:
        task = (f"Suggest {limit} more insights to explore about the report below. Use kind \"chart\" for a "
                "new chart worth adding to the report and \"question\" for something to ask in chat.")
        lines = [f"Report: {ctx['title']}"]
        for w in ctx["widgets"][:10]:
            lines.append(f"- {w['title']} ({w['chart']}): {w['sql'][:300]}")
            if w["columns"]:
                lines.append("  " + _sample(w["columns"], w["rows"][:3]).replace("\n", "\n  "))
        body = "\n".join(lines)
    shown = ctx["previous"][-30:]
    asked = ctx["asked"][-20:]
    extra = ""
    if shown:
        extra += "\nAlready shown:\n- " + "\n- ".join(shown)
    if asked:
        extra += "\nAlready asked:\n- " + "\n- ".join(asked)
    system = f"{head}\n\nSchema:\n{schema_text}\n\n{_RULES}\n\nAnswer in JSON."
    user = f"{task}\n\n{body}{extra}".strip()
    return system, user


def _from_ai(spec: ModelSpec, kind: str, source: DataSource, schema: Schema, ctx: dict,
             picker: Picker) -> int:
    """Adds the model's grounded, new suggestions. Returns how many it wrote in all."""
    system, user = _ai_prompt(kind, source, ctx, picker.limit + 2)
    answer = complete_json(spec, system, user, _SCHEMA)
    items = answer.get("suggestions") if isinstance(answer, dict) else None
    if not isinstance(items, list):
        raise ValueError("the model's answer had no suggestions")
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        uses = item.get("uses") if isinstance(item.get("uses"), list) else []
        if not grounded(text, uses, schema):
            log.info("suggestion dropped, names something not in %s: %r uses %r", source.name, text, uses)
            continue
        kind_ = item.get("kind") if kind == "report" else "question"
        picker.add(text, str(item.get("category") or ""), kind_)
    return len(items)


# ---------------------------------------------------------------------------
# Quick actions
# ---------------------------------------------------------------------------

def followup_actions(ctx: dict, dated: bool) -> list[dict]:
    """What can be done with this answer right here. Only actions that apply are listed."""
    out = []
    cols, n = ctx["columns"], ctx["row_count"] or len(ctx["rows"])
    if len(cols) >= 2 and n >= 2:
        out.append({"id": "change_chart", "label": "Change chart type"})
    if n:
        out.append({"id": "view_rows", "label": "View the rows"})
    if ctx["sql"]:
        out.append({"id": "view_sql", "label": "View the SQL"})
    if n:
        out.append({"id": "export_csv", "label": "Export results"})
    if dated:
        out.append({"id": "compare_period", "label": "Compare with previous period"})
    if ctx["sql"]:
        out.append({"id": "add_to_report", "label": "Add to a report"})
        out.append({"id": "build_report", "label": "Build a report from this"})
    return out


def report_actions(ctx: dict, dated: bool, can_edit: bool, ai: bool) -> list[dict]:
    out = [{"id": "ask_about", "label": "Ask about this report"}]
    if can_edit:
        out.append({"id": "add_chart", "label": "Add charts"})
    if dated:
        out.append({"id": "compare_periods", "label": "Compare periods"})
    if ai and ctx["widgets"]:
        out.append({"id": "executive_summary", "label": "Executive summary"})
    out.append({"id": "export_excel", "label": "Export Excel"})
    out.append({"id": "export_ppt", "label": "Export PowerPoint"})
    out.append({"id": "build_another", "label": "Build another report"})
    return out


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

def _clean_rows(rows: list, columns: list[str]) -> list[list]:
    out = []
    for r in rows[:SAMPLE_ROWS]:
        if isinstance(r, list):
            out.append([v if isinstance(v, (int, float, bool)) or v is None else str(v)[:CELL_CHARS]
                        for v in r[:len(columns)]])
    return out


def report_context(db: Session, report: Report) -> dict:
    """What a report holds, for suggestions: each chart's title, shape, SQL and last numbers."""
    from .refresh import saved_data   # imported here: refresh imports half the app
    config = report.config or {}
    snap = saved_data(db, report)
    results = {w.get("id"): w for w in ((snap.data.get("widgets") if snap else None) or [])}
    widgets = []
    for w in config.get("widgets") or []:
        if w.get("kind") in ("text", "media") or not w.get("sql"):
            continue
        chart = w.get("chart") or {}
        res = results.get(w.get("id")) or {}
        cols = list(res.get("columns") or []) if res.get("ok", True) else []
        rows = _clean_rows(res.get("rows") or [], cols) if cols else []
        x = chart.get("x") or ""
        ys = [y for y in chart.get("y") or [] if y]
        top = ""
        if x in cols and rows:
            v = rows[0][cols.index(x)]
            top = str(v)[:40] if v is not None else ""
        widgets.append({"id": w.get("id"), "title": str(w.get("title") or "")[:120], "chart": chart.get("type") or "",
                        "sql": str(w.get("sql") or ""), "x": x, "y": ys[0] if ys else "",
                        "columns": cols, "rows": rows, "top": top})
    return {"title": report.title, "widgets": widgets}


def suggest(db: Session, user: User, source: DataSource, kind: str, body: dict,
            spec: ModelSpec | None, *, report: Report | None = None, can_edit: bool = False,
            model_notice: str = "") -> dict:
    """Suggestions and quick actions for one place in the app. Never raises for a model failure."""
    limit = max(1, min(int(body.get("limit") or 6), 10))
    if kind == "starter":
        limit = max(limit, 6)
    columns = [str(c)[:120] for c in body.get("columns") or []][:60]
    ctx = {
        "question": str(body.get("question") or "")[:2000],
        "answer": str(body.get("answer") or "")[:4000],
        "title": str(body.get("title") or "")[:200],
        "sql": str(body.get("sql") or "")[:20000],
        "columns": columns,
        "rows": _clean_rows(body.get("rows") or [], columns),
        "row_count": int(body.get("row_count") or 0),
        "previous": [str(s)[:300] for s in body.get("previous") or []][:100],
        "asked": [str(s)[:300] for s in body.get("asked") or []][:50],
        "history": [],
        "widgets": [],
    }
    if kind == "starter":
        cache_key = (user.id, source.id, source.version, tuple(source.tables), spec.model if spec else None)
        hit = _starter_cache.get(cache_key)
        if hit and not body.get("refresh") and time.time() - hit[0] < STARTER_CACHE_SECONDS \
                and not ctx["previous"]:
            return hit[1]
        ctx["history"] = past_questions(db, user, source)
    elif kind == "followup":
        ctx["history"] = ctx["asked"]
    else:
        ctx.update(report_context(db, report))
        ctx["title"] = report.title

    extra = list(columns) + [c for w in ctx["widgets"] for c in w["columns"]]
    # A starter for OpenPages without a model needs no schema: its questions are written in
    # OpenPages words, and reading every object type's fields is one request per type.
    skip_schema = kind == "starter" and spec is None and source.is_openpages
    schema = Schema(tables={}, known=set()) if skip_schema else read_schema(source, extra)
    picker = Picker(ctx["previous"] + ctx["asked"], limit)

    origin, notice = "fallback", model_notice
    if spec is not None:
        try:
            if _from_ai(spec, kind, source, schema, ctx, picker):
                origin = "ai"
        except Exception as err:   # an offer is never worth an error page
            log.warning("suggestions fell back to the columns: %s", err)
            notice = "The AI model couldn't suggest anything just now, so these come from the columns."

    # Too few left after the checks: fill the gaps from the columns.
    if len(picker.out) < min(4, limit):
        if kind == "starter":
            fallback_starters(source, schema, ctx["history"], picker)
        elif kind == "followup":
            fallback_followups(source, schema, ctx, picker)
        else:
            fallback_report(source, schema, ctx, picker)

    if kind == "followup":
        actions = followup_actions(ctx, has_date(source, schema, columns, ctx["rows"], ctx["sql"])) \
            if ctx["sql"] else []
    elif kind == "report":
        dated = any(_roles(schema.columns_of(tables_in_sql(source, w["sql"])))["date"] for w in ctx["widgets"])
        actions = report_actions(ctx, dated, can_edit, ai=spec is not None)
    else:
        actions = []
    result = {"suggestions": [asdict(s) for s in picker.out], "actions": actions,
              "origin": origin, "notice": notice}
    if kind == "starter" and not ctx["previous"]:
        _starter_cache[cache_key] = (time.time(), result)
    return result


def forget(user_id: int | None = None):
    """Drops cached starter suggestions (tests, and after someone's history changes a lot)."""
    for key in [k for k in _starter_cache if user_id is None or k[0] == user_id]:
        del _starter_cache[key]


# ---------------------------------------------------------------------------
# Executive summary of a report, from the numbers it last showed
# ---------------------------------------------------------------------------

_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"},
                   "highlights": {"type": "array", "items": {"type": "string"}}},
    "required": ["summary", "highlights"],
    "additionalProperties": False,
}


def executive_summary(spec: ModelSpec, ctx: dict) -> dict:
    """A short summary for an executive, written by the model from the report's saved numbers.

    No query runs: it reads what the report last showed, and says nothing about charts that have
    no saved numbers. Raises whatever the model raises; the router turns that into a message."""
    lines = [f"Report: {ctx['title']}"]
    with_numbers = 0
    for w in ctx["widgets"][:12]:
        if not w["columns"]:
            continue
        with_numbers += 1
        lines.append(f"\n{w['title']} ({w['chart']}):\n{_sample(w['columns'], w['rows'])}")
    if not with_numbers:
        raise ValueError("This report has no saved numbers yet. Open or refresh it, then try again.")
    system = ("You write executive summaries of BI reports. Use only the numbers given; never invent "
              "figures, causes or metrics. The rows shown are the first few of each chart. Write a "
              "summary of 2 to 4 sentences, then 3 to 5 short highlights. Answer in JSON.")
    answer = complete_json(spec, system, "\n".join(lines), _SUMMARY_SCHEMA)
    summary = " ".join(str(answer.get("summary") or "").split())[:1500]
    highlights = [" ".join(str(h).split())[:240] for h in answer.get("highlights") or [] if str(h).strip()][:6]
    if not summary:
        raise ValueError("The AI model returned an empty summary.")
    return {"summary": summary, "highlights": highlights}
