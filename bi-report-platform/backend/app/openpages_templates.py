"""
Built-in dashboard templates for IBM OpenPages connections.

Each one builds a dashboard of ready-written OpenPages SQL on the connection you choose, so nothing
depends on an AI model. Written for the standard OpenPages GRC data model (field groups such as
OPSS-Ctl, OPSS-Iss, OPSS-Finding, OPSS-Aud); charts whose fields or object types don't exist in a
connection are left out when the dashboard is built, and the person is told which.

OpenPages SQL has no AS, so counts come back as "Count_Resource ID". COUNT works on one object type
only, so charts that count never JOIN; lists may.
"""

import re

from .report_layout import shape

COUNT = "Count_Resource ID"
# Bar charts whose values are long phrases.
LONG_LABELS = {"Risks by category", "Management responses", "Root causes", "Issues by type", "Resolution status",
               "Controls by COSO component", "Why policies were revised", "Loss events by risk category",
               "Loss events by business line", "Loss impact by effect subcategory", "How losses were recovered",
               "Risks by residual rating", "Risks by inherent rating", "Findings by category",
               "Audits by country", "Findings by business unit", "Action items by status",
               "KRIs by Level 2 taxonomy", "Risks by Level 2 taxonomy", "Incidents by theme",
               "Root causes of issues", "Issue resolution status"}


# A field a template asks for by name, or several names for the same thing. OpenPages installations
# put the same field in different groups - a risk's domain is "OPSS-Risk:Risk Domain" on one server
# and "OPSS-Rsk:Domain" on another, its residual rating "OPSS-Risk:Residual Risk Rating" or
# "OPSS-Risk-Qual:Residual Risk Rating" - and a chart naming only one of them is dropped on every
# server that uses the other. Where a field is known by more than one name, the template lists them
# all: the first is written into the chart, the rest go in "alt_sql", and the build step tries them
# in turn until one runs (see routers/templates.build_dashboard).
Field = str | list[str]


def _names(field: Field) -> list[str]:
    return [field] if isinstance(field, str) else [f for f in field if f]


def _with_alternatives(widget: dict, variants: list[str]) -> dict:
    """The first query on the widget, the rest as alternatives to fall back to."""
    widget["sql"] = variants[0]
    if len(variants) > 1:
        widget["alt_sql"] = variants[1:]
    return widget


def _count_by(type_name: str, field: Field, title: str, chart: str = "bar", where: str = "", size: str = "auto",
              question: str = "", by_value: bool = False, skip_nulls: bool = True) -> dict:
    """A count per value of one field, largest first (by_value: in the field's order, for years).

    skip_nulls=False leaves out the "IS NOT NULL" guard: some object types, custom ones especially,
    answer IS NULL on their own field groups with "columnReference cannot be null" and refuse the
    whole query. Those charts then show a blank slice for items where nobody filled the field in,
    which is honest about the data rather than quietly dropping it."""
    def one(name: str) -> str:
        ref = f"[{type_name}].[{name}]"
        conditions = ([f"{ref} IS NOT NULL"] if skip_nulls else []) + ([where] if where else [])
        return (f"SELECT {ref}, COUNT([{type_name}].[Resource ID]) FROM [{type_name}] "
                + (f"WHERE {' AND '.join(conditions)} " if conditions else "")
                + f"GROUP BY {ref} ORDER BY " + (ref if by_value else f"COUNT([{type_name}].[Resource ID]) DESC"))

    names = _names(field)
    widget = {"title": title, "question": question or title, "sql": "", "size": size,
              # The chart's axis is named for the field that is actually used; the build step renames
              # it if it falls back to another name.
              "chart": {"type": chart, "x": names[0], "y": [COUNT]}, "alt_x": names[1:]}
    if title in LONG_LABELS:
        widget["style"] = {"horizontal": True, "showValues": True}  # long names read better down the side
    return _with_alternatives(widget, [one(n) for n in names])


def _count_by_two(type_name: str, row_field: Field, col_field: Field, title: str, size: str = "half",
                  question: str = "") -> dict:
    """A count per pair of values, shown as a table: the nearest thing to a heat map here."""
    def one(row_name: str, col_name: str) -> str:
        # No ORDER BY: the two fields of a grid like this are almost always enums, and the Query
        # Service answers "OP-60009: Sorting on field [...] type of Enumerated String is not
        # supported" and refuses the query. A grid is read by its cells, not by row order.
        row, col = f"[{type_name}].[{row_name}]", f"[{type_name}].[{col_name}]"
        return (f"SELECT {row}, {col}, COUNT([{type_name}].[Resource ID]) FROM [{type_name}] "
                f"WHERE {row} IS NOT NULL AND {col} IS NOT NULL GROUP BY {row}, {col}")

    pairs = field_pairs(row_field, col_field)
    widget = {"title": title, "question": question or title, "sql": "", "size": size,
              "chart": {"type": "table", "x": "", "y": []},
              "alt_x": [r for r, _ in pairs[1:]], "alt_legend": [c for _, c in pairs[1:]]}
    return _with_alternatives(widget, [one(r, c) for r, c in pairs])


def field_pairs(row_field: Field, col_field: Field) -> list[tuple[str, str]]:
    """Every (row field, column field) a grid of these two fields might be written against, best
    first. Both names vary together on a server that renames a field group, so the pairs are tried
    in step first, and only then every remaining combination."""
    rows, cols = _names(row_field), _names(col_field)
    pairs = [(rows[i], cols[i]) for i in range(min(len(rows), len(cols)))]
    return pairs + [(r, c) for r in rows for c in cols if (r, c) not in pairs]


def _summary(type_name: str, title: str, fields: list[Field], size: str = "full", question: str = "") -> dict:
    """One row per record, with the fields a section is about, as a table.

    Any of the fields may be given as the several names installations file it under. They are tried
    in step - all the first names, then all the second - because a server that renames one field
    group has renamed the others with it, and a SELECT naming one field this installation doesn't
    have fails for all of them. Trying every combination of a six-field table would be hundreds of
    queries for the same answer."""
    steps = max(len(_names(f)) for f in fields)
    variants, seen = [], set()
    for i in range(steps):
        picked = [_names(f)[min(i, len(_names(f)) - 1)] for f in fields]
        sql = (f"SELECT " + ", ".join(f"[{type_name}].[{name}]" for name in picked)
               + f" FROM [{type_name}]")
        if sql not in seen:
            seen.add(sql)
            variants.append(sql)
    widget = {"title": title, "question": question or title, "sql": "", "size": size,
              "chart": {"type": "table", "x": "", "y": []},
              # The names, so the build step can settle them against the object type's own field
              # list in one read instead of guessing (routers/templates.with_known_fields). The
              # queries below are the fallback for when that list can't be read.
              "pick_fields": {"type": type_name, "fields": [_names(f) for f in fields]}}
    return _with_alternatives(widget, variants)


