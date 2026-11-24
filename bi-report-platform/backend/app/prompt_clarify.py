"""
Asking the few questions a request leaves open, before a report is built from it.

"Build a Risk Status Chart" is a real request, but it does not say what shape the chart should be,
whether the bars should carry counts or shares, or whether each status should keep its own colour.
A model asked that question guesses all three, and the person finds out what it guessed only after
a minute of waiting. Asking first costs one click each and takes no time at all.

The point is to ask only what is still open. "Build a Risk Status Pie Chart showing record counts,
Open - Orange, Closed - Green, Draft - Blue" answers every one of those questions in the sentence
itself, so nothing is asked and the build starts straight away.

No AI model is used here. What is already settled is read out of the words of the request, and the
values a status can take come from the database's own schema, which means the questions appear
instantly, cost nothing, and name the real values rather than invented ones.

Each option carries the text it adds to the request, so the person sees exactly what they are
about to build and can edit it before sending. Nothing is applied behind their back.
"""

import re

from .ai.colors import color_rules_from_prompt
from .datasources import DataSource, column_values, table_columns
from .openpages_detail_reports import expand as expand_detail_report

# Never put more than this in front of someone. Past four questions it stops being a clarification
# and becomes a form, which is the thing the plain-language box exists to avoid.
MAX_QUESTIONS = 4
# Looking further would mean reading the columns of every table on a large connection.
MAX_TABLES = 8
# A column with more values than this is not a status: colouring it by hand would be a chore and
# the chart would be unreadable anyway.
ENUM_MAX = 12
# Below this, one value is not a breakdown.
ENUM_MIN = 2

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")

# Words in a request that say nothing about which table or column it is about.
_STOP = {"the", "and", "for", "with", "all", "any", "show", "showing", "give", "list", "chart",
         "charts", "graph", "report", "reports", "dashboard", "build", "create", "make", "add",
         "using", "use", "each", "per", "by", "of", "a", "an", "in", "on", "to", "me", "my",
         "data", "field", "fields", "object", "objects", "table", "tables", "view", "please",
         "want", "need", "would", "like", "new", "its", "their", "this", "that", "from", "where",
         "ibm", "openpages", "bar", "column", "pie", "donut", "line", "area", "kpi", "card"}

# Keys and hashes are never what a report groups by.
_SKIP_COLUMN = re.compile(r"(^|[_\s:-])(id|uuid|guid|key|code|hash|token|password|rowid)$", re.I)

# Columns holding one thing per record rather than a category. A small table can have few enough
# owner names to look like an enumeration, but colouring people by hand is not what the question
# is for, and on real data the list would be hundreds long.
_FREE_TEXT = re.compile(
    r"(name|description|title|subject|summary|email|address|phone|url|note|notes|comment|remark|"
    r"detail|details|text|reference)", re.I)

# The shape is already named: "a pie chart of...", "show it as a donut".
_SAYS_CHART = re.compile(
    r"\b(bar|bars|column|columns|pie|donut|doughnut|ring|line|trend|area|table|grid|kpi|card|tile|"
    r"gauge|heat ?map|matrix|scatter|funnel|stacked)\b", re.I)

# What to display is already named: "how many", "total spend", "percentage of".
_SAYS_MEASURE = re.compile(
    r"\b(count|counts|counting|how many|number of|total|totals|sum|summed|average|averages|avg|mean|"
    r"median|percent|percentage|percentages|share|shares|proportion|ratio|rate|breakdown|%)\b", re.I)


# ---------------------------------------------------------------------------
# Reading what the request already settles


def _terms(text: str) -> set[str]:
    """The meaningful words in a name or a request, with CamelCase split apart so "SOXRiskStatus"
    matches someone asking about a "risk status"."""
    out: set[str] = set()
    for word in _WORD.findall(text or ""):
        for part in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", word) or [word]:
            low = part.lower()
            if len(low) > 2 and low not in _STOP:
                out.add(low)
                # "statuses" and "status" are the same word to anyone reading.
                if low.endswith("es") and len(low) > 4:
                    out.add(low[:-2])
                elif low.endswith("s") and len(low) > 3:
                    out.add(low[:-1])
    return out


