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
               "Controls by COSO component", "Why policies were revised"}


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
]


def template_rows() -> list[dict]:
    """The templates as rows for report_templates (layout holds the dashboard)."""
    return [{"name": t["name"], "description": t["description"], "color": t["color"], "prompt": t["prompt"],
             "layout": {"kind": "dashboard", "source_type": "openpages", "widgets": t["widgets"],
                        "filters": t["filters"]}}
            for t in OPENPAGES_TEMPLATES]