def _total(type_name: str, title: str, where: str | list[str] = "", size: str = "quarter") -> dict:
    """A count of one object type, whole or narrowed by a condition. Several conditions mean the
    same count written against field names that differ between installations; the first that runs
    is the one the tile keeps."""
    wheres = [where] if isinstance(where, str) else list(where) or [""]
    variants = [f"SELECT COUNT([{type_name}].[Resource ID]) FROM [{type_name}]" + (f" WHERE {w}" if w else "")
                for w in wheres]
    widget = {"title": title, "question": title, "sql": "", "size": size,
              "chart": {"type": "kpi", "x": "", "y": [COUNT]}}
    return _with_alternatives(widget, variants)


def _list(title: str, sql: str, size: str = "full") -> dict:
    return {"title": title, "question": title, "sql": sql, "size": size, "chart": {"type": "table", "x": "", "y": []}}


def _heading(title: str, text: str = "") -> dict:
    return {"kind": "text", "title": title, "text": text, "question": "", "sql": "", "size": "full",
            "chart": {"type": "table", "x": "", "y": []}}


def _filter(label: str, types: str | list[str], field: Field, kind: str = "category") -> dict:
    """A filter on one field. With several object types it filters every chart that reads one of
    them. Several names mean the same field under different group names; the build step keeps the
    one the charts turned out to use (see routers/templates)."""
    types = [types] if isinstance(types, str) else types
    names = _names(field)
    f = {"label": label, "kind": kind, "type": types[0], "field": names[0], "alt_fields": names[1:]}
    if len(types) > 1:
        f["types"] = types
    return f


def _styled(widgets: list[dict], style: dict, good_when_down: set[str] = frozenset()) -> list[dict]:
    """Gives every chart the same style; number tiles named in good_when_down turn red when they go up."""
    out = []
    for w in widgets:
        if w.get("kind") != "text":
            w = {**w, "style": {**style, **w.get("style", {}), **({"goodWhen": "down"} if w["title"] in good_when_down else {})}}
        out.append(w)
    return out


CTL, ISS, FND, AUD, RSK, KRI, POL, OBL = ("SOXControl", "SOXIssue", "Finding", "AuditProgram", "SOXRisk",
                                          "KeyRiskIndicator", "Policy", "Obligation")
# Used by the templates below. LossImpact and LossRecovery are children of LossEvent; SOXBusEntity
# is the root of every OpenPages object model (see Openpages_model/Model_name_space.txt), so it
# carries the entity and geography fields. Installations rename or drop some of these, and any
# chart whose type or field is missing is left out when the dashboard is built.
LOSS, LIMP, LREC, ACT, ENT = "LossEvent", "LossImpact", "LossRecovery", "ActionItem", "SOXBusEntity"
# Internal Audit's plan items. The object type's name has spaces in it, and its fields sit in the
# IAM-PlanItem-FG group rather than an OPSS one, because it is part of the Internal Audit solution
# rather than the shared GRC model.
API, APIF = "Audit Plan Item", "IAM-PlanItem-FG:"
# The Equiti ORM dashboard's incidents, and the Basel risk taxonomy levels that KRIs, risks and loss
# events share.
INC = "Incident"
L1, L2 = "OPSS-Shared-Basel:Risk Category", "OPSS-Shared-Basel:Risk Subcategory"

# Public names for the builders above, used by openpages_modules.
count_by, count_by_two, total, table_of, heading, filter_on = (_count_by, _count_by_two, _total, _list,
                                                               _heading, _filter)
summary_table = _summary