def _overlap(name: str, wanted: set[str]) -> int:
    return len(_terms(name) & wanted)


def _label(name: str) -> str:
    """A column name as a person would say it: "OPSS-Rsk:Risk Status" -> "Risk Status"."""
    bare = name.rpartition(":")[2].rpartition(".")[2]
    return " ".join(bare.replace("_", " ").split()) or name


# ---------------------------------------------------------------------------
# Finding what the report is about


def _choices(source: DataSource, table: str, column: str, ctype: str) -> list[str]:
    """The handful of values a column can take, or [] when it isn't that kind of column.

    OpenPages carries its enumerations in the field definition, which costs nothing to read. A SQL
    database has to be asked, so it is asked once, for one column, with a small limit.
    """
    if _FREE_TEXT.search(column):
        return []
    if source.is_openpages:
        try:
            field = next((f for f in source.client.type_fields(source.op_type(table))
                          if f["name"].lower() == column.lower()), None)
        except Exception:
            return []
        if not field or not field.get("values") or len(field["values"]) > ENUM_MAX:
            return []
    elif not any(t in str(ctype).lower() for t in ("char", "text", "string", "enum")):
        return []
    try:
        values = column_values(source, table, column, limit=ENUM_MAX + 1)
    except Exception:
        return []
    return values if ENUM_MIN <= len(values) <= ENUM_MAX else []


def _subject(source: DataSource, prompt: str) -> dict | None:
    """What the request is about: the table, and the column it most likely breaks down by.

    Returns None when the request names nothing in this database, which is itself worth knowing -
    that is the case where the useful question is "what should the report cover?".
    """
    wanted = _terms(prompt)
    if not wanted:
        return None
    ranked = sorted(source.tables, key=lambda t: -_overlap(t, wanted))
    best: dict | None = None
    for table in ranked[:MAX_TABLES]:
        table_score = _overlap(table, wanted)
        for name, ctype in table_columns(source, table):
            if _SKIP_COLUMN.search(name):
                continue
            score = _overlap(name, wanted) * 3 + table_score
            if score <= table_score:        # the column itself was never named
                continue
            if best is None or score > best["score"]:
                best = {"score": score, "table": table, "column": name, "type": ctype}
    if best is None:
        # The table was named but no column was. Still worth reporting: it rules out the "what
        # should this cover?" question without claiming to know the breakdown.
        if ranked and _overlap(ranked[0], wanted):
            return {"table": ranked[0], "column": "", "label": _label(ranked[0]), "values": []}
        return None
    return {"table": best["table"], "column": best["column"], "label": _label(best["column"]),
            "values": _choices(source, best["table"], best["column"], best["type"])}


# ---------------------------------------------------------------------------
# Colours for a set of values

# What the words mean in a report, most specific first. A status nobody listed here falls through
# to the spare palette below, so every value still gets a colour of its own.
_MEANS = [
    (r"critical|catastroph|severe|extreme|very high|breach|fail", "red"),
    (r"^high$|\bhigh\b|major|overdue|urgent|reject|escalat|non.?complian", "red"),
    (r"significant|elevated|at risk|needs|action required", "orange"),
    (r"^open$|\bopen\b|in progress|ongoing|active|pending|under review|submitted", "orange"),
    (r"moderate|medium|partial|warning|watch|monitor", "yellow"),
    (r"^low$|\blow\b|minor|negligible|insignificant", "green"),
    (r"closed|complete|completed|done|resolved|approved|effective|pass|satisfactor|compliant|mitigated", "green"),
    (r"draft|new|not started|planned|proposed|identified|backlog", "blue"),
    (r"cancel|withdraw|retired|archiv|deferred|on hold|suspended", "grey"),
    (r"n/?a$|^none$|not applicable|unknown|unspecified|blank", "grey"),
]

