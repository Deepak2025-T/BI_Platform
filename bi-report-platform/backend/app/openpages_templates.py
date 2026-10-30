"""
Built-in dashboard templates for IBM OpenPages connections.

Each one builds a dashboard of ready-written OpenPages SQL on the connection you choose, so nothing
depends on an AI model. Written for the standard OpenPages GRC data model (field groups such as
OPSS-Ctl, OPSS-Iss, OPSS-Finding, OPSS-Aud); charts whose fields or object types don't exist in a
connection are left out when the dashboard is built, and the person is told which.

OpenPages SQL has no AS, so counts come back as "Count_Resource ID". COUNT works on one object type
only, so charts that count never JOIN; lists may.
"""

COUNT = "Count_Resource ID"
# Bar charts whose values are long phrases.
LONG_LABELS = {"Risks by category", "Management responses", "Root causes", "Issues by type", "Resolution status",
               "Controls by COSO component", "Why policies were revised", "Loss events by risk category",
               "Loss events by business line", "Loss impact by effect subcategory", "How losses were recovered",
               "Risks by residual rating", "Risks by inherent rating", "Findings by category",
               "Audits by country", "Findings by business unit", "Action items by status"}


def _count_by(type_name: str, field: str, title: str, chart: str = "bar", where: str = "", size: str = "auto",
              question: str = "", by_value: bool = False) -> dict:
    """A count per value of one field, largest first (by_value: in the field's order, for years)."""
    ref = f"[{type_name}].[{field}]"
    conditions = [f"{ref} IS NOT NULL"] + ([where] if where else [])
    sql = (f"SELECT {ref}, COUNT([{type_name}].[Resource ID]) FROM [{type_name}] WHERE {' AND '.join(conditions)} "
           f"GROUP BY {ref} ORDER BY " + (ref if by_value else f"COUNT([{type_name}].[Resource ID]) DESC"))
    widget = {"title": title, "question": question or title, "sql": sql, "size": size,
              "chart": {"type": chart, "x": field, "y": [COUNT]}}
    if title in LONG_LABELS:
        widget["style"] = {"horizontal": True, "showValues": True}  # long names read better down the side
    return widget


def _count_by_two(type_name: str, row_field: str, col_field: str, title: str, size: str = "half",
                  question: str = "") -> dict:
    """A count per pair of values, shown as a table: the nearest thing to a heat map here."""
    row, col = f"[{type_name}].[{row_field}]", f"[{type_name}].[{col_field}]"
    sql = (f"SELECT {row}, {col}, COUNT([{type_name}].[Resource ID]) FROM [{type_name}] "
           f"WHERE {row} IS NOT NULL AND {col} IS NOT NULL GROUP BY {row}, {col} ORDER BY {row}, {col}")
    return {"title": title, "question": question or title, "sql": sql, "size": size,
            "chart": {"type": "table", "x": "", "y": []}}


def _total(type_name: str, title: str, where: str = "", size: str = "quarter") -> dict:
    sql = f"SELECT COUNT([{type_name}].[Resource ID]) FROM [{type_name}]" + (f" WHERE {where}" if where else "")
    return {"title": title, "question": title, "sql": sql, "size": size, "chart": {"type": "kpi", "x": "", "y": [COUNT]}}


def _list(title: str, sql: str, size: str = "full") -> dict:
    return {"title": title, "question": title, "sql": sql, "size": size, "chart": {"type": "table", "x": "", "y": []}}


def _heading(title: str, text: str = "") -> dict:
    return {"kind": "text", "title": title, "text": text, "question": "", "sql": "", "size": "full",
            "chart": {"type": "table", "x": "", "y": []}}


def _filter(label: str, type_name: str, field: str, kind: str = "category") -> dict:
    return {"label": label, "kind": kind, "type": type_name, "field": field}


CTL, ISS, FND, AUD, RSK, KRI, POL, OBL = ("SOXControl", "SOXIssue", "Finding", "AuditProgram", "SOXRisk",
                                          "KeyRiskIndicator", "Policy", "Obligation")
# Used by the templates below. LossImpact and LossRecovery are children of LossEvent; BusinessEntity
# carries the geography fields. Installations rename or drop some of these, and any chart whose type
# or field is missing is left out when the dashboard is built.
LOSS, LIMP, LREC, ACT, ENT = "LossEvent", "LossImpact", "LossRecovery", "ActionItem", "BusinessEntity"

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
]


def template_rows() -> list[dict]:
    """The templates as rows for report_templates (layout holds the dashboard)."""
    return [{"name": t["name"], "description": t["description"], "color": t["color"], "prompt": t["prompt"],
             "category": "GRC",
             "layout": {"kind": "dashboard", "source_type": "openpages", "widgets": t["widgets"],
                        "filters": t["filters"]}}
            for t in OPENPAGES_TEMPLATES]