OPENPAGES_TEMPLATES = [
    {
        "name": "OpenPages: Controls effectiveness",
        "description": "Control counts, design and operating effectiveness, types and the ineffective list",
        "color": "#0F62FE",
        "prompt": "How effective are our controls, and which ones are ineffective?",
        "widgets": [
            _total(CTL, "Total controls"),
            _total(CTL, "Ineffective controls", f"[{CTL}].[OPSS-Ctl:Design Effectiveness] = 'Ineffective' "
                                                f"OR [{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'"),
            _total(CTL, "Effective by design", f"[{CTL}].[OPSS-Ctl:Design Effectiveness] = 'Effective'"),
            _total(CTL, "Key controls", f"[{CTL}].[OPSS-Ctl:Classification] = 'Key Control Activity'"),
            _count_by(CTL, "OPSS-Ctl:Design Effectiveness", "Design effectiveness", "pie", size="third"),
            _count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Operating effectiveness", "pie", size="third"),
            _count_by(CTL, "OPSS-Ctl:Control Type", "Controls by type", size="third"),
            _count_by(CTL, "OPSS-Ctl:Control Method", "Automated or manual", "pie", size="half"),
            _count_by(CTL, "OPSS-Ctl-Fin:COSO Component", "Controls by COSO component", size="half"),
            _list("Ineffective controls",
                  f"SELECT [{CTL}].[Name], [{CTL}].[OPSS-Ctl:Design Effectiveness], [{CTL}].[OPSS-Ctl:Operating Effectiveness], "
                  f"[{CTL}].[OPSS-Ctl:Control Type] FROM [{CTL}] WHERE [{CTL}].[OPSS-Ctl:Design Effectiveness] = 'Ineffective' "
                  f"OR [{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'"),
        ],
        "filters": [_filter("Control type", CTL, "OPSS-Ctl:Control Type"),
                    _filter("Control status", CTL, "OPSS-Ctl:Status")],
    },
    {
        "name": "OpenPages: Issues and remediation",
        "description": "Open issues by type, priority and resolution status, newest first",
        "color": "#A63D40",
        "prompt": "Where do our open issues stand, and what kind of issues are they?",
        "widgets": [
            _total(ISS, "Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
            _total(ISS, "High priority", f"[{ISS}].[OPSS-Iss:Priority] = 'High'"),
            _total(ISS, "Material weaknesses", f"[{ISS}].[OPSS-Iss:Conclusion] = 'Material Weakness'"),
            _total(ISS, "Classified issues", f"[{ISS}].[OPSS-Iss:Issue Type] IS NOT NULL"),
            _count_by(ISS, "OPSS-Iss:Issue Type", "Issues by type", size="half"),
            _count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="half"),
            _count_by(ISS, "OPSS-Iss:Resolution Status", "Resolution status", size="half"),
            _count_by(ISS, "OPSS-Iss:Root Cause Type", "Root causes", size="half"),
            _list("Latest classified issues",
                  f"SELECT [{ISS}].[Name], [{ISS}].[OPSS-Iss:Issue Type], [{ISS}].[OPSS-Iss:Priority], "
                  f"[{ISS}].[OPSS-Iss:Status], [{ISS}].[Creation Date] FROM [{ISS}] "
                  f"WHERE [{ISS}].[OPSS-Iss:Issue Type] IS NOT NULL ORDER BY [{ISS}].[Creation Date] DESC"),
        ],
        "filters": [_filter("Created", ISS, "Creation Date", "date"),
                    _filter("Priority", ISS, "OPSS-Iss:Priority")],
    },
    {
        "name": "OpenPages: Audit findings",
        "description": "Open findings, priority, impact, management responses and which audit they belong to",
        "color": "#F5A623",
        "prompt": "Summarise our audit findings and management responses",
        "widgets": [
            _total(FND, "Open findings", f"[{FND}].[OPSS-Finding:Status] = 'Open'"),
            _total(FND, "High priority open", f"[{FND}].[OPSS-Finding:Status] = 'Open' AND [{FND}].[OPSS-Finding:Priority] = 'High'"),
            _total(FND, "Significant impact", f"[{FND}].[OPSS-Finding:Impact] = 'Significant'"),
            _total(FND, "Awaiting response", f"[{FND}].[OPSS-Finding:MgmtRespStat] = 'Waiting for Response'"),
            _count_by(FND, "OPSS-Finding:Priority", "Findings by priority", size="third"),
            _count_by(FND, "OPSS-Finding:Impact", "Findings by impact", "pie", size="third"),
            _count_by(FND, "OPSS-Finding:Status", "Open and closed", "pie", size="third"),
            _count_by(FND, "OPSS-Finding:MgmtResp", "Management responses", size="full"),
            _list("Open findings",
                  f"SELECT [{FND}].[Name], [{FND}].[OPSS-Finding:Priority], [{FND}].[OPSS-Finding:Impact], "
                  f"[{FND}].[OPSS-Finding:MgmtRespStat] FROM [{FND}] WHERE [{FND}].[OPSS-Finding:Status] = 'Open'"),
            _list("Findings by audit",
                  f"SELECT [{AUD}].[Name], [{FND}].[Name], [{FND}].[OPSS-Finding:Status], [{FND}].[OPSS-Finding:Priority] "
                  f"FROM [{AUD}] JOIN [{FND}] ON PARENT([{AUD}])"),
        ],
        "filters": [_filter("Finding status", FND, "OPSS-Finding:Status"),
                    _filter("Priority", FND, "OPSS-Finding:Priority")],
    },
    {
        "name": "OpenPages: Audit programme",
        "description": "Audits by status, type and result, with what's in progress",
        "color": "#2A9D8F",
        "prompt": "Show the status of our audit programme",
        "widgets": [
            _total(AUD, "Audits"),
            _total(AUD, "In progress or in review", f"[{AUD}].[OPSS-Aud:Status] IN ('In Progress', 'In Review')"),
            _total(AUD, "Completed", f"[{AUD}].[OPSS-Aud:Status] = 'Completed'"),
            _total(AUD, "Planned or not started", f"[{AUD}].[OPSS-Aud:Status] IN ('Planned', 'Not Started')"),
            _count_by(AUD, "OPSS-Aud:Status", "Audits by status", size="half"),
            _count_by(AUD, "OPSS-Aud:Type", "Audits by type", "pie", size="half"),
            _count_by(AUD, "OPSS-Aud:Result", "Audit results", size="half"),
            _count_by(AUD, "OPSS-Aud:Audit Commitment", "Audits by commitment year", size="half"),
            _list("Audits in progress",
                  f"SELECT [{AUD}].[Name], [{AUD}].[OPSS-Aud:Status], [{AUD}].[OPSS-Aud:Type], [{AUD}].[OPSS-Aud:Result] "
                  f"FROM [{AUD}] WHERE [{AUD}].[OPSS-Aud:Status] IN ('In Progress', 'In Review', 'On Hold')"),
        ],
        "filters": [_filter("Audit type", AUD, "OPSS-Aud:Type")],
    },
    {
        "name": "OpenPages: Risk and KRI monitor",
        "description": "Risks by category and assessment, and key risk indicators with breach status and trend",
        "color": "#6D597A",
        "prompt": "Give me an overview of our risks and key risk indicators",
        "widgets": [
            _total(RSK, "Risks"),
            _total(RSK, "Awaiting assessment", f"[{RSK}].[OPSS-Risk:Status] = 'Awaiting Assessment'"),
            _total(KRI, "Key risk indicators"),
            _total(KRI, "KRIs trending worse", f"[{KRI}].[OPSS-KRI:Indicator Trend] = 'Worse'"),
            _heading("Risks"),
            _count_by(RSK, "OPSS-Shared-Basel:Risk Category", "Risks by category", size="twothird"),
            _count_by(RSK, "OPSS-Risk:Assessment Method", "Assessment method", "pie", size="third"),
            _heading("Key risk indicators"),
            _count_by(KRI, "OPSS-KRI-Shared:Breach Status", "KRI breach status", "pie", size="third"),
            _count_by(KRI, "OPSS-KRI:Indicator Trend", "KRI trend", size="third"),
            _count_by(KRI, "OPSS-KRI:Frequency", "KRI collection frequency", size="third"),
            _list("Key risk indicators",
                  f"SELECT [{KRI}].[Name], [{KRI}].[OPSS-KRI-Shared:Breach Status], [{KRI}].[OPSS-KRI:Indicator Trend], "
                  f"[{KRI}].[OPSS-KRI:Frequency], [{KRI}].[OPSS-KRI:Unit of Measure] FROM [{KRI}]"),
        ],
        "filters": [],
    },
    {
        "name": "OpenPages: Policies and obligations",
        "description": "Policy approval and publishing, and regulatory obligations by risk area",
        "color": "#1E7F4F",
        "prompt": "Where are our policies in their approval cycle, and what obligations do we have?",
        "widgets": [
            _total(POL, "Policies"),
            _total(POL, "Published", f"[{POL}].[OPSS-Pol:Publishing Status] = 'Published Successfully'"),
            _total(POL, "In revision", f"[{POL}].[OPSS-Pol:Approval Status] = 'In Revision'"),
            _total(OBL, "Obligations"),
            _count_by(POL, "OPSS-Pol:Approval Status", "Policy approval status", size="third"),
            _count_by(POL, "OPSS-Pol:Type", "Policy type", "pie", size="third"),
            _count_by(POL, "OPSS-Pol:IssueDept", "Policies by issuing department", size="third"),
            _count_by(OBL, "OPSS-Obl-DT:Functional Risk Area", "Obligations by risk area", "pie", size="half"),
            _count_by(POL, "OPSS-Pol:Revision Type", "Why policies were revised", size="half"),
            _list("Policies",
                  f"SELECT [{POL}].[Name], [{POL}].[OPSS-Pol:Approval Status], [{POL}].[OPSS-Pol:Publishing Status], "
                  f"[{POL}].[OPSS-Pol:Type], [{POL}].[OPSS-Pol:IssueDept] FROM [{POL}]"),
        ],
        "filters": [],
    },
    {
        "name": "OpenPages: Loss events",
        "description": "Operational loss events by status, risk category, business line and outcome, with impact and recovery",
        "color": "#B5179E",
        "prompt": "Show our operational loss events and what they cost us",
        "widgets": [
            _total(LOSS, "Loss events"),
            _total(LOSS, "Open loss events", f"[{LOSS}].[OPSS-LossEv:Status] = 'Open'"),
            _total(LOSS, "Approved loss events", f"[{LOSS}].[OPSS-LossEv:Approval Status] = 'Approved'"),
            _total(LOSS, "Near misses", f"[{LOSS}].[OPSS-LossEv:Outcome] = 'Near Miss'"),
            _heading("Loss event analysis"),
            _count_by(LOSS, "OPSS-LossEv:Status", "Loss events by status", "pie", size="third"),
            _count_by(LOSS, "OPSS-LossEv:Outcome", "Gain, loss or near miss", "pie", size="third"),
            _count_by(LOSS, "OPSS-LossEv:Business Line", "Loss events by business line", size="third"),
            _count_by(LOSS, "OPSS-Shared-Basel:Risk Category L1", "Loss events by risk category", size="full"),
            _heading("Impact and recovery"),
            _count_by(LIMP, "OPSS-LossImp:Impact Category", "Loss impact by category", "pie", size="half"),
            _count_by(LIMP, "OPSS-LossImp:Effect Subcategory", "Loss impact by effect subcategory", size="half"),
            _count_by(LREC, "OPSS-LossRec:Recovery Category", "How losses were recovered", "pie", size="half"),
            _count_by(LREC, "OPSS-LossRec:Status", "Recovery status", size="half"),
            _list("Open loss events",
                  f"SELECT [{LOSS}].[Name], [{LOSS}].[OPSS-LossEv:Status], [{LOSS}].[OPSS-LossEv:Outcome], "
                  f"[{LOSS}].[OPSS-LossEv:Business Line], [{LOSS}].[Creation Date] FROM [{LOSS}] "
                  f"WHERE [{LOSS}].[OPSS-LossEv:Status] = 'Open' ORDER BY [{LOSS}].[Creation Date] DESC"),
            _list("Impacts by loss event",
                  f"SELECT [{LOSS}].[Name], [{LIMP}].[Name], [{LIMP}].[OPSS-LossImp:Impact Category], "
                  f"[{LIMP}].[OPSS-LossImp:Effect Subcategory] FROM [{LOSS}] JOIN [{LIMP}] ON PARENT([{LOSS}])"),
        ],
        "filters": [_filter("Loss event status", LOSS, "OPSS-LossEv:Status"),
                    _filter("Business line", LOSS, "OPSS-LossEv:Business Line"),
                    _filter("Raised", LOSS, "Creation Date", "date")],
    },
    {
        "name": "OpenPages: Action item monitoring",
        "description": "Management action items by status and approval, with the longest-open items listed",
        "color": "#1F7A8C",
        "prompt": "Track the status, progress and ageing of our management action items",
        "widgets": [
            _total(ACT, "Total action items"),
            _total(ACT, "Open action items", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'"),
            _total(ACT, "Awaiting approval", f"[{ACT}].[OPSS-ActItem:Status] = 'Awaiting Approval'"),
            _total(ACT, "Closed action items", f"[{ACT}].[OPSS-ActItem:Status] = 'Closed'"),
            _count_by(ACT, "OPSS-ActItem:Status", "Action items by status", "pie", size="third"),
            _count_by(ACT, "OPSS-ActItem:Submit for Approval", "Submitted for approval", "pie", size="third"),
            _count_by(ACT, "OPSS-ActItem:Priority", "Action items by priority", size="third"),
            _list("Open action items, oldest first",
                  f"SELECT [{ACT}].[Name], [{ACT}].[Description], [{ACT}].[OPSS-ActItem:Status], "
                  f"[{ACT}].[OPSS-ActItem:Start Date], [{ACT}].[OPSS-ActItem:Due Date] FROM [{ACT}] "
                  f"WHERE [{ACT}].[OPSS-ActItem:Status] <> 'Closed' ORDER BY [{ACT}].[OPSS-ActItem:Start Date]"),
            _list("Action items by issue",
                  f"SELECT [{ISS}].[Name], [{ACT}].[Name], [{ACT}].[OPSS-ActItem:Status], "
                  f"[{ACT}].[OPSS-ActItem:Due Date] FROM [{ISS}] JOIN [{ACT}] ON PARENT([{ISS}])"),
        ],
        "filters": [_filter("Action item status", ACT, "OPSS-ActItem:Status"),
                    _filter("Due", ACT, "OPSS-ActItem:Due Date", "date")],
    },
    {
        "name": "OpenPages: Risk assessment overview",
        "description": "Inherent and residual ratings, risk status and a residual likelihood by impact grid",
        "color": "#C1121F",
        "prompt": "Give me a risk overview with inherent and residual ratings and a heat map",
        "widgets": [
            _total(RSK, "Total risks"),
            _total(RSK, "Open risks", f"[{RSK}].[OPSS-Risk:Status] <> 'Closed'"),
            _total(RSK, "Very high residual", f"[{RSK}].[OPSS-Risk:Residual Risk Rating] IN ('Major', 'Significant')"),
            _total(RSK, "Awaiting assessment", f"[{RSK}].[OPSS-Risk:Status] = 'Awaiting Assessment'"),
            _count_by(RSK, "OPSS-Risk:Residual Risk Rating", "Risks by residual rating", size="half"),
            _count_by(RSK, "OPSS-Risk:Inherent Risk Rating", "Risks by inherent rating", size="half"),
            _count_by(RSK, "OPSS-Risk:Status", "Risks by status", "pie", size="third"),
            _count_by(RSK, "OPSS-Shared-Basel:Risk Category L1", "Risks by category", "pie", size="third"),
            _count_by(RSK, "OPSS-Risk:Frequency", "Risks by frequency", size="third"),
            _count_by_two(RSK, "OPSS-Risk:Residual Likelihood", "OPSS-Risk:Residual Impact",
                          "Residual likelihood by impact", size="half",
                          question="How many risks sit at each residual likelihood and impact?"),
            _count_by_two(RSK, "OPSS-Risk:Inherent Likelihood", "OPSS-Risk:Inherent Impact",
                          "Inherent likelihood by impact", size="half"),
            _list("Risks by residual rating",
                  f"SELECT [{RSK}].[Name], [{RSK}].[OPSS-Risk:Inherent Risk Rating], "
                  f"[{RSK}].[OPSS-Risk:Residual Risk Rating], [{RSK}].[OPSS-Risk:Status] FROM [{RSK}] "
                  f"ORDER BY [{RSK}].[OPSS-Risk:Residual Risk Rating]"),
        ],
        "filters": [_filter("Residual rating", RSK, "OPSS-Risk:Residual Risk Rating"),
                    _filter("Risk status", RSK, "OPSS-Risk:Status")],
    },
    {
        "name": "OpenPages: Audit coverage by geography",
        "description": "Where audits run and where findings land, by country, geography and business entity",
        "color": "#15616D",
        "prompt": "Where are we auditing, and which countries have the most findings?",
        "widgets": [
            _total(AUD, "Audits"),
            _total(ENT, "Business entities"),
            _total(FND, "Findings"),
            _total(FND, "Open findings", f"[{FND}].[OPSS-Finding:Status] = 'Open'"),
            _count_by(ENT, "OPSS-Ent:Country", "Entities by country", size="half"),
            _count_by(ENT, "OPSS-Ent:Geography", "Entities by geography", "pie", size="half"),
            _count_by(AUD, "OPSS-Aud:Country", "Audits by country", size="half"),
            _count_by(AUD, "OPSS-Aud:Result", "Audit results", "pie", size="half"),
            _list("Audits by business entity",
                  f"SELECT [{ENT}].[Name], [{ENT}].[OPSS-Ent:Country], [{AUD}].[Name], [{AUD}].[OPSS-Aud:Status], "
                  f"[{AUD}].[OPSS-Aud:Result] FROM [{ENT}] JOIN [{AUD}] ON PARENT([{ENT}])"),
            _list("Findings per audit",
                  f"SELECT [{AUD}].[Name], [{AUD}].[OPSS-Aud:Type], [{FND}].[Name], "
                  f"[{FND}].[OPSS-Finding:Status], [{FND}].[OPSS-Finding:Priority] "
                  f"FROM [{AUD}] JOIN [{FND}] ON PARENT([{AUD}])"),
        ],
        "filters": [_filter("Country", ENT, "OPSS-Ent:Country"),
                    _filter("Audit type", AUD, "OPSS-Aud:Type")],
    },
    {
        "name": "OpenPages: Compliance findings",
        "description": "Compliant against non-compliant findings, by category, business unit and audit year",
        "color": "#007F5F",
        "prompt": "How do our compliant and non-compliant findings compare across business units?",
        "widgets": [
            _total(FND, "Findings"),
            _total(FND, "Non-compliant", f"[{FND}].[OPSS-Finding:Compliance Status] = 'Non-Compliant'"),
            _total(FND, "Compliant", f"[{FND}].[OPSS-Finding:Compliance Status] = 'Compliant'"),
            _total(FND, "Repeat findings", f"[{FND}].[OPSS-Finding:Repeat Finding] = 'Yes'"),
            _count_by(FND, "OPSS-Finding:Compliance Status", "Compliant against non-compliant", "pie", size="third"),
            _count_by(FND, "OPSS-Finding:Category", "Findings by category", size="twothird"),
            _count_by(FND, "OPSS-Finding:Business Unit", "Findings by business unit", size="half"),
            _count_by(AUD, "OPSS-Aud:Audit Commitment", "Audits by year", size="half", by_value=True),
            _count_by_two(FND, "OPSS-Finding:Business Unit", "OPSS-Finding:Compliance Status",
                          "Compliance by business unit", size="half"),
            _count_by_two(FND, "OPSS-Finding:Category", "OPSS-Finding:Compliance Status",
                          "Compliance by finding category", size="half"),
            _list("Non-compliant findings",
                  f"SELECT [{FND}].[Name], [{FND}].[OPSS-Finding:Category], [{FND}].[OPSS-Finding:Business Unit], "
                  f"[{FND}].[OPSS-Finding:Priority], [{FND}].[OPSS-Finding:Status] FROM [{FND}] "
                  f"WHERE [{FND}].[OPSS-Finding:Compliance Status] = 'Non-Compliant'"),
        ],
        "filters": [_filter("Compliance status", FND, "OPSS-Finding:Compliance Status"),
                    _filter("Finding category", FND, "OPSS-Finding:Category")],
    },
    {
        # The "Audit Plan Item Overview" report, as an OpenPages dashboard: the same six breakdowns
        # across the top and the same list of plans underneath. Audit Plan Item refuses IS NULL on
        # its own field group, so these counts keep the unfilled items as a blank slice instead
        # (see _count_by), which is also what the original report shows.
        "name": "OpenPages: Audit plan item overview",
        "description": "Audit plan items by status, type, risk level, priority, quarter and auditable unit",
        "color": "#1B3A5C",
        "prompt": "Give me an audit plan item overview: status, type, risk level, priority, planned "
                  "quarter and auditable unit, with the plan items listed by estimated effort",
        "widgets": [
            _count_by(API, f"{APIF}Status", "Audit plan item — status", "pie", size="third", skip_nulls=False),
            _count_by(API, f"{APIF}Type", "Audit plan item — type", "pie", size="third", skip_nulls=False),
            _count_by(API, f"{APIF}RskLvl", "Audit plan item — risk level", size="third", skip_nulls=False),
            _count_by(API, f"{APIF}Prty", "Audit plan item — priority", size="third", skip_nulls=False),
            _count_by(API, f"{APIF}PlnQtr", "Audit plan item — planned quarter", "pie", size="third",
                      skip_nulls=False),
            _count_by(API, f"{APIF}AudUnt", "Audit plan item — auditable unit", size="third", skip_nulls=False),
            # No LIMIT in OpenPages SQL, so the whole list comes back with the largest effort first
            # rather than only the top ten.
            _list("Audit plans by estimated effort, largest first",
                  f"SELECT [{API}].[Name], [{API}].[Description], [{API}].[{APIF}Status], "
                  f"[{API}].[{APIF}EstmtdEfrt], [{API}].[{APIF}PlnQtr], [{API}].[{APIF}Prty], "
                  f"[{API}].[{APIF}PlndStrt], [{API}].[{APIF}PlndEnd], [{API}].[{APIF}Type], "
                  f"[{API}].[{APIF}RskLvl], [{API}].[Creation Date] FROM [{API}] "
                  f"ORDER BY [{API}].[{APIF}EstmtdEfrt] DESC"),
        ],
        "filters": [_filter("Plan item status", API, f"{APIF}Status"),
                    _filter("Risk level", API, f"{APIF}RskLvl")],
    },
    {
        # The "Action Item Monitoring Dashboard" report. The ageing chart needs a field holding the
        # bucket an item falls in: OpenPages SQL has no date arithmetic, so ageing cannot be worked
        # out in the query. Installations that compute it elsewhere have no such field, and that one
        # chart is then left out when the dashboard is built, with the reason shown.
        "name": "OpenPages: Action item monitoring dashboard",
        "description": "Total, open and closed action items, with status, ageing and approval, and the longest open",
        "color": "#2E8B9B",
        "prompt": "Track the status, progress and ageing of management action items: total, open and "
                  "closed counts, a status breakdown, an ageing analysis and what is awaiting approval",
        "widgets": [
            _total(ACT, "Total action items", size="third"),
            _total(ACT, "Open action items", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'", size="third"),
            _total(ACT, "Closed action items", f"[{ACT}].[OPSS-ActItem:Status] = 'Closed'", size="third"),
            _count_by(ACT, "OPSS-ActItem:Status", "Action items by status", "pie", size="third"),
            _count_by(ACT, "OPSS-ActItem:Aging Bucket", "Action item ageing analysis", size="third"),
            _count_by(ACT, "OPSS-ActItem:Submit for Approval", "Action item submit for approval", "pie",
                      size="third"),
            _list("Action items with the highest open duration",
                  f"SELECT [{ACT}].[Name], [{ACT}].[Description], [{ACT}].[OPSS-ActItem:Status], "
                  f"[{ACT}].[OPSS-ActItem:Start Date], [{ACT}].[OPSS-ActItem:Due Date] FROM [{ACT}] "
                  f"WHERE [{ACT}].[OPSS-ActItem:Status] <> 'Closed' "
                  f"ORDER BY [{ACT}].[OPSS-ActItem:Start Date]"),
        ],
        "filters": [_filter("Action item status", ACT, "OPSS-ActItem:Status"),
                    _filter("Due", ACT, "OPSS-ActItem:Due Date", "date")],
    },
    {
        # The Equiti Group ORM "Consolidated Risk Dashboard": KRIs, RCSA and risk incidents. OpenPages
        # calls Amber "Yellow". Monthly trends come from auto-refresh history (no date functions in
        # OpenPages SQL), and sums of losses from the loss table (no SUM).
        "name": "OpenPages: Equiti ORM dashboard",
        "description": "Operational risk: KRI status and taxonomy, RCSA ratings and heat map, risk incidents and losses",
        "color": "#00AFAB",
        "prompt": "Equiti ORM consolidated risk dashboard: KRIs, risk register and control assessment, risk incidents",
        "widgets": _styled([
            _heading("KRI overview and status", "Key risk indicators by breach status and risk taxonomy. "
                     "Amber is Yellow in OpenPages. Turn on auto-refresh to see changes and trends over time."),
            _total(KRI, "Total KRIs tracked", size="third"),
            _total(KRI, "KRIs in Red", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] = 'Red'", size="third"),
            _total(KRI, "KRIs in Amber", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] = 'Yellow'", size="third"),
            _count_by(KRI, "OPSS-KRI-Shared:Breach Status", "KRIs by indicator status", "pie", size="half"),
            _count_by(KRI, "OPSS-KRI:Indicator Trend", "KRI trend", "pie", size="half"),
            _list("KRIs by Level 1 taxonomy and status",
                  f"SELECT [{KRI}].[{L1}], [{KRI}].[OPSS-KRI-Shared:Breach Status], COUNT([{KRI}].[Resource ID]) FROM [{KRI}] "
                  f"WHERE [{KRI}].[{L1}] IS NOT NULL GROUP BY [{KRI}].[{L1}], [{KRI}].[OPSS-KRI-Shared:Breach Status]", size="half"),
            _count_by(KRI, L2, "KRIs by Level 2 taxonomy", size="half"),
            _list("KRI values against thresholds",
                  f"SELECT [{KRI}].[Name], [{KRI}].[OPSS-KRI-Shared:Breach Status], [{KRI}].[OPSS-KRI:Value], "
                  f"[{KRI}].[OPSS-KRI-Shared:Yellow Threshold], [{KRI}].[OPSS-KRI-Shared:Red Threshold], "
                  f"[{KRI}].[OPSS-KRI:Indicator Trend], [{KRI}].[OPSS-KRI:Value Date] FROM [{KRI}]"),

            _heading("Risk register and control assessment (RCSA)",
                     "Inherent and residual ratings, the residual heat map (impact by likelihood) and controls."),
            _total(RSK, "Total risks", size="third"),
            _total(RSK, "Major risks", f"[{RSK}].[Eval-FG:Res Rating] = 'Major'", size="third"),
            _total(RSK, "Significant risks", f"[{RSK}].[Eval-FG:Res Rating] = 'Significant'", size="third"),
            _count_by(RSK, "OPSS-Risk-Qual:Inherent Risk Rating", "Inherent risk rating", size="half"),
            _count_by(RSK, "OPSS-Risk-Qual:Residual Risk Rating", "Residual risk rating", size="half"),
            _list("Residual risk heat map (impact by likelihood)",
                  f"SELECT [{RSK}].[OPSS-Risk-Qual:Residual Impact], [{RSK}].[OPSS-Risk-Qual:Residual Likelihood], "
                  f"COUNT([{RSK}].[Resource ID]) FROM [{RSK}] WHERE [{RSK}].[OPSS-Risk-Qual:Residual Impact] IS NOT NULL "
                  f"AND [{RSK}].[OPSS-Risk-Qual:Residual Likelihood] IS NOT NULL "
                  f"GROUP BY [{RSK}].[OPSS-Risk-Qual:Residual Impact], [{RSK}].[OPSS-Risk-Qual:Residual Likelihood]", size="half"),
            _count_by(RSK, L2, "Risks by Level 2 taxonomy", size="half"),
            _count_by(CTL, "OPSS-Ctl:Control Method", "Controls by method", "pie", size="half"),
            _list("Risks by business entity",
                  f"SELECT [{ENT}].[Name], [{RSK}].[Name], [{RSK}].[OPSS-Risk-Qual:Residual Risk Rating], "
                  f"[{RSK}].[OPSS-Risk:Status] FROM [{ENT}] JOIN [{RSK}] ON PARENT([{ENT}])", size="half"),

            _heading("Risk incidents overview", "Open and major incidents by theme and rating, and the losses behind them. "
                     "Download Excel to total the losses."),
            _total(INC, "Open incidents", f"[{INC}].[OPSS-Inc:Closed Date] IS NULL", size="third"),
            _total(INC, "Major incidents", f"[{INC}].[OPSS-Inc:Criticality] IN ('Critical', 'High')", size="third"),
            _total(LOSS, "Loss events", size="third"),
            _count_by(INC, "OPSS-Inc:Category", "Incidents by theme", size="third"),
            _count_by(INC, "OPSS-Inc:Criticality", "Incidents by rating", "pie", size="third"),
            _count_by(INC, "OPSS-Inc:Severity", "Incidents by severity", size="third"),
            _list("Top major incidents",
                  f"SELECT [{INC}].[Name], [{INC}].[Description], [{INC}].[OPSS-Inc:Category], [{INC}].[OPSS-Inc:Criticality], "
                  f"[{INC}].[OPSS-Inc:Occurrence Date], [{INC}].[OPSS-Inc:Loss Amount], [{INC}].[OPSS-Inc:Exec_Status], "
                  f"[{INC}].[OPSS-Inc:Closed Date] FROM [{INC}] ORDER BY [{INC}].[OPSS-Inc:Loss Amount] DESC"),
            _list("Loss events and financial impact",
                  f"SELECT [{LOSS}].[Name], [{LOSS}].[{L1}], [{LOSS}].[OPSS-LossEv:Gross Loss], [{LOSS}].[OPSS-LossEv:Net Loss], "
                  f"[{LOSS}].[OPSS-LossEv:Status], [{LOSS}].[OPSS-LossEv:Occurrence Date] FROM [{LOSS}] "
                  f"ORDER BY [{LOSS}].[OPSS-LossEv:Net Loss] DESC"),
        ], {"color": "#00AFAB"}, good_when_down={"KRIs in Red", "KRIs in Amber", "Major risks", "Significant risks",
                                                  "Open incidents", "Major incidents", "Loss events"}),
        "filters": [_filter("Level 1 taxonomy", [KRI, RSK, LOSS], L1),
                    _filter("Level 2 taxonomy", [KRI, RSK, LOSS], L2),
                    _filter("KRI status", KRI, "OPSS-KRI-Shared:Breach Status"),
                    _filter("Residual risk rating", RSK, "OPSS-Risk-Qual:Residual Risk Rating"),
                    _filter("Incident rating", INC, "OPSS-Inc:Criticality"),
                    _filter("Created", [KRI, RSK, CTL, INC, LOSS], "Creation Date", "date")],
    },
    {
        # One page for leadership across the GRC programme. Issues use the OPSS-Issue field group, which is the
        # one filled in on most installations (OPSS-Iss is often left "Not Determined").
        "name": "OpenPages: GRC executive overview",
        "description": "One page for leadership: open issues and findings, weaknesses, controls, KRIs, audits and policies",
        "color": "#0D3B66",
        "prompt": "Give leadership a one-page view of where the GRC programme needs attention",
        "widgets": _styled([
            _heading("At a glance", "The numbers that need attention. Turn on auto-refresh to see what changed since "
                     "the last refresh on each of them."),
            *[{**w, "style": {"headBg": "#0D3B66"}} for w in [
                _total(ISS, "Open issues", f"[{ISS}].[OPSS-Issue:Status] IN ('New', 'Open')"),
                _total(ISS, "High-priority open issues", f"[{ISS}].[OPSS-Issue:Priority] IN ('Critical', 'High') "
                                                         f"AND [{ISS}].[OPSS-Issue:Status] IN ('New', 'Open')"),
                _total(ISS, "Material weaknesses", f"[{ISS}].[OPSS-Issue:Conclusion] = 'Material Weakness'"),
                _total(FND, "Open audit findings", f"[{FND}].[OPSS-Finding:Status] = 'Open'"),
                _total(CTL, "Ineffective controls", f"[{CTL}].[OPSS-Ctl:Design Effectiveness] = 'Ineffective' "
                                                    f"OR [{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'"),
                _total(KRI, "KRIs in Amber or Red", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] IN ('Red', 'Yellow')"),
                _total(AUD, "Audits in progress", f"[{AUD}].[OPSS-Aud:Status] IN ('In Progress', 'In Review')"),
                _total(POL, "Policies in revision", f"[{POL}].[OPSS-Pol:Approval Status] = 'In Revision'"),
            ]],

            _heading("Where attention is needed"),
            _count_by(ISS, "OPSS-Issue:Priority", "Issues by priority", "pie", size="third"),
            _count_by(FND, "OPSS-Finding:Priority", "Open findings by priority", where=f"[{FND}].[OPSS-Finding:Status] = 'Open'",
                      size="third"),
            _count_by(KRI, "OPSS-KRI-Shared:Breach Status", "KRI breach status", "pie", size="third"),
            _count_by(ISS, "OPSS-Issue:Resolution Status", "Issue resolution status", size="half"),
            _count_by(ISS, "OPSS-Issue:Root Cause Type", "Root causes of issues", size="half"),
            _count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Control operating effectiveness", "pie", size="third"),
            _count_by(AUD, "OPSS-Aud:Status", "Audit programme status", size="third"),
            _count_by(RSK, "OPSS-Risk-Qual:Inherent Risk Rating", "Inherent risk rating", size="third"),

            _heading("To follow up"),
            _list("Open material weaknesses",
                  f"SELECT [{ISS}].[Name], [{ISS}].[OPSS-Issue:Issue Type], [{ISS}].[OPSS-Issue:Priority], "
                  f"[{ISS}].[OPSS-Issue:Resolution Status] FROM [{ISS}] WHERE [{ISS}].[OPSS-Issue:Conclusion] = 'Material Weakness' "
                  f"AND [{ISS}].[OPSS-Issue:Status] IN ('New', 'Open')", size="half"),
            _list("High-priority open findings",
                  f"SELECT [{FND}].[Name], [{FND}].[OPSS-Finding:Impact], [{FND}].[OPSS-Finding:MgmtRespStat] FROM [{FND}] "
                  f"WHERE [{FND}].[OPSS-Finding:Status] = 'Open' AND [{FND}].[OPSS-Finding:Priority] = 'High'", size="half"),
            _list("Ineffective controls",
                  f"SELECT [{CTL}].[Name], [{CTL}].[OPSS-Ctl:Design Effectiveness], [{CTL}].[OPSS-Ctl:Operating Effectiveness] "
                  f"FROM [{CTL}] WHERE [{CTL}].[OPSS-Ctl:Design Effectiveness] = 'Ineffective' "
                  f"OR [{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'", size="half"),
            _list("KRIs outside appetite",
                  f"SELECT [{KRI}].[Name], [{KRI}].[OPSS-KRI-Shared:Breach Status], [{KRI}].[OPSS-KRI:Value], "
                  f"[{KRI}].[OPSS-KRI-Shared:Yellow Threshold], [{KRI}].[OPSS-KRI-Shared:Red Threshold], "
                  f"[{KRI}].[OPSS-KRI:Indicator Trend] FROM [{KRI}] "
                  f"WHERE [{KRI}].[OPSS-KRI-Shared:Breach Status] IN ('Red', 'Yellow')", size="half"),
        ], {"color": "#00B4D8"}, good_when_down={"Open issues", "High-priority open issues", "Material weaknesses",
                                                  "Open audit findings", "Ineffective controls", "KRIs in Amber or Red",
                                                  "Policies in revision"}),
        "filters": [_filter("Issue priority", ISS, "OPSS-Issue:Priority"),
                    _filter("Risk category", [KRI, RSK, ISS], L1),
                    _filter("Created", [ISS, FND, CTL, KRI, AUD, POL, RSK], "Creation Date", "date")],
    },
]


# The OpenPages solution each of the templates above belongs to, so they sit in the same folders as
# the module templates in openpages_modules. Nothing is renamed or dropped: they only move.
TEMPLATE_MODULES = {
    "OpenPages: Controls effectiveness": "FCM",
    "OpenPages: Issues and remediation": "ORM",
    "OpenPages: Audit findings": "IAM",
    "OpenPages: Audit programme": "IAM",
    "OpenPages: Risk and KRI monitor": "ORM",
    "OpenPages: Policies and obligations": "PCM",
    "OpenPages: Loss events": "ORM",
    "OpenPages: Action item monitoring": "ORM",
    "OpenPages: Risk assessment overview": "ORM",
    "OpenPages: Audit coverage by geography": "IAM",
    "OpenPages: Compliance findings": "PCM",
    "OpenPages: Audit plan item overview": "IAM",
    "OpenPages: Action item monitoring dashboard": "ORM",
    "OpenPages: Equiti ORM dashboard": "ORM",
    # Leadership's view across every solution, so it sits in no one module's folder.
    "OpenPages: GRC executive overview": "",
}


def template_rows() -> list[dict]:
    """The templates as rows for report_templates (layout holds the dashboard)."""
    return [{"name": t["name"], "description": t["description"], "color": t["color"], "prompt": t["prompt"],
             "category": "GRC", "module": TEMPLATE_MODULES.get(t["name"], ""),
             "layout": {"kind": "dashboard", "source_type": "openpages",
                        "widgets": normalise(t["widgets"]),
                        "filters": with_entity_filter(t["filters"])}}
            for t in OPENPAGES_TEMPLATES]


# ---------------------------------------------------------------------------
# One shape for every template: twelve charts, then the summary table
# ---------------------------------------------------------------------------

# What a template is brought up to. Twelve is three rows of four, or two of six, and it is where a
# dashboard stops being a handful of charts and starts answering a subject.
WANTED_CHARTS = 12

# The filter every OpenPages template carries, on the system field every object has. "*" is
# resolved per chart against that chart's own object type when the dashboard is built.
ENTITY_FILTER = {"label": "Business entity", "kind": "category", "type": "*", "field": "Location"}

# Fields no one wants counted. Every record has its own name and its own dates, so a chart of them
# is one bar per record; amounts and scores are quantities, not categories; the rest are plumbing.
_NOT_A_CATEGORY = re.compile(
    r"(^|[:\s])(name|description|location|resource id|created by|creation date|last modif\w*|"
    r"comments?|notes?|details?|summary|url|link|email|address|phone|identifier|guid|uuid)$", re.I)
#
# Matched on whole words: "Overdue" is a yes/no worth charting, while "Due" on its own is a date
# and would draw one bar per day.
_QUANTITY = re.compile(
    r"\b(amount|amounts|cost|costs|effort|value|values|score|scores|count|number|percent|"
    r"total|totals|days|hours|rate|weight|date|dates|due|start|end|deadline|version|"
    r"revenue|budget|loss|exposure)\b", re.I)

_FIELD_REF = re.compile(r"\[(?P<type>[^\]]+)\]\.\[(?P<field>[^\]]+)\]")


def _label(field: str) -> str:
    """"OPSS-Iss:Root Cause Type" as someone would say it: "root cause type"."""
    bare = field.split(":", 1)[-1].strip()
    return bare[:1].lower() + bare[1:] if bare else field


def _is_chart(w: dict) -> bool:
    return w.get("kind", "chart") == "chart" and (w.get("chart") or {}).get("type") != "table"


def _is_table(w: dict) -> bool:
    return w.get("kind", "chart") == "chart" and (w.get("chart") or {}).get("type") == "table"


def _charted(widgets: list[dict]) -> set[str]:
    """The fields the template already has a chart of, so nothing is suggested twice."""
    out = set()
    for w in widgets:
        if not _is_chart(w):
            continue
        for name in [(w.get("chart") or {}).get("x", "")] + list(w.get("alt_x") or []):
            if name:
                out.add(name.lower())
    return out


def _candidates(widgets: list[dict]) -> list[tuple[str, str]]:
    """(object type, field) pairs worth charting, in the order the template itself mentions them.

    Only fields the template already names somewhere - in a summary table's columns or in a
    query - are used. A field invented here would be dropped on every installation that spells it
    differently, which is how a template ends up shorter than it promised rather than fuller.
    """
    out: list[tuple[str, str]] = []
    seen = set()

    def offer(type_name: str, field: str):
        key = (type_name.lower(), field.lower())
        if key in seen or _NOT_A_CATEGORY.search(field) or _QUANTITY.search(field):
            return
        seen.add(key)
        out.append((type_name, field))

    for w in widgets:
        pick = w.get("pick_fields") or {}
        for names in pick.get("fields") or []:
            # Each entry is the names one installation or another files the field under; they are
            # kept together so the chart can fall back the same way the table does.
            if names and names[0]:
                offer(pick.get("type", ""), names[0])
        for sql in [w.get("sql", "")] + list(w.get("alt_sql") or []):
            for m in _FIELD_REF.finditer(sql or ""):
                offer(m.group("type"), m.group("field"))
    return [(t, f) for t, f in out if t]


def pad_charts(widgets: list[dict], wanted: int = WANTED_CHARTS) -> list[dict]:
    """Brings a template up to `wanted` charts using fields it already names.

    A template with more than that is left exactly as it is: the big module dashboards are long on
    purpose, and cutting one down to a round number would throw away the part someone wrote.
    """
    charts = [w for w in widgets if _is_chart(w)]
    if len(charts) >= wanted:
        return widgets
    already = _charted(widgets)
    extra = []
    for type_name, field in _candidates(widgets):
        if len(charts) + len(extra) >= wanted:
            break
        if field.lower() in already:
            continue
        already.add(field.lower())
        # Pies for the first few, then bars: a pie of twenty values is unreadable, and the fields
        # a template names first are the ones with few values.
        shape = "pie" if len(extra) < 2 else "bar"
        extra.append(_count_by(type_name, field, f"By {_label(field)}", shape, size="third",
                               skip_nulls=False))
    if not extra:
        return widgets
    # In before the closing table, so the summary still reads as the end of the report.
    at = next((i for i in range(len(widgets) - 1, -1, -1) if _is_table(widgets[i])), len(widgets))
    return widgets[:at] + extra + widgets[at:]


def table_last(widgets: list[dict]) -> list[dict]:
    """Moves the summary table to the end, where a report's "and here are the records" belongs."""
    tables = [i for i, w in enumerate(widgets) if _is_table(w)]
    if not tables or tables[-1] == len(widgets) - 1:
        return widgets
    at = tables[-1]
    return widgets[:at] + widgets[at + 1:] + [widgets[at]]


def normalise(widgets: list[dict]) -> list[dict]:
    """One shape for every template: twelve charts where the fields allow it, then the house
    layout - counts at the top, charts three to a row, records last (report_layout.shape)."""
    return shape(table_last(pad_charts(list(widgets))))


def with_entity_filter(filters: list[dict] | None) -> list[dict]:
    """Every OpenPages template filters by business entity, whatever else it offers.

    [Location] is on every object type, so this one filter narrows a whole dashboard to a branch
    of the organisation - which is the question people ask of a GRC report before any other.
    """
    out = list(filters or [])
    if not any(f.get("field") == ENTITY_FILTER["field"] for f in out):
        out.insert(0, dict(ENTITY_FILTER))
    return out