# For values none of the above describes. Picked to stay apart from each other and to read as
# categories rather than as a rating scale.
_SPARE = ["blue", "teal", "purple", "orange", "green", "pink", "brown", "grey",
          "dark blue", "yellow", "red", "silver"]


def colour_for_values(values: list[str]) -> list[tuple[str, str]]:
    """[(value, colour name)] - the traffic-light reading where the word has one, else a spare.

    "Open", "Closed" and "Draft" come back orange, green and blue, which is what people reach for
    when they colour a status by hand.
    """
    out: list[tuple[str, str]] = []
    taken: set[str] = set()
    spare = list(_SPARE)
    for value in values:
        text = str(value).strip().lower()
        name = next((colour for pattern, colour in _MEANS if re.search(pattern, text, re.I)), "")
        # Two values sharing a colour is fine for a rating scale ("High" and "Critical" are both
        # red) but not for a plain list, so an unnamed value never takes one that is already used.
        if not name:
            name = next((c for c in spare if c not in taken), _SPARE[len(out) % len(_SPARE)])
        taken.add(name)
        out.append((str(value), name))
    return out


def _colour_sentence(label: str, values: list[str]) -> str:
    pairs = ", ".join(f"{value} - {colour.title()}" for value, colour in colour_for_values(values))
    return f"Colour each {label.lower()}: {pairs}."


# ---------------------------------------------------------------------------
# The questions


def _chart_question() -> dict:
    """The shape. Bar and column are the same chart stood on different ends, and that is the
    difference people mean when they name one or the other, so both are offered."""
    horizontal = "Bars across, one per value. Good when the names are long."
    return {
        "id": "chart_type",
        "question": "Which chart type would you prefer?",
        "hint": "Pick the shape you have in mind, or leave it to the model.",
        "options": [
            {"id": "column", "label": "Column chart", "hint": "Columns up the page, one per value.",
             "adds": "Draw it as a column chart.", "charts": ["bar"], "style": {}},
            {"id": "bar", "label": "Bar chart", "hint": horizontal,
             "adds": "Draw it as a horizontal bar chart.", "charts": ["bar"], "style": {"horizontal": True}},
            {"id": "pie", "label": "Pie chart", "hint": "Shares of a whole, up to about eight slices.",
             "adds": "Draw it as a pie chart.", "charts": ["pie"], "style": {}},
            {"id": "donut", "label": "Donut chart", "hint": "A ring, with the total in the middle.",
             "adds": "Draw it as a donut chart.", "charts": ["pie"],
             "style": {"donut": True, "ringLegend": True}},
            {"id": "any", "label": "Let the model choose", "hint": "It picks whatever fits each result.",
             "adds": "", "charts": [], "style": {}},
        ],
    }


def _measure_question(source: DataSource) -> dict:
    """What goes on the chart. On OpenPages a percentage can only be a label, because its query
    language counts but cannot divide - so the option says so rather than quietly giving counts."""
    percent_hint = ("Each value's share of the total."
                    + (" Pie and donut charts show this; OpenPages cannot divide inside a query, "
                       "so bars still carry counts." if source.is_openpages else ""))
    return {
        "id": "measure",
        "question": "What information should be displayed?",
        "hint": "What the labels on the chart say.",
        "options": [
            {"id": "count", "label": "Record count", "hint": "How many records fall into each value.",
             "adds": "Show the record count for each value.", "charts": [], "style": {"showValues": True}},
            {"id": "percent", "label": "Percentage", "hint": percent_hint,
             "adds": "Show each value's percentage of the total.", "charts": [], "style": {}},
            {"id": "both", "label": "Both count and percentage", "hint": "The number, with its share beside it.",
             "adds": "Show both the record count and its percentage of the total.",
             "charts": [], "style": {"showValues": True}},
        ],
    }


def _colour_question(label: str, values: list[str]) -> dict:
    shown = ", ".join(values[:4]) + ("…" if len(values) > 4 else "")
    return {
        "id": "colours",
        "question": f"Should each {label.lower()} get its own colour?",
        "hint": f"{len(values)} values: {shown}",
        "options": [
            {"id": "yes", "label": "Yes, a colour per value",
             "hint": ", ".join(f"{v} {c}" for v, c in colour_for_values(values)[:3]) + "…",
             "adds": _colour_sentence(label, values), "charts": [], "style": {}},
            {"id": "no", "label": "No, use the report palette",
             "hint": "Every chart in the report draws from the same set of colours.",
             "adds": "", "charts": [], "style": {}},
        ],
    }


def _subject_question(source: DataSource) -> dict | None:
    """Asked only when the request names nothing in this database at all, which is the one case
    where every chart after it would be a guess."""
    options = [{"id": t, "label": _label(t), "hint": "", "adds": f"Report on {_label(t)}.",
                "charts": [], "style": {}} for t in source.tables[:6]]
    if len(options) < 2:
        return None
    return {"id": "subject", "question": "Which part of the database should the report cover?",
            "hint": f"{source.name} shares {len(source.tables)} table(s).", "options": options}


def clarify(source: DataSource, prompt: str, parameters: dict | None = None) -> dict:
    """The questions this request leaves open, with the real values of the column it is about.

    Returns {"subject", "questions"}. An empty "questions" means the request says enough: the
    caller should build it as written, without stopping to ask anything.
    """
    parameters = parameters or {}
    text = prompt or ""
    # A request for one of the written-out detail reports has nothing open: the shape, the
    # measure and the window are all settled by the prompt it is about to be expanded into.
    # Asking anyway would add words that stop it being recognised.
    if source.is_openpages and expand_detail_report(text) is not None:
        return {"subject": None, "questions": []}
    subject = _subject(source, text)
    questions: list[dict] = []

    if subject is None:
        asked = _subject_question(source)
        if asked:
            questions.append(asked)

    # A shape named in the request, or chosen in More options, is a shape already decided.
    if not _SAYS_CHART.search(text) and not (parameters.get("charts") or []):
        questions.append(_chart_question())

    if not _SAYS_MEASURE.search(text):
        questions.append(_measure_question(source))

    # Only worth asking where there is something to colour: a column with a handful of values, and
    # no colours already written into the request.
    if subject and subject["values"] and not color_rules_from_prompt(text):
        questions.append(_colour_question(subject["label"], subject["values"]))

    return {"subject": subject, "questions": questions[:MAX_QUESTIONS]}


# ---------------------------------------------------------------------------
# Applying the answers to what was built


def apply_style(widgets: list[dict], style: dict | None) -> None:
    """Puts the look the person asked for onto the charts that were built, in place.

    The planner only knows the six original chart shapes, so a donut is a pie until it gets here.
    Everything else is a flag the renderer already reads.
    """
    style = {k: v for k, v in (style or {}).items() if v}
    if not style:
        return
    donut = bool(style.pop("donut", False))
    for w in widgets:
        if not isinstance(w, dict):
            continue
        chart = dict(w.get("chart") or {})
        kind = chart.get("type")
        if donut and kind == "pie":
            chart["type"] = "donut"
            w["chart"] = chart
            kind = "donut"
        look = dict(w.get("style") or {})
        for key, value in style.items():
            # A ring reads its slices down the side; on a bar chart it would mean nothing. The same
            # goes the other way for horizontal.
            if key == "ringLegend" and kind not in ("pie", "donut"):
                continue
            if key == "horizontal" and kind not in ("bar", "combo"):
                continue
            if key == "showValues" and kind in ("kpi", "table", "matrix"):
                continue
            look.setdefault(key, value)
        if look:
            w["style"] = look
