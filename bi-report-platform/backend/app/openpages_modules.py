"""
Advanced dashboard templates, ten per IBM OpenPages solution (ORM, PCM, MRG, IAM, ITG, FCM, BCM,
DPM, ESG, TPRM). They are filed under the GRC category, in a folder named after the solution.

Everything here is rooted at the business entity. In every OpenPages object model the root of the
hierarchy is SOXBusEntity (see Openpages_model/Model_name_space.txt: every namespace begins
"SOXBusEntity|SOXBusEntity, SOXBusEntity|..."), so each dashboard:

  * opens with a business entity section, counting the entities the rest of the dashboard sits under;
  * ends with a list joined down from [SOXBusEntity], so the rows carry the entity they belong to;
  * carries a "Business entity" filter of kind "*", which the build step points at each chart's own
    object type on the [Location] field. [Location] is a system field on every object and holds the
    entity path the object hangs under, so one filter narrows an entire dashboard to a branch of the
    hierarchy even though OpenPages SQL cannot join a COUNT to its parent.

Field names (the OPSS-* groups) differ between installations. A chart whose object type or field is
missing is left out when the dashboard is built, and the person is told which, so a template degrades
instead of failing. Only the object types are reliable: they come from the shipped object models.

OpenPages SQL has no AS, no SUM and no date functions; COUNT works on one object type at a time and
never alongside a JOIN. Totals are therefore counts, and amounts appear in lists rather than charts.
"""

from .openpages_templates import COUNT, ENT, count_by, count_by_two, filter_on, heading, table_of, total

# ---------- object types, from the shipped object models and solution profiles ----------

ACT, ISS, CTL, RSK, PRC, SUB = "ActionItem", "SOXIssue", "SOXControl", "SOXRisk", "SOXProcess", "SOXSubprocess"
TEST, TRES, CEVAL, REVAL, PEVAL = "SOXTest", "SOXTestResult", "CtlEval", "RiskEval", "ProcessEval"
RASS, RAEVAL, CTLOBJ = "RiskAssessment", "RiskAssessmentEval", "ControlObjective"
LOSS, LIMP, LREC, ORX, FIRST = "LossEvent", "LossImpact", "LossRecovery", "ORXLoss", "FIRSTLoss"
KRI, KRIV, KPI, KPIV = "KeyRiskIndicator", "KeyRiskIndicatorValue", "KeyPerfIndicator", "KeyPerfIndicatorValue"
SCEN, SRES, TREAT, CAUSE, CONSQ = "ScenarioAnalysis", "ScenarioResult", "Treatment", "Cause", "Consequence"
ACC, SACC, ASRT, EMP, CC = "SOXAccount", "SOXSubaccount", "Assertion", "Employee", "CostCenter"
POL, PRCD, MAND, SMAND, REQ = "Policy", "Procedure", "Mandate", "Submandate", "Requirement"
OBL, OBLE, REGCH, REGTASK, REGL = "Obligation", "ObligationEvaluation", "RegChange", "RegulatoryTask", "Regulator"
REGI, REGAPP, ATT, CAMP, WAIV = "RegulatoryInitiative", "RegulationApplicability", "Attestation", "Campaign", "Waiver"
PRC_RC, POL_RC = "ComplianceReviewComment", "PolicyReviewComment"
MODEL, MLINK, MIN, MOUT, MSCORE = "Model", "ModelLink", "ModelInput", "ModelOutput", "ModelScorecard"
MATT, MUSE, REVIEW, CHAL, CHG, CMTE = "ModelAttestation", "ModelUseCase", "Review", "Challenge", "ChangeRequest", "Committee"
METRIC, METV = "Metric", "MetricValue"
AUDE, AUD, APHASE, WP, FND = "AuditableEntity", "AuditProgram", "AuditPhase", "Workpaper", "Finding"
AUDR, PLAN, SPLAN, TSHEET, RCMT = "Auditor", "Plan", "SummaryAuditPlan", "Timesheet", "ReviewComment"
RES, RLINK, BASE, INC, THR, VUL = "Resource", "ResourceLink", "Baseline", "Incident", "Threat", "Vulnerability"
BCP, BCTP, BCTR, BIA, BSVC, BSEV = ("BCPlan", "BCTestPlan", "BCTestResult", "BusinessImpactAnalysis",
                                    "BusinessService", "BusinessServiceEval")
BCEV, LOC, TEAM = "BCEvent", "Location", "Team"
OBJV, PROD, DISC = "Objective", "Product", "DisclosureStatement"
VEN, VSUB, SUBC, CONT, ENG = "Vendor", "VendorSubsidiary", "Subcontractor", "Contract", "Engagement"
PROG, QA, QT = "Program", "QuestionnaireAssessment", "QuestionnaireTemplate"

# The filter every dashboard carries. "*" is resolved per chart against the chart's own object type.
ROOT_FILTER = {"label": "Business entity", "kind": "category", "type": "*", "field": "Location"}


def rooted(child: str, title: str, fields: list[str], direct: bool = False, size: str = "full") -> dict:
    """A list that starts at the root object and walks down to `child`, so every row names the
    business entity it belongs to. PARENT is for a direct child; ANCESTOR reaches any depth."""
    join = f"PARENT([{ENT}])" if direct else f"ANCESTOR([{ENT}])"
    columns = ", ".join([f"[{ENT}].[Name]"] + [f"[{child}].[{f}]" for f in ["Name"] + fields])
    return table_of(title, f"SELECT {columns} FROM [{ENT}] JOIN [{child}] ON {join}", size=size)


def entity_section(what: str) -> list[dict]:
    """The business entity header every dashboard opens with."""
    return [heading("Business entities", f"Everything below hangs under these entities. {what}"),
            total(ENT, "Business entities", size="quarter"),
            count_by(ENT, "OPSS-Ent:Entity Type", "Entities by type", "pie", size="third"),
            count_by(ENT, "OPSS-Ent:Status", "Entities by status", "pie", size="third")]


def report(module: str, name: str, description: str, color: str, prompt: str, body: list[dict],
           filters: list[dict] | None = None, intro: str = "") -> dict:
    return {"module": module, "name": f"{module}: {name}", "description": description, "color": color,
            "prompt": prompt, "widgets": entity_section(intro) + body,
            "filters": [ROOT_FILTER] + list(filters or [])}


def kpis(type_name: str, items: list[tuple[str, str]]) -> list[dict]:
    return [total(type_name, title, where) for title, where in items]


def status_set(type_name: str, prefix: str, extra: list[tuple[str, str, str, str]] = ()) -> list[dict]:
    """The three breakdowns almost every object type supports, plus whatever else is passed."""
    charts = [count_by(type_name, f"{prefix}:Status", "By status", "pie", size="third")]
    charts += [count_by(t, f, title, chart, size="third") for t, f, title, chart in extra]
    return charts


# ---------- ORM: Operational Risk Management ----------

ORM_COLOR = "#6D597A"
ORM = [
    report("ORM", "Risk and control profile",
           "Risks and the controls on them, by category, rating and effectiveness, under each entity",
           ORM_COLOR, "Show our operational risk and control profile by business entity",
           kpis(RSK, [("Risks", ""), ("Open risks", f"[{RSK}].[OPSS-Risk:Status] <> 'Closed'")]) +
           kpis(CTL, [("Controls", ""),
                      ("Ineffective controls", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'")]) +
           [count_by(RSK, "OPSS-Shared-Basel:Risk Category L1", "Risks by Basel category", size="half"),
            count_by(RSK, "OPSS-Risk:Residual Risk Rating", "Risks by residual rating", size="half"),
            count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Control effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Method", "Automated or manual", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Classification", "Key against standard controls", "pie", size="third"),
            count_by_two(RSK, "OPSS-Risk:Residual Likelihood", "OPSS-Risk:Residual Impact",
                         "Residual likelihood by impact", size="half"),
            rooted(RSK, "Risks by entity", ["OPSS-Risk:Residual Risk Rating", "OPSS-Risk:Status"])],
           [filter_on("Residual rating", RSK, "OPSS-Risk:Residual Risk Rating")]),
    report("ORM", "Loss events",
           "Loss events by status, Basel category, business line and outcome, with impacts and recoveries",
           ORM_COLOR, "Show operational loss events and their impacts by business entity",
           kpis(LOSS, [("Loss events", ""), ("Open loss events", f"[{LOSS}].[OPSS-LossEv:Status] = 'Open'"),
                       ("Near misses", f"[{LOSS}].[OPSS-LossEv:Outcome] = 'Near Miss'"),
                       ("Approved", f"[{LOSS}].[OPSS-LossEv:Approval Status] = 'Approved'")]) +
           [count_by(LOSS, "OPSS-Shared-Basel:Risk Category L1", "Loss events by Basel category", size="half"),
            count_by(LOSS, "OPSS-LossEv:Business Line", "Loss events by business line", size="half"),
            count_by(LOSS, "OPSS-LossEv:Outcome", "Gain, loss or near miss", "pie", size="third"),
            count_by(LIMP, "OPSS-LossImp:Impact Category", "Impact by category", "pie", size="third"),
            count_by(LREC, "OPSS-LossRec:Recovery Category", "Recovery by category", "pie", size="third"),
            rooted(LOSS, "Loss events by entity",
                   ["OPSS-LossEv:Status", "OPSS-LossEv:Outcome", "Creation Date"], direct=True)],
           [filter_on("Loss event status", LOSS, "OPSS-LossEv:Status"),
            filter_on("Raised", LOSS, "Creation Date", "date")]),
    report("ORM", "Key risk indicators",
           "KRI breach status, trend and collection frequency, with the values behind them",
           ORM_COLOR, "How are our key risk indicators performing by business entity?",
           kpis(KRI, [("Key risk indicators", ""),
                      ("In breach", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] <> 'Within Threshold'"),
                      ("Trending worse", f"[{KRI}].[OPSS-KRI:Indicator Trend] = 'Worse'")]) +
           kpis(KRIV, [("KRI readings", "")]) +
           [count_by(KRI, "OPSS-KRI-Shared:Breach Status", "Breach status", "pie", size="third"),
            count_by(KRI, "OPSS-KRI:Indicator Trend", "Trend", "pie", size="third"),
            count_by(KRI, "OPSS-KRI:Frequency", "Collection frequency", size="third"),
            count_by_two(KRI, "OPSS-KRI-Shared:Breach Status", "OPSS-KRI:Indicator Trend",
                         "Breach status by trend", size="half"),
            rooted(KRI, "Indicators by entity",
                   ["OPSS-KRI-Shared:Breach Status", "OPSS-KRI:Indicator Trend", "OPSS-KRI:Frequency"],
                   direct=True)],
           [filter_on("Breach status", KRI, "OPSS-KRI-Shared:Breach Status")]),
    report("ORM", "Risk and control self-assessment",
           "Risk assessments and their evaluations, by status, method and rating",
           ORM_COLOR, "Where do our risk and control self-assessments stand?",
           kpis(RASS, [("Risk assessments", ""),
                       ("In progress", f"[{RASS}].[OPSS-RiskAssess:Status] = 'In Progress'"),
                       ("Completed", f"[{RASS}].[OPSS-RiskAssess:Status] = 'Completed'")]) +
           kpis(REVAL, [("Risk evaluations", "")]) +
           [count_by(RASS, "OPSS-RiskAssess:Status", "Assessments by status", "pie", size="third"),
            count_by(RASS, "OPSS-RiskAssess:Type", "Assessments by type", "pie", size="third"),
            count_by(REVAL, "OPSS-RiskEval:Residual Risk Rating", "Evaluated residual rating", size="third"),
            count_by(CEVAL, "OPSS-CtlEval:Operating Effectiveness", "Evaluated control effectiveness",
                     size="half"),
            rooted(RASS, "Assessments by entity",
                   ["OPSS-RiskAssess:Status", "OPSS-RiskAssess:Type"], direct=True)],
           [filter_on("Assessment status", RASS, "OPSS-RiskAssess:Status")]),
    report("ORM", "Scenario analysis",
           "Scenario analyses and their results, by status, severity and category",
           ORM_COLOR, "Summarise our operational risk scenario analyses",
           kpis(SCEN, [("Scenario analyses", ""),
                       ("Approved", f"[{SCEN}].[OPSS-ScenAn:Status] = 'Approved'"),
                       ("In progress", f"[{SCEN}].[OPSS-ScenAn:Status] = 'In Progress'")]) +
           kpis(SRES, [("Scenario results", "")]) +
           [count_by(SCEN, "OPSS-ScenAn:Status", "Scenarios by status", "pie", size="third"),
            count_by(SCEN, "OPSS-ScenAn:Scenario Type", "Scenarios by type", "pie", size="third"),
            count_by(SCEN, "OPSS-Shared-Basel:Risk Category L1", "Scenarios by Basel category", size="third"),
            count_by(SRES, "OPSS-ScenRes:Severity", "Results by severity", size="half"),
            rooted(SCEN, "Scenarios by entity", ["OPSS-ScenAn:Status", "OPSS-ScenAn:Scenario Type"],
                   direct=True)]),
    report("ORM", "Process and sub-process coverage",
           "Which processes carry risks and controls, and which are still unassessed",
           ORM_COLOR, "Which processes and sub-processes are covered by risks and controls?",
           kpis(PRC, [("Processes", "")]) + kpis(SUB, [("Sub-processes", "")]) +
           kpis(RSK, [("Risks", "")]) + kpis(CTL, [("Controls", "")]) +
           [count_by(PRC, "OPSS-Proc:Status", "Processes by status", "pie", size="third"),
            count_by(PRC, "OPSS-Proc:Process Type", "Processes by type", "pie", size="third"),
            count_by(SUB, "OPSS-Subproc:Status", "Sub-processes by status", "pie", size="third"),
            count_by(PEVAL, "OPSS-ProcEval:Conclusion", "Process evaluation conclusions", size="half"),
            rooted(PRC, "Processes by entity", ["OPSS-Proc:Status", "OPSS-Proc:Process Type"], direct=True),
            table_of("Risks under each process",
                     f"SELECT [{PRC}].[Name], [{RSK}].[Name], [{RSK}].[OPSS-Risk:Residual Risk Rating] "
                     f"FROM [{PRC}] JOIN [{RSK}] ON ANCESTOR([{PRC}])")]),
    report("ORM", "Control testing",
           "Test plans and their results, by status, conclusion and tester",
           ORM_COLOR, "How is operational control testing going?",
           kpis(TEST, [("Test plans", ""), ("Open tests", f"[{TEST}].[OPSS-Test:Status] <> 'Closed'")]) +
           kpis(TRES, [("Test results", ""),
                       ("Failed tests", f"[{TRES}].[OPSS-TestRes:Conclusion] = 'Fail'")]) +
           [count_by(TEST, "OPSS-Test:Status", "Tests by status", "pie", size="third"),
            count_by(TEST, "OPSS-Test:Test Type", "Tests by type", "pie", size="third"),
            count_by(TRES, "OPSS-TestRes:Conclusion", "Results by conclusion", "pie", size="third"),
            count_by(TRES, "OPSS-TestRes:Status", "Results by status", size="half"),
            table_of("Results under each test",
                     f"SELECT [{TEST}].[Name], [{TRES}].[Name], [{TRES}].[OPSS-TestRes:Conclusion], "
                     f"[{TRES}].[OPSS-TestRes:Status] FROM [{TEST}] JOIN [{TRES}] ON PARENT([{TEST}])"),
            rooted(TEST, "Tests by entity", ["OPSS-Test:Status", "OPSS-Test:Test Type"])]),
    report("ORM", "Issues and action items",
           "Open issues, their priority and root cause, and the action items closing them",
           ORM_COLOR, "Where do our operational risk issues and actions stand?",
           kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
                      ("High priority", f"[{ISS}].[OPSS-Iss:Priority] = 'High'")]) +
           kpis(ACT, [("Open action items", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'"),
                      ("Awaiting approval", f"[{ACT}].[OPSS-ActItem:Status] = 'Awaiting Approval'")]) +
           [count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Root Cause Type", "Issues by root cause", size="third"),
            count_by(ACT, "OPSS-ActItem:Status", "Action items by status", "pie", size="third"),
            count_by_two(ISS, "OPSS-Iss:Status", "OPSS-Iss:Priority", "Issue status by priority", size="half"),
            table_of("Action items under each issue",
                     f"SELECT [{ISS}].[Name], [{ACT}].[Name], [{ACT}].[OPSS-ActItem:Status], "
                     f"[{ACT}].[OPSS-ActItem:Due Date] FROM [{ISS}] JOIN [{ACT}] ON PARENT([{ISS}])"),
            rooted(ISS, "Issues by entity", ["OPSS-Iss:Status", "OPSS-Iss:Priority"])],
           [filter_on("Issue priority", ISS, "OPSS-Iss:Priority")]),
    report("ORM", "External loss benchmarking",
           "ORX and FIRST external loss data beside our own loss events",
           ORM_COLOR, "How do our losses compare with external loss data?",
           kpis(LOSS, [("Internal loss events", "")]) + kpis(ORX, [("ORX losses", "")]) +
           kpis(FIRST, [("FIRST losses", "")]) +
           kpis(LOSS, [("Open internally", f"[{LOSS}].[OPSS-LossEv:Status] = 'Open'")]) +
           [count_by(ORX, "OPSS-Shared-Basel:Risk Category L1", "ORX losses by Basel category", size="half"),
            count_by(FIRST, "OPSS-Shared-Basel:Risk Category L1", "FIRST losses by Basel category", size="half"),
            count_by(ORX, "OPSS-ORXLoss:Business Line", "ORX losses by business line", size="half"),
            count_by(LOSS, "OPSS-LossEv:Business Line", "Our losses by business line", size="half"),
            rooted(ORX, "External losses by entity", ["OPSS-Shared-Basel:Risk Category L1"], direct=True)]),
    report("ORM", "Treatments, causes and consequences",
           "How risks are being treated, and the causes and consequences recorded against them",
           ORM_COLOR, "How are we treating our risks, and what causes and consequences are recorded?",
           kpis(TREAT, [("Treatments", ""), ("In progress", f"[{TREAT}].[OPSS-Treat:Status] = 'In Progress'")]) +
           kpis(CAUSE, [("Causes", "")]) + kpis(CONSQ, [("Consequences", "")]) +
           [count_by(TREAT, "OPSS-Treat:Status", "Treatments by status", "pie", size="third"),
            count_by(TREAT, "OPSS-Treat:Treatment Type", "Treatment approach", "pie", size="third"),
            count_by(CAUSE, "OPSS-Cause:Cause Type", "Causes by type", size="third"),
            count_by(CONSQ, "OPSS-Consq:Consequence Type", "Consequences by type", size="half"),
            table_of("Treatments under each risk",
                     f"SELECT [{RSK}].[Name], [{TREAT}].[Name], [{TREAT}].[OPSS-Treat:Status] "
                     f"FROM [{RSK}] JOIN [{TREAT}] ON PARENT([{RSK}])"),
            rooted(TREAT, "Treatments by entity", ["OPSS-Treat:Status"])]),
]

# ---------- PCM: Policy and Compliance Management ----------

PCM_COLOR = "#1E7F4F"
PCM = [
    report("PCM", "Policy lifecycle",
           "Policies through approval and publishing, by type, department and revision reason",
           PCM_COLOR, "Where are our policies in their approval and publishing cycle?",
           kpis(POL, [("Policies", ""),
                      ("Published", f"[{POL}].[OPSS-Pol:Publishing Status] = 'Published Successfully'"),
                      ("In revision", f"[{POL}].[OPSS-Pol:Approval Status] = 'In Revision'"),
                      ("Awaiting approval", f"[{POL}].[OPSS-Pol:Approval Status] = 'Awaiting Approval'")]) +
           [count_by(POL, "OPSS-Pol:Approval Status", "Approval status", "pie", size="third"),
            count_by(POL, "OPSS-Pol:Publishing Status", "Publishing status", "pie", size="third"),
            count_by(POL, "OPSS-Pol:Type", "Policies by type", size="third"),
            count_by(POL, "OPSS-Pol:IssueDept", "Policies by issuing department", size="half"),
            count_by(POL, "OPSS-Pol:Revision Type", "Why policies were revised", size="half"),
            rooted(POL, "Policies by entity",
                   ["OPSS-Pol:Approval Status", "OPSS-Pol:Publishing Status", "OPSS-Pol:Type"], direct=True)],
           [filter_on("Approval status", POL, "OPSS-Pol:Approval Status")]),
    report("PCM", "Policy attestation campaigns",
           "Attestation campaigns and the attestations collected under them",
           PCM_COLOR, "How are our policy attestation campaigns going?",
           kpis(CAMP, [("Campaigns", ""), ("Open campaigns", f"[{CAMP}].[OPSS-Camp:Status] = 'Open'")]) +
           kpis(ATT, [("Attestations", ""), ("Completed", f"[{ATT}].[OPSS-Att:Status] = 'Completed'")]) +
           [count_by(CAMP, "OPSS-Camp:Status", "Campaigns by status", "pie", size="third"),
            count_by(ATT, "OPSS-Att:Status", "Attestations by status", "pie", size="third"),
            count_by(ATT, "OPSS-Att:Response", "Attestation responses", "pie", size="third"),
            table_of("Attestations under each campaign",
                     f"SELECT [{CAMP}].[Name], [{ATT}].[Name], [{ATT}].[OPSS-Att:Status], "
                     f"[{ATT}].[OPSS-Att:Response] FROM [{CAMP}] JOIN [{ATT}] ON ANCESTOR([{CAMP}])"),
            rooted(CAMP, "Campaigns by entity", ["OPSS-Camp:Status"])]),
    report("PCM", "Mandates and requirements",
           "The regulatory mandates we are held to and the requirements under them",
           PCM_COLOR, "What mandates apply to us and what requirements do they impose?",
           kpis(MAND, [("Mandates", "")]) + kpis(SMAND, [("Sub-mandates", "")]) +
           kpis(REQ, [("Requirements", ""), ("Met", f"[{REQ}].[OPSS-Req:Status] = 'Met'")]) +
           [count_by(MAND, "OPSS-Man:Status", "Mandates by status", "pie", size="third"),
            count_by(MAND, "OPSS-Man:Mandate Type", "Mandates by type", "pie", size="third"),
            count_by(REQ, "OPSS-Req:Status", "Requirements by status", size="third"),
            count_by(REQ, "OPSS-Req:Requirement Type", "Requirements by type", size="half"),
            table_of("Requirements under each mandate",
                     f"SELECT [{MAND}].[Name], [{REQ}].[Name], [{REQ}].[OPSS-Req:Status] "
                     f"FROM [{MAND}] JOIN [{REQ}] ON ANCESTOR([{MAND}])"),
            rooted(MAND, "Mandates by entity", ["OPSS-Man:Status", "OPSS-Man:Mandate Type"], direct=True)]),
    report("PCM", "Obligations",
           "Regulatory obligations by risk area and status, with their evaluations",
           PCM_COLOR, "What regulatory obligations do we carry and how are they assessed?",
           kpis(OBL, [("Obligations", ""), ("Active", f"[{OBL}].[OPSS-Obl:Status] = 'Active'")]) +
           kpis(OBLE, [("Obligation evaluations", ""),
                       ("Not met", f"[{OBLE}].[OPSS-OblEval:Conclusion] = 'Not Met'")]) +
           [count_by(OBL, "OPSS-Obl:Status", "Obligations by status", "pie", size="third"),
            count_by(OBL, "OPSS-Obl-DT:Functional Risk Area", "Obligations by risk area", size="third"),
            count_by(OBL, "OPSS-Obl:Obligation Type", "Obligations by type", "pie", size="third"),
            count_by(OBLE, "OPSS-OblEval:Conclusion", "Evaluation conclusions", size="half"),
            rooted(OBL, "Obligations by entity", ["OPSS-Obl:Status", "OPSS-Obl-DT:Functional Risk Area"])]),
    report("PCM", "Regulatory change",
           "Incoming regulatory change by status, impact and regulator",
           PCM_COLOR, "What regulatory change is coming and how will it affect us?",
           kpis(REGCH, [("Regulatory changes", ""),
                        ("Open", f"[{REGCH}].[OPSS-RegCh:Status] <> 'Closed'"),
                        ("High impact", f"[{REGCH}].[OPSS-RegCh:Impact] = 'High'")]) +
           kpis(REGL, [("Regulators", "")]) +
           [count_by(REGCH, "OPSS-RegCh:Status", "Changes by status", "pie", size="third"),
            count_by(REGCH, "OPSS-RegCh:Impact", "Changes by impact", "pie", size="third"),
            count_by(REGCH, "OPSS-RegCh:Change Type", "Changes by type", size="third"),
            count_by(REGAPP, "OPSS-RegApp:Applicability", "Applicability decisions", "pie", size="half"),
            rooted(REGCH, "Regulatory change by entity",
                   ["OPSS-RegCh:Status", "OPSS-RegCh:Impact", "Creation Date"], direct=True)],
           [filter_on("Change status", REGCH, "OPSS-RegCh:Status")]),
    report("PCM", "Regulatory tasks",
           "The tasks raised off regulatory change, by status, priority and owner",
           PCM_COLOR, "What regulatory tasks are outstanding?",
           kpis(REGTASK, [("Regulatory tasks", ""),
                          ("Open", f"[{REGTASK}].[OPSS-RegTask:Status] = 'Open'"),
                          ("High priority", f"[{REGTASK}].[OPSS-RegTask:Priority] = 'High'")]) +
           kpis(ACT, [("Action items", "")]) +
           [count_by(REGTASK, "OPSS-RegTask:Status", "Tasks by status", "pie", size="third"),
            count_by(REGTASK, "OPSS-RegTask:Priority", "Tasks by priority", "pie", size="third"),
            count_by(REGTASK, "OPSS-RegTask:Task Type", "Tasks by type", size="third"),
            table_of("Tasks under each regulatory change",
                     f"SELECT [{REGCH}].[Name], [{REGTASK}].[Name], [{REGTASK}].[OPSS-RegTask:Status], "
                     f"[{REGTASK}].[OPSS-RegTask:Priority] FROM [{REGCH}] JOIN [{REGTASK}] ON ANCESTOR([{REGCH}])"),
            rooted(REGTASK, "Tasks by entity", ["OPSS-RegTask:Status", "OPSS-RegTask:Priority"])]),
    report("PCM", "Regulator interactions",
           "Dealings with regulators, by type, status and regulator",
           PCM_COLOR, "What interactions have we had with our regulators?",
           kpis("RegulatorInteraction", [("Interactions", ""),
                                         ("Open", "[RegulatorInteraction].[OPSS-RegInt:Status] = 'Open'")]) +
           kpis(REGL, [("Regulators", "")]) + kpis(REGI, [("Regulatory initiatives", "")]) +
           [count_by("RegulatorInteraction", "OPSS-RegInt:Status", "Interactions by status", "pie", size="third"),
            count_by("RegulatorInteraction", "OPSS-RegInt:Interaction Type", "Interactions by type", size="third"),
            count_by(REGL, "OPSS-Regl:Regulator Type", "Regulators by type", "pie", size="third"),
            rooted("RegulatorInteraction", "Interactions by entity", ["OPSS-RegInt:Status"])]),
    report("PCM", "Procedures",
           "The procedures that put policies into practice, by status and owner",
           PCM_COLOR, "Which procedures support our policies, and are they current?",
           kpis(PRCD, [("Procedures", ""),
                       ("Approved", f"[{PRCD}].[OPSS-Prcd:Approval Status] = 'Approved'"),
                       ("In revision", f"[{PRCD}].[OPSS-Prcd:Approval Status] = 'In Revision'")]) +
           kpis(POL, [("Policies", "")]) +
           [count_by(PRCD, "OPSS-Prcd:Approval Status", "Procedures by approval status", "pie", size="third"),
            count_by(PRCD, "OPSS-Prcd:Type", "Procedures by type", "pie", size="third"),
            count_by(PRCD, "OPSS-Prcd:Status", "Procedures by status", size="third"),
            table_of("Procedures under each policy",
                     f"SELECT [{POL}].[Name], [{PRCD}].[Name], [{PRCD}].[OPSS-Prcd:Approval Status] "
                     f"FROM [{POL}] JOIN [{PRCD}] ON ANCESTOR([{POL}])"),
            rooted(PRCD, "Procedures by entity", ["OPSS-Prcd:Approval Status"])]),
    report("PCM", "Compliance controls",
           "Controls that evidence compliance, their effectiveness and the issues against them",
           PCM_COLOR, "How effective are the controls behind our compliance obligations?",
           kpis(CTL, [("Controls", ""),
                      ("Ineffective", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'")]) +
           kpis(CEVAL, [("Control evaluations", "")]) +
           kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'")]) +
           [count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Operating effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Design Effectiveness", "Design effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Type", "Controls by type", size="third"),
            count_by(CEVAL, "OPSS-CtlEval:Operating Effectiveness", "Evaluated effectiveness", size="half"),
            rooted(CTL, "Controls by entity",
                   ["OPSS-Ctl:Operating Effectiveness", "OPSS-Ctl:Control Type"])]),
    report("PCM", "Waivers and exceptions",
           "Approved exceptions to policy, by status, type and expiry",
           PCM_COLOR, "What policy waivers are in force and when do they expire?",
           kpis(WAIV, [("Waivers", ""), ("Approved", f"[{WAIV}].[OPSS-Waiv:Status] = 'Approved'"),
                       ("Expired", f"[{WAIV}].[OPSS-Waiv:Status] = 'Expired'"),
                       ("Awaiting approval", f"[{WAIV}].[OPSS-Waiv:Status] = 'Awaiting Approval'")]) +
           [count_by(WAIV, "OPSS-Waiv:Status", "Waivers by status", "pie", size="third"),
            count_by(WAIV, "OPSS-Waiv:Waiver Type", "Waivers by type", "pie", size="third"),
            count_by(WAIV, "OPSS-Waiv:Reason", "Why waivers were granted", size="third"),
            rooted(WAIV, "Waivers by entity",
                   ["OPSS-Waiv:Status", "OPSS-Waiv:Waiver Type", "OPSS-Waiv:Expiration Date"])],
           [filter_on("Expires", WAIV, "OPSS-Waiv:Expiration Date", "date")]),
]

# ---------- MRG: Model Risk Governance ----------

MRG_COLOR = "#3A0CA3"
MRG = [
    report("MRG", "Model inventory",
           "Every model, by tier, status and use, under the entity that owns it",
           MRG_COLOR, "Show our model inventory by business entity",
           kpis(MODEL, [("Models", ""), ("In production", f"[{MODEL}].[OPSS-Mdl:Status] = 'In Production'"),
                        ("High tier", f"[{MODEL}].[OPSS-Mdl:Model Tier] = 'Tier 1'"),
                        ("Retired", f"[{MODEL}].[OPSS-Mdl:Status] = 'Retired'")]) +
           [count_by(MODEL, "OPSS-Mdl:Status", "Models by status", "pie", size="third"),
            count_by(MODEL, "OPSS-Mdl:Model Tier", "Models by tier", "pie", size="third"),
            count_by(MODEL, "OPSS-Mdl:Model Type", "Models by type", size="third"),
            count_by(MODEL, "OPSS-Mdl:Risk Rating", "Models by risk rating", size="half"),
            rooted(MODEL, "Models by entity",
                   ["OPSS-Mdl:Status", "OPSS-Mdl:Model Tier", "OPSS-Mdl:Risk Rating"], direct=True)],
           [filter_on("Model tier", MODEL, "OPSS-Mdl:Model Tier")]),
    report("MRG", "Model risk scorecards",
           "Scorecards against each model, by rating and status",
           MRG_COLOR, "How do our models score on risk?",
           kpis(MSCORE, [("Scorecards", ""), ("Approved", f"[{MSCORE}].[OPSS-MdlScore:Status] = 'Approved'")]) +
           kpis(MODEL, [("Models", ""), ("High tier models", f"[{MODEL}].[OPSS-Mdl:Model Tier] = 'Tier 1'")]) +
           [count_by(MSCORE, "OPSS-MdlScore:Status", "Scorecards by status", "pie", size="third"),
            count_by(MSCORE, "OPSS-MdlScore:Overall Rating", "Scorecards by rating", "pie", size="third"),
            count_by(MODEL, "OPSS-Mdl:Risk Rating", "Models by risk rating", size="third"),
            table_of("Scorecards under each model",
                     f"SELECT [{MODEL}].[Name], [{MSCORE}].[Name], [{MSCORE}].[OPSS-MdlScore:Overall Rating], "
                     f"[{MSCORE}].[OPSS-MdlScore:Status] FROM [{MODEL}] JOIN [{MSCORE}] ON PARENT([{MODEL}])"),
            rooted(MSCORE, "Scorecards by entity", ["OPSS-MdlScore:Overall Rating"])]),
    report("MRG", "Model validation reviews",
           "Validation and periodic reviews, by status, outcome and reviewer",
           MRG_COLOR, "Where do our model validation reviews stand?",
           kpis(REVIEW, [("Reviews", ""), ("Open", f"[{REVIEW}].[OPSS-Rev:Status] <> 'Closed'"),
                         ("Completed", f"[{REVIEW}].[OPSS-Rev:Status] = 'Completed'")]) +
           kpis(CHAL, [("Challenges raised", "")]) +
           [count_by(REVIEW, "OPSS-Rev:Status", "Reviews by status", "pie", size="third"),
            count_by(REVIEW, "OPSS-Rev:Review Type", "Reviews by type", "pie", size="third"),
            count_by(REVIEW, "OPSS-Rev:Outcome", "Review outcomes", size="third"),
            table_of("Reviews against each model",
                     f"SELECT [{MODEL}].[Name], [{REVIEW}].[Name], [{REVIEW}].[OPSS-Rev:Status], "
                     f"[{REVIEW}].[OPSS-Rev:Outcome] FROM [{MODEL}] JOIN [{REVIEW}] ON ANCESTOR([{MODEL}])"),
            rooted(REVIEW, "Reviews by entity", ["OPSS-Rev:Status", "OPSS-Rev:Outcome"])]),
    report("MRG", "Challenges",
           "Challenges raised against models and reviews, by status and severity",
           MRG_COLOR, "What challenges have been raised against our models?",
           kpis(CHAL, [("Challenges", ""), ("Open", f"[{CHAL}].[OPSS-Chal:Status] = 'Open'"),
                       ("High severity", f"[{CHAL}].[OPSS-Chal:Severity] = 'High'"),
                       ("Resolved", f"[{CHAL}].[OPSS-Chal:Status] = 'Resolved'")]) +
           [count_by(CHAL, "OPSS-Chal:Status", "Challenges by status", "pie", size="third"),
            count_by(CHAL, "OPSS-Chal:Severity", "Challenges by severity", "pie", size="third"),
            count_by(CHAL, "OPSS-Chal:Challenge Type", "Challenges by type", size="third"),
            table_of("Challenges under each review",
                     f"SELECT [{REVIEW}].[Name], [{CHAL}].[Name], [{CHAL}].[OPSS-Chal:Status], "
                     f"[{CHAL}].[OPSS-Chal:Severity] FROM [{REVIEW}] JOIN [{CHAL}] ON PARENT([{REVIEW}])"),
            rooted(CHAL, "Challenges by entity", ["OPSS-Chal:Status", "OPSS-Chal:Severity"])]),
    report("MRG", "Model change requests",
           "Requested changes to models, by status, type and urgency",
           MRG_COLOR, "What changes have been requested to our models?",
           kpis(CHG, [("Change requests", ""), ("Open", f"[{CHG}].[OPSS-ChgReq:Status] = 'Open'"),
                      ("Approved", f"[{CHG}].[OPSS-ChgReq:Status] = 'Approved'"),
                      ("Rejected", f"[{CHG}].[OPSS-ChgReq:Status] = 'Rejected'")]) +
           [count_by(CHG, "OPSS-ChgReq:Status", "Change requests by status", "pie", size="third"),
            count_by(CHG, "OPSS-ChgReq:Change Type", "Changes by type", "pie", size="third"),
            count_by(CHG, "OPSS-ChgReq:Priority", "Changes by priority", size="third"),
            table_of("Change requests against each model",
                     f"SELECT [{MODEL}].[Name], [{CHG}].[Name], [{CHG}].[OPSS-ChgReq:Status], "
                     f"[{CHG}].[OPSS-ChgReq:Change Type] FROM [{MODEL}] JOIN [{CHG}] ON ANCESTOR([{MODEL}])"),
            rooted(CHG, "Change requests by entity", ["OPSS-ChgReq:Status"])]),
    report("MRG", "Model inputs, outputs and lineage",
           "What each model consumes and produces, and how models feed each other",
           MRG_COLOR, "What do our models consume and produce, and how are they linked?",
           kpis(MIN, [("Model inputs", "")]) + kpis(MOUT, [("Model outputs", "")]) +
           kpis(MLINK, [("Model links", "")]) + kpis(MODEL, [("Models", "")]) +
           [count_by(MIN, "OPSS-MdlIn:Input Type", "Inputs by type", "pie", size="third"),
            count_by(MOUT, "OPSS-MdlOut:Output Type", "Outputs by type", "pie", size="third"),
            count_by(MLINK, "OPSS-MdlLink:Link Type", "Links by type", size="third"),
            table_of("Inputs of each model",
                     f"SELECT [{MODEL}].[Name], [{MIN}].[Name], [{MIN}].[OPSS-MdlIn:Input Type] "
                     f"FROM [{MODEL}] JOIN [{MIN}] ON PARENT([{MODEL}])"),
            table_of("Outputs of each model",
                     f"SELECT [{MODEL}].[Name], [{MOUT}].[Name], [{MOUT}].[OPSS-MdlOut:Output Type] "
                     f"FROM [{MODEL}] JOIN [{MOUT}] ON PARENT([{MODEL}])"),
            rooted(MODEL, "Models by entity", ["OPSS-Mdl:Model Tier", "OPSS-Mdl:Status"], direct=True)]),
    report("MRG", "Model attestations",
           "Periodic attestations that models are still fit for use",
           MRG_COLOR, "Which model owners have attested, and which have not?",
           kpis(MATT, [("Attestations", ""), ("Completed", f"[{MATT}].[OPSS-MdlAtt:Status] = 'Completed'"),
                       ("Outstanding", f"[{MATT}].[OPSS-MdlAtt:Status] <> 'Completed'")]) +
           kpis(MODEL, [("Models", "")]) +
           [count_by(MATT, "OPSS-MdlAtt:Status", "Attestations by status", "pie", size="third"),
            count_by(MATT, "OPSS-MdlAtt:Response", "Attestation responses", "pie", size="third"),
            count_by(MODEL, "OPSS-Mdl:Model Tier", "Models by tier", size="third"),
            table_of("Attestations against each model",
                     f"SELECT [{MODEL}].[Name], [{MATT}].[Name], [{MATT}].[OPSS-MdlAtt:Status] "
                     f"FROM [{MODEL}] JOIN [{MATT}] ON ANCESTOR([{MODEL}])"),
            rooted(MATT, "Attestations by entity", ["OPSS-MdlAtt:Status"])]),
    report("MRG", "Committee oversight",
           "The committees governing models, and what they have in front of them",
           MRG_COLOR, "What model risk work is in front of our committees?",
           kpis(CMTE, [("Committees", ""), ("Active", f"[{CMTE}].[OPSS-Cmte:Status] = 'Active'")]) +
           kpis(REVIEW, [("Reviews", "")]) + kpis(CHAL, [("Open challenges", f"[{CHAL}].[OPSS-Chal:Status] = 'Open'")]) +
           [count_by(CMTE, "OPSS-Cmte:Status", "Committees by status", "pie", size="third"),
            count_by(CMTE, "OPSS-Cmte:Committee Type", "Committees by type", "pie", size="third"),
            count_by(REVIEW, "OPSS-Rev:Status", "Reviews awaiting a decision", size="third"),
            rooted(CMTE, "Committees by entity", ["OPSS-Cmte:Status", "OPSS-Cmte:Committee Type"])]),
    report("MRG", "Model performance metrics",
           "The metrics tracked against models and the readings behind them",
           MRG_COLOR, "How are our models performing against their metrics?",
           kpis(METRIC, [("Metrics", ""), ("Breaching", f"[{METRIC}].[OPSS-Metr:Breach Status] <> 'Within Threshold'")]) +
           kpis(METV, [("Metric readings", "")]) + kpis(MODEL, [("Models", "")]) +
           [count_by(METRIC, "OPSS-Metr:Breach Status", "Metrics by breach status", "pie", size="third"),
            count_by(METRIC, "OPSS-Metr:Trend", "Metric trend", "pie", size="third"),
            count_by(METRIC, "OPSS-Metr:Frequency", "Collection frequency", size="third"),
            table_of("Readings under each metric",
                     f"SELECT [{METRIC}].[Name], [{METV}].[Name], [{METV}].[OPSS-MetrVal:Value], "
                     f"[{METV}].[OPSS-MetrVal:Period] FROM [{METRIC}] JOIN [{METV}] ON PARENT([{METRIC}])"),
            rooted(METRIC, "Metrics by entity", ["OPSS-Metr:Breach Status", "OPSS-Metr:Trend"])]),
    report("MRG", "Model issues and actions",
           "Issues raised against models and the action items closing them",
           MRG_COLOR, "What issues are open against our models?",
           kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
                      ("High priority", f"[{ISS}].[OPSS-Iss:Priority] = 'High'")]) +
           kpis(ACT, [("Open actions", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'")]) +
           kpis(MODEL, [("Models", "")]) +
           [count_by(ISS, "OPSS-Iss:Status", "Issues by status", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="third"),
            count_by(ACT, "OPSS-ActItem:Status", "Actions by status", size="third"),
            table_of("Issues against each model",
                     f"SELECT [{MODEL}].[Name], [{ISS}].[Name], [{ISS}].[OPSS-Iss:Status], "
                     f"[{ISS}].[OPSS-Iss:Priority] FROM [{MODEL}] JOIN [{ISS}] ON ANCESTOR([{MODEL}])"),
            rooted(ISS, "Issues by entity", ["OPSS-Iss:Status", "OPSS-Iss:Priority"])]),
]

# ---------- IAM: Internal Audit Management ----------

IAM_COLOR = "#2A9D8F"
IAM = [
    report("IAM", "Audit universe",
           "The auditable entities we could audit, their risk rating and when they were last covered",
           IAM_COLOR, "What is in our audit universe and how risky is it?",
           kpis(AUDE, [("Auditable entities", ""),
                       ("High risk", f"[{AUDE}].[OPSS-AudEnt:Risk Rating] = 'High'"),
                       ("In scope", f"[{AUDE}].[OPSS-AudEnt:Status] = 'Active'")]) +
           kpis(AUD, [("Audits", "")]) +
           [count_by(AUDE, "OPSS-AudEnt:Risk Rating", "Entities by risk rating", "pie", size="third"),
            count_by(AUDE, "OPSS-AudEnt:Status", "Entities by status", "pie", size="third"),
            count_by(AUDE, "OPSS-AudEnt:Entity Type", "Entities by type", size="third"),
            table_of("Audits against each auditable entity",
                     f"SELECT [{AUDE}].[Name], [{AUD}].[Name], [{AUD}].[OPSS-Aud:Status], "
                     f"[{AUD}].[OPSS-Aud:Result] FROM [{AUDE}] JOIN [{AUD}] ON PARENT([{AUDE}])"),
            rooted(AUDE, "Auditable entities by business entity",
                   ["OPSS-AudEnt:Risk Rating", "OPSS-AudEnt:Status"], direct=True)],
           [filter_on("Risk rating", AUDE, "OPSS-AudEnt:Risk Rating")]),
    report("IAM", "Audit plan",
           "The planned audit programme, by commitment year, type and status",
           IAM_COLOR, "What is on our audit plan and how much of it has started?",
           kpis(AUD, [("Audits", ""), ("Planned", f"[{AUD}].[OPSS-Aud:Status] IN ('Planned', 'Not Started')"),
                      ("In progress", f"[{AUD}].[OPSS-Aud:Status] IN ('In Progress', 'In Review')"),
                      ("Completed", f"[{AUD}].[OPSS-Aud:Status] = 'Completed'")]) +
           [count_by(AUD, "OPSS-Aud:Status", "Audits by status", "pie", size="third"),
            count_by(AUD, "OPSS-Aud:Type", "Audits by type", "pie", size="third"),
            count_by(AUD, "OPSS-Aud:Audit Commitment", "Audits by commitment year", size="third",
                     by_value=True),
            count_by(SPLAN, "OPSS-SumPlan:Status", "Summary audit plans by status", size="half"),
            rooted(AUD, "Audits by entity", ["OPSS-Aud:Status", "OPSS-Aud:Type", "OPSS-Aud:Result"])],
           [filter_on("Audit type", AUD, "OPSS-Aud:Type")]),
    report("IAM", "Audit execution",
           "Audits in flight, their phases and the workpapers under them",
           IAM_COLOR, "How are our audits progressing through their phases?",
           kpis(AUD, [("Audits in progress", f"[{AUD}].[OPSS-Aud:Status] IN ('In Progress', 'In Review')")]) +
           kpis(APHASE, [("Audit phases", "")]) + kpis(WP, [("Workpapers", "")]) +
           kpis(FND, [("Findings", "")]) +
           [count_by(APHASE, "OPSS-AudPh:Status", "Phases by status", "pie", size="third"),
            count_by(APHASE, "OPSS-AudPh:Phase Type", "Phases by type", "pie", size="third"),
            count_by(WP, "OPSS-WP:Status", "Workpapers by status", size="third"),
            table_of("Phases under each audit",
                     f"SELECT [{AUD}].[Name], [{APHASE}].[Name], [{APHASE}].[OPSS-AudPh:Status] "
                     f"FROM [{AUD}] JOIN [{APHASE}] ON PARENT([{AUD}])"),
            rooted(AUD, "Audits in flight by entity", ["OPSS-Aud:Status", "OPSS-Aud:Type"])]),
    report("IAM", "Audit findings",
           "Findings by priority, impact and management response",
           IAM_COLOR, "Summarise our audit findings and management responses",
           kpis(FND, [("Findings", ""), ("Open", f"[{FND}].[OPSS-Finding:Status] = 'Open'"),
                      ("High priority open", f"[{FND}].[OPSS-Finding:Status] = 'Open' "
                                             f"AND [{FND}].[OPSS-Finding:Priority] = 'High'"),
                      ("Awaiting response", f"[{FND}].[OPSS-Finding:MgmtRespStat] = 'Waiting for Response'")]) +
           [count_by(FND, "OPSS-Finding:Priority", "Findings by priority", "pie", size="third"),
            count_by(FND, "OPSS-Finding:Impact", "Findings by impact", "pie", size="third"),
            count_by(FND, "OPSS-Finding:Status", "Open and closed", "pie", size="third"),
            count_by(FND, "OPSS-Finding:MgmtResp", "Management responses", size="half"),
            count_by_two(FND, "OPSS-Finding:Priority", "OPSS-Finding:Status",
                         "Priority by status", size="half"),
            rooted(FND, "Findings by entity", ["OPSS-Finding:Status", "OPSS-Finding:Priority"])],
           [filter_on("Finding priority", FND, "OPSS-Finding:Priority")]),
    report("IAM", "Workpapers and evidence",
           "Workpapers by status and type, and the findings raised off them",
           IAM_COLOR, "What evidence has been gathered, and what did it find?",
           kpis(WP, [("Workpapers", ""), ("Open", f"[{WP}].[OPSS-WP:Status] <> 'Closed'"),
                     ("Reviewed", f"[{WP}].[OPSS-WP:Status] = 'Reviewed'")]) +
           kpis(FND, [("Findings raised", "")]) +
           [count_by(WP, "OPSS-WP:Status", "Workpapers by status", "pie", size="third"),
            count_by(WP, "OPSS-WP:Workpaper Type", "Workpapers by type", "pie", size="third"),
            count_by(RCMT, "OPSS-RevCmt:Status", "Review comments by status", size="third"),
            table_of("Findings under each workpaper",
                     f"SELECT [{WP}].[Name], [{FND}].[Name], [{FND}].[OPSS-Finding:Priority], "
                     f"[{FND}].[OPSS-Finding:Status] FROM [{WP}] JOIN [{FND}] ON PARENT([{WP}])"),
            rooted(WP, "Workpapers by entity", ["OPSS-WP:Status"])]),
    report("IAM", "Auditor workload",
           "Auditors, what they are assigned and the time booked against it",
           IAM_COLOR, "How is work spread across our auditors?",
           kpis(AUDR, [("Auditors", ""), ("Active", f"[{AUDR}].[OPSS-Audr:Status] = 'Active'")]) +
           kpis(TSHEET, [("Timesheets", "")]) + kpis(AUD, [("Audits", "")]) +
           [count_by(AUDR, "OPSS-Audr:Status", "Auditors by status", "pie", size="third"),
            count_by(AUDR, "OPSS-Audr:Role", "Auditors by role", "pie", size="third"),
            count_by(TSHEET, "OPSS-TSheet:Status", "Timesheets by status", size="third"),
            table_of("Timesheets under each plan",
                     f"SELECT [{PLAN}].[Name], [{TSHEET}].[Name], [{TSHEET}].[OPSS-TSheet:Status], "
                     f"[{TSHEET}].[OPSS-TSheet:Hours] FROM [{PLAN}] JOIN [{TSHEET}] ON PARENT([{PLAN}])"),
            rooted(AUDR, "Auditors by entity", ["OPSS-Audr:Status", "OPSS-Audr:Role"], direct=True)]),
    report("IAM", "Review comments",
           "Supervisory review comments on audit work, by status and raiser",
           IAM_COLOR, "What review comments are outstanding on our audit work?",
           kpis(RCMT, [("Review comments", ""), ("Open", f"[{RCMT}].[OPSS-RevCmt:Status] = 'Open'"),
                       ("Closed", f"[{RCMT}].[OPSS-RevCmt:Status] = 'Closed'")]) +
           kpis(WP, [("Workpapers", "")]) +
           [count_by(RCMT, "OPSS-RevCmt:Status", "Comments by status", "pie", size="third"),
            count_by(RCMT, "OPSS-RevCmt:Comment Type", "Comments by type", "pie", size="third"),
            count_by(RCMT, "OPSS-RevCmt:Priority", "Comments by priority", size="third"),
            table_of("Comments under each workpaper",
                     f"SELECT [{WP}].[Name], [{RCMT}].[Name], [{RCMT}].[OPSS-RevCmt:Status] "
                     f"FROM [{WP}] JOIN [{RCMT}] ON PARENT([{WP}])"),
            rooted(RCMT, "Review comments by entity", ["OPSS-RevCmt:Status"])]),
    report("IAM", "Audit issues and actions",
           "Issues raised by audit and the management actions closing them",
           IAM_COLOR, "What has audit raised, and is it being fixed?",
           kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
                      ("Material weaknesses", f"[{ISS}].[OPSS-Iss:Conclusion] = 'Material Weakness'")]) +
           kpis(ACT, [("Open actions", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'"),
                      ("Awaiting approval", f"[{ACT}].[OPSS-ActItem:Status] = 'Awaiting Approval'")]) +
           [count_by(ISS, "OPSS-Iss:Status", "Issues by status", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Issue Type", "Issues by type", size="third"),
            count_by(ACT, "OPSS-ActItem:Status", "Actions by status", "pie", size="third"),
            table_of("Actions under each issue",
                     f"SELECT [{ISS}].[Name], [{ACT}].[Name], [{ACT}].[OPSS-ActItem:Status], "
                     f"[{ACT}].[OPSS-ActItem:Due Date] FROM [{ISS}] JOIN [{ACT}] ON PARENT([{ISS}])"),
            rooted(ACT, "Actions by entity", ["OPSS-ActItem:Status", "OPSS-ActItem:Due Date"])],
           [filter_on("Action due", ACT, "OPSS-ActItem:Due Date", "date")]),
    report("IAM", "Control testing in audits",
           "The controls audit tested, and how they held up",
           IAM_COLOR, "Which controls did audit test, and did they pass?",
           kpis(TEST, [("Test plans", "")]) +
           kpis(TRES, [("Test results", ""), ("Failed", f"[{TRES}].[OPSS-TestRes:Conclusion] = 'Fail'")]) +
           kpis(CTL, [("Controls", "")]) +
           [count_by(TRES, "OPSS-TestRes:Conclusion", "Results by conclusion", "pie", size="third"),
            count_by(TEST, "OPSS-Test:Status", "Tests by status", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Control effectiveness", size="third"),
            table_of("Results under each test",
                     f"SELECT [{TEST}].[Name], [{TRES}].[Name], [{TRES}].[OPSS-TestRes:Conclusion] "
                     f"FROM [{TEST}] JOIN [{TRES}] ON PARENT([{TEST}])"),
            rooted(TEST, "Tests by entity", ["OPSS-Test:Status"])]),
    report("IAM", "Audit results by entity",
           "Audit coverage and outcomes across the business entity hierarchy",
           IAM_COLOR, "Which parts of the business have been audited, and with what result?",
           kpis(AUD, [("Audits", ""), ("Completed", f"[{AUD}].[OPSS-Aud:Status] = 'Completed'")]) +
           kpis(FND, [("Findings", ""), ("Open findings", f"[{FND}].[OPSS-Finding:Status] = 'Open'")]) +
           [count_by(ENT, "OPSS-Ent:Country", "Entities by country", size="half"),
            count_by(AUD, "OPSS-Aud:Result", "Audit results", "pie", size="half"),
            count_by_two(AUD, "OPSS-Aud:Type", "OPSS-Aud:Result", "Result by audit type", size="half"),
            rooted(AUD, "Audits by entity", ["OPSS-Aud:Status", "OPSS-Aud:Result"]),
            table_of("Findings per audit",
                     f"SELECT [{AUD}].[Name], [{AUD}].[OPSS-Aud:Type], [{FND}].[Name], "
                     f"[{FND}].[OPSS-Finding:Status] FROM [{AUD}] JOIN [{FND}] ON ANCESTOR([{AUD}])")]),
]

# ---------- ITG: IT Governance ----------

ITG_COLOR = "#0F62FE"
ITG = [
    report("ITG", "IT asset inventory",
           "Systems and assets by type, criticality and status, under the entity that owns them",
           ITG_COLOR, "What IT assets do we have and how critical are they?",
           kpis(RES, [("Assets", ""), ("Critical", f"[{RES}].[OPSS-Res:Criticality] = 'High'"),
                      ("Active", f"[{RES}].[OPSS-Res:Status] = 'Active'"),
                      ("Decommissioned", f"[{RES}].[OPSS-Res:Status] = 'Decommissioned'")]) +
           [count_by(RES, "OPSS-Res:Resource Type", "Assets by type", "pie", size="third"),
            count_by(RES, "OPSS-Res:Criticality", "Assets by criticality", "pie", size="third"),
            count_by(RES, "OPSS-Res:Status", "Assets by status", size="third"),
            count_by(RES, "OPSS-Res:Classification", "Assets by data classification", size="half"),
            rooted(RES, "Assets by entity",
                   ["OPSS-Res:Resource Type", "OPSS-Res:Criticality", "OPSS-Res:Status"], direct=True)],
           [filter_on("Criticality", RES, "OPSS-Res:Criticality")]),
    report("ITG", "Asset relationships",
           "How assets depend on each other, and which dependencies are critical",
           ITG_COLOR, "How do our IT assets depend on each other?",
           kpis(RLINK, [("Asset links", "")]) + kpis(RES, [("Assets", "")]) +
           kpis(RES, [("Critical assets", f"[{RES}].[OPSS-Res:Criticality] = 'High'")]) +
           kpis(INC, [("Incidents", "")]) +
           [count_by(RLINK, "OPSS-ResLink:Link Type", "Links by type", "pie", size="third"),
            count_by(RLINK, "OPSS-ResLink:Criticality", "Links by criticality", "pie", size="third"),
            count_by(RES, "OPSS-Res:Resource Type", "Assets by type", size="third"),
            table_of("Links from each asset",
                     f"SELECT [{RES}].[Name], [{RLINK}].[Name], [{RLINK}].[OPSS-ResLink:Link Type] "
                     f"FROM [{RES}] JOIN [{RLINK}] ON PARENT([{RES}])"),
            rooted(RLINK, "Asset links by entity", ["OPSS-ResLink:Link Type"])]),
    report("ITG", "Threats",
           "The threat landscape, by category, likelihood and the assets exposed",
           ITG_COLOR, "What threats are recorded against our IT estate?",
           kpis(THR, [("Threats", ""), ("Active", f"[{THR}].[OPSS-Thr:Status] = 'Active'"),
                      ("High likelihood", f"[{THR}].[OPSS-Thr:Likelihood] = 'High'")]) +
           kpis(RES, [("Assets", "")]) +
           [count_by(THR, "OPSS-Thr:Threat Category", "Threats by category", size="half"),
            count_by(THR, "OPSS-Thr:Likelihood", "Threats by likelihood", "pie", size="third"),
            count_by(THR, "OPSS-Thr:Status", "Threats by status", "pie", size="third"),
            count_by_two(THR, "OPSS-Thr:Likelihood", "OPSS-Thr:Impact", "Likelihood by impact", size="half"),
            rooted(THR, "Threats by entity", ["OPSS-Thr:Threat Category", "OPSS-Thr:Likelihood"])]),
    report("ITG", "Vulnerabilities",
           "Open vulnerabilities by severity and status, and what they affect",
           ITG_COLOR, "What vulnerabilities are open, and how severe are they?",
           kpis(VUL, [("Vulnerabilities", ""), ("Open", f"[{VUL}].[OPSS-Vul:Status] = 'Open'"),
                      ("Critical", f"[{VUL}].[OPSS-Vul:Severity] = 'Critical'"),
                      ("Remediated", f"[{VUL}].[OPSS-Vul:Status] = 'Remediated'")]) +
           [count_by(VUL, "OPSS-Vul:Severity", "Vulnerabilities by severity", "pie", size="third"),
            count_by(VUL, "OPSS-Vul:Status", "Vulnerabilities by status", "pie", size="third"),
            count_by(VUL, "OPSS-Vul:Vulnerability Type", "Vulnerabilities by type", size="third"),
            count_by_two(VUL, "OPSS-Vul:Severity", "OPSS-Vul:Status", "Severity by status", size="half"),
            rooted(VUL, "Vulnerabilities by entity",
                   ["OPSS-Vul:Severity", "OPSS-Vul:Status", "Creation Date"])],
           [filter_on("Severity", VUL, "OPSS-Vul:Severity")]),
    report("ITG", "IT incidents",
           "Incidents by severity, type and status, with what caused them",
           ITG_COLOR, "What IT incidents have we had and how severe were they?",
           kpis(INC, [("Incidents", ""), ("Open", f"[{INC}].[OPSS-Inc:Status] = 'Open'"),
                      ("High severity", f"[{INC}].[OPSS-Inc:Severity] = 'High'"),
                      ("Closed", f"[{INC}].[OPSS-Inc:Status] = 'Closed'")]) +
           [count_by(INC, "OPSS-Inc:Severity", "Incidents by severity", "pie", size="third"),
            count_by(INC, "OPSS-Inc:Status", "Incidents by status", "pie", size="third"),
            count_by(INC, "OPSS-Inc:Incident Type", "Incidents by type", size="third"),
            count_by(INC, "OPSS-Inc:Root Cause", "Incidents by root cause", size="half"),
            rooted(INC, "Incidents by entity",
                   ["OPSS-Inc:Severity", "OPSS-Inc:Status", "Creation Date"], direct=True)],
           [filter_on("Raised", INC, "Creation Date", "date")]),
    report("ITG", "Baselines and configuration compliance",
           "Configuration baselines and how far assets conform to them",
           ITG_COLOR, "Are our systems configured to their baselines?",
           kpis(BASE, [("Baselines", ""), ("Approved", f"[{BASE}].[OPSS-Base:Status] = 'Approved'"),
                       ("Draft", f"[{BASE}].[OPSS-Base:Status] = 'Draft'")]) +
           kpis(RES, [("Assets", "")]) +
           [count_by(BASE, "OPSS-Base:Status", "Baselines by status", "pie", size="third"),
            count_by(BASE, "OPSS-Base:Baseline Type", "Baselines by type", "pie", size="third"),
            count_by(BASE, "OPSS-Base:Compliance Status", "Conformance", size="third"),
            table_of("Baselines against each asset",
                     f"SELECT [{RES}].[Name], [{BASE}].[Name], [{BASE}].[OPSS-Base:Status] "
                     f"FROM [{RES}] JOIN [{BASE}] ON ANCESTOR([{RES}])"),
            rooted(BASE, "Baselines by entity", ["OPSS-Base:Status"])]),
    report("ITG", "IT controls",
           "The controls over IT, their effectiveness and how they were tested",
           ITG_COLOR, "How effective are our IT controls?",
           kpis(CTL, [("Controls", ""),
                      ("Ineffective", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'"),
                      ("Key controls", f"[{CTL}].[OPSS-Ctl:Classification] = 'Key Control Activity'")]) +
           kpis(CTLOBJ, [("Control objectives", "")]) +
           [count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Operating effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Design Effectiveness", "Design effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Method", "Automated or manual", "pie", size="third"),
            count_by(CEVAL, "OPSS-CtlEval:Operating Effectiveness", "Evaluated effectiveness", size="half"),
            rooted(CTL, "Controls by entity",
                   ["OPSS-Ctl:Operating Effectiveness", "OPSS-Ctl:Control Method"])]),
    report("ITG", "Exceptions and waivers",
           "Approved exceptions to IT policy and when they run out",
           ITG_COLOR, "What IT policy exceptions are in force?",
           kpis(WAIV, [("Waivers", ""), ("Approved", f"[{WAIV}].[OPSS-Waiv:Status] = 'Approved'"),
                       ("Expired", f"[{WAIV}].[OPSS-Waiv:Status] = 'Expired'")]) +
           kpis(VUL, [("Open vulnerabilities", f"[{VUL}].[OPSS-Vul:Status] = 'Open'")]) +
           [count_by(WAIV, "OPSS-Waiv:Status", "Waivers by status", "pie", size="third"),
            count_by(WAIV, "OPSS-Waiv:Waiver Type", "Waivers by type", "pie", size="third"),
            count_by(WAIV, "OPSS-Waiv:Reason", "Why waivers were granted", size="third"),
            rooted(WAIV, "Waivers by entity",
                   ["OPSS-Waiv:Status", "OPSS-Waiv:Expiration Date"])],
           [filter_on("Expires", WAIV, "OPSS-Waiv:Expiration Date", "date")]),
    report("ITG", "IT policies and procedures",
           "The IT policy set, its approval state and the procedures beneath it",
           ITG_COLOR, "Are our IT policies and procedures current?",
           kpis(POL, [("Policies", ""),
                      ("Published", f"[{POL}].[OPSS-Pol:Publishing Status] = 'Published Successfully'")]) +
           kpis(PRCD, [("Procedures", ""),
                       ("Approved", f"[{PRCD}].[OPSS-Prcd:Approval Status] = 'Approved'")]) +
           [count_by(POL, "OPSS-Pol:Approval Status", "Policy approval status", "pie", size="third"),
            count_by(POL, "OPSS-Pol:Type", "Policies by type", "pie", size="third"),
            count_by(PRCD, "OPSS-Prcd:Approval Status", "Procedure approval status", size="third"),
            table_of("Procedures under each policy",
                     f"SELECT [{POL}].[Name], [{PRCD}].[Name], [{PRCD}].[OPSS-Prcd:Approval Status] "
                     f"FROM [{POL}] JOIN [{PRCD}] ON ANCESTOR([{POL}])"),
            rooted(POL, "Policies by entity", ["OPSS-Pol:Approval Status"], direct=True)]),
    report("ITG", "IT risk indicators",
           "The KRIs and KPIs watching IT risk, and their readings",
           ITG_COLOR, "What do our IT risk indicators say?",
           kpis(KRI, [("Key risk indicators", ""),
                      ("In breach", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] <> 'Within Threshold'")]) +
           kpis(KPI, [("Key performance indicators", "")]) + kpis(KRIV, [("KRI readings", "")]) +
           [count_by(KRI, "OPSS-KRI-Shared:Breach Status", "KRI breach status", "pie", size="third"),
            count_by(KRI, "OPSS-KRI:Indicator Trend", "KRI trend", "pie", size="third"),
            count_by(KPI, "OPSS-KPI:Status", "KPIs by status", size="third"),
            table_of("Readings under each KRI",
                     f"SELECT [{KRI}].[Name], [{KRIV}].[Name], [{KRIV}].[OPSS-KRIVal:Value], "
                     f"[{KRIV}].[OPSS-KRIVal:Period] FROM [{KRI}] JOIN [{KRIV}] ON PARENT([{KRI}])"),
            rooted(KRI, "Indicators by entity", ["OPSS-KRI-Shared:Breach Status"], direct=True)]),
]

# ---------- FCM: Financial Controls Management ----------

FCM_COLOR = "#8B5E34"
FCM = [
    report("FCM", "Account and assertion coverage",
           "Significant accounts, the sub-accounts beneath them and the assertions tested",
           FCM_COLOR, "Which accounts are in scope and what assertions do they carry?",
           kpis(ACC, [("Accounts", ""), ("Significant", f"[{ACC}].[OPSS-Acc:Significant] = 'Yes'")]) +
           kpis(SACC, [("Sub-accounts", "")]) + kpis(ASRT, [("Assertions", "")]) +
           [count_by(ACC, "OPSS-Acc:Account Type", "Accounts by type", "pie", size="third"),
            count_by(ACC, "OPSS-Acc:Status", "Accounts by status", "pie", size="third"),
            count_by(ASRT, "OPSS-Asrt:Assertion Type", "Assertions by type", size="third"),
            table_of("Sub-accounts under each account",
                     f"SELECT [{ACC}].[Name], [{SACC}].[Name], [{SACC}].[OPSS-Subacc:Status] "
                     f"FROM [{ACC}] JOIN [{SACC}] ON PARENT([{ACC}])"),
            rooted(ACC, "Accounts by entity", ["OPSS-Acc:Account Type", "OPSS-Acc:Status"], direct=True)]),
    report("FCM", "Process and sub-process scope",
           "The financial processes in scope and the risks mapped to them",
           FCM_COLOR, "Which financial processes are in scope for SOX?",
           kpis(PRC, [("Processes", "")]) + kpis(SUB, [("Sub-processes", "")]) +
           kpis(RSK, [("Risks", "")]) + kpis(CTL, [("Controls", "")]) +
           [count_by(PRC, "OPSS-Proc:Status", "Processes by status", "pie", size="third"),
            count_by(PRC, "OPSS-Proc:Process Type", "Processes by type", "pie", size="third"),
            count_by(SUB, "OPSS-Subproc:Status", "Sub-processes by status", size="third"),
            table_of("Sub-processes under each process",
                     f"SELECT [{PRC}].[Name], [{SUB}].[Name], [{SUB}].[OPSS-Subproc:Status] "
                     f"FROM [{PRC}] JOIN [{SUB}] ON PARENT([{PRC}])"),
            rooted(PRC, "Processes by entity", ["OPSS-Proc:Status"], direct=True)]),
    report("FCM", "Key controls",
           "Key financial controls, how they are classified and whether they are automated",
           FCM_COLOR, "What are our key financial controls and how are they run?",
           kpis(CTL, [("Controls", ""),
                      ("Key controls", f"[{CTL}].[OPSS-Ctl:Classification] = 'Key Control Activity'"),
                      ("Automated", f"[{CTL}].[OPSS-Ctl:Control Method] = 'Automated'"),
                      ("Ineffective", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'")]) +
           [count_by(CTL, "OPSS-Ctl:Classification", "Controls by classification", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Method", "Automated or manual", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Type", "Controls by type", size="third"),
            count_by(CTL, "OPSS-Ctl-Fin:COSO Component", "Controls by COSO component", size="half"),
            rooted(CTL, "Controls by entity",
                   ["OPSS-Ctl:Classification", "OPSS-Ctl:Operating Effectiveness"])],
           [filter_on("Classification", CTL, "OPSS-Ctl:Classification")]),
    report("FCM", "Control testing",
           "Test plans against financial controls and how far through testing we are",
           FCM_COLOR, "How far through control testing are we this cycle?",
           kpis(TEST, [("Test plans", ""), ("Open", f"[{TEST}].[OPSS-Test:Status] <> 'Closed'"),
                       ("Completed", f"[{TEST}].[OPSS-Test:Status] = 'Completed'")]) +
           kpis(TRES, [("Test results", "")]) +
           [count_by(TEST, "OPSS-Test:Status", "Tests by status", "pie", size="third"),
            count_by(TEST, "OPSS-Test:Test Type", "Tests by type", "pie", size="third"),
            count_by(TEST, "OPSS-Test:Frequency", "Testing frequency", size="third"),
            table_of("Tests against each control",
                     f"SELECT [{CTL}].[Name], [{TEST}].[Name], [{TEST}].[OPSS-Test:Status] "
                     f"FROM [{CTL}] JOIN [{TEST}] ON PARENT([{CTL}])"),
            rooted(TEST, "Tests by entity", ["OPSS-Test:Status"])]),
    report("FCM", "Test results and exceptions",
           "What testing concluded, and the exceptions it threw up",
           FCM_COLOR, "What did control testing conclude, and what failed?",
           kpis(TRES, [("Test results", ""), ("Passed", f"[{TRES}].[OPSS-TestRes:Conclusion] = 'Pass'"),
                       ("Failed", f"[{TRES}].[OPSS-TestRes:Conclusion] = 'Fail'"),
                       ("Exceptions noted", f"[{TRES}].[OPSS-TestRes:Exceptions] = 'Yes'")]) +
           [count_by(TRES, "OPSS-TestRes:Conclusion", "Results by conclusion", "pie", size="third"),
            count_by(TRES, "OPSS-TestRes:Status", "Results by status", "pie", size="third"),
            count_by(TRES, "OPSS-TestRes:Result Type", "Results by type", size="third"),
            count_by_two(TRES, "OPSS-TestRes:Conclusion", "OPSS-TestRes:Status",
                         "Conclusion by status", size="half"),
            rooted(TRES, "Failed results by entity", ["OPSS-TestRes:Conclusion"])]),
    report("FCM", "Control evaluations",
           "Period-end control evaluations and the conclusions reached",
           FCM_COLOR, "What did our period-end control evaluations conclude?",
           kpis(CEVAL, [("Control evaluations", ""),
                        ("Effective", f"[{CEVAL}].[OPSS-CtlEval:Operating Effectiveness] = 'Effective'"),
                        ("Ineffective", f"[{CEVAL}].[OPSS-CtlEval:Operating Effectiveness] = 'Ineffective'")]) +
           kpis(CTL, [("Controls", "")]) +
           [count_by(CEVAL, "OPSS-CtlEval:Operating Effectiveness", "Operating effectiveness", "pie",
                     size="third"),
            count_by(CEVAL, "OPSS-CtlEval:Design Effectiveness", "Design effectiveness", "pie", size="third"),
            count_by(CEVAL, "OPSS-CtlEval:Status", "Evaluations by status", size="third"),
            table_of("Evaluations against each control",
                     f"SELECT [{CTL}].[Name], [{CEVAL}].[Name], "
                     f"[{CEVAL}].[OPSS-CtlEval:Operating Effectiveness] "
                     f"FROM [{CTL}] JOIN [{CEVAL}] ON PARENT([{CTL}])"),
            rooted(CEVAL, "Evaluations by entity", ["OPSS-CtlEval:Operating Effectiveness"])]),
    report("FCM", "Risk evaluations",
           "Financial risk evaluations, by rating and conclusion",
           FCM_COLOR, "How were our financial risks evaluated this period?",
           kpis(REVAL, [("Risk evaluations", "")]) +
           kpis(RSK, [("Risks", ""), ("Open", f"[{RSK}].[OPSS-Risk:Status] <> 'Closed'")]) +
           kpis(RASS, [("Risk assessments", "")]) +
           [count_by(REVAL, "OPSS-RiskEval:Residual Risk Rating", "Evaluated residual rating", size="third"),
            count_by(REVAL, "OPSS-RiskEval:Inherent Risk Rating", "Evaluated inherent rating", size="third"),
            count_by(REVAL, "OPSS-RiskEval:Status", "Evaluations by status", "pie", size="third"),
            count_by_two(RSK, "OPSS-Risk:Residual Likelihood", "OPSS-Risk:Residual Impact",
                         "Residual likelihood by impact", size="half"),
            rooted(REVAL, "Evaluations by entity", ["OPSS-RiskEval:Residual Risk Rating"])]),
    report("FCM", "Process evaluations",
           "Process-level evaluations and their conclusions",
           FCM_COLOR, "What did our process evaluations conclude?",
           kpis(PEVAL, [("Process evaluations", "")]) + kpis(PRC, [("Processes", "")]) +
           kpis(SUB, [("Sub-processes", "")]) + kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'")]) +
           [count_by(PEVAL, "OPSS-ProcEval:Conclusion", "Evaluation conclusions", "pie", size="third"),
            count_by(PEVAL, "OPSS-ProcEval:Status", "Evaluations by status", "pie", size="third"),
            count_by(PRC, "OPSS-Proc:Process Type", "Processes by type", size="third"),
            table_of("Evaluations against each process",
                     f"SELECT [{PRC}].[Name], [{PEVAL}].[Name], [{PEVAL}].[OPSS-ProcEval:Conclusion] "
                     f"FROM [{PRC}] JOIN [{PEVAL}] ON PARENT([{PRC}])"),
            rooted(PEVAL, "Evaluations by entity", ["OPSS-ProcEval:Conclusion"])]),
    report("FCM", "Deficiencies",
           "Control deficiencies by severity and conclusion, and the actions closing them",
           FCM_COLOR, "What control deficiencies do we have and how severe are they?",
           kpis(ISS, [("Issues", ""), ("Open", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
                      ("Material weaknesses", f"[{ISS}].[OPSS-Iss:Conclusion] = 'Material Weakness'"),
                      ("Significant deficiencies", f"[{ISS}].[OPSS-Iss:Conclusion] = 'Significant Deficiency'")]) +
           [count_by(ISS, "OPSS-Iss:Conclusion", "Issues by conclusion", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Root Cause Type", "Issues by root cause", size="third"),
            table_of("Actions under each deficiency",
                     f"SELECT [{ISS}].[Name], [{ACT}].[Name], [{ACT}].[OPSS-ActItem:Status] "
                     f"FROM [{ISS}] JOIN [{ACT}] ON PARENT([{ISS}])"),
            rooted(ISS, "Deficiencies by entity", ["OPSS-Iss:Conclusion", "OPSS-Iss:Status"])],
           [filter_on("Conclusion", ISS, "OPSS-Iss:Conclusion")]),
    report("FCM", "Certification programme",
           "The certification programme and the questionnaires collected under it",
           FCM_COLOR, "How is our financial certification programme progressing?",
           kpis(PROG, [("Programmes", ""), ("Open", f"[{PROG}].[OPSS-Prog:Status] = 'Open'")]) +
           kpis(QA, [("Questionnaire assessments", ""),
                     ("Completed", f"[{QA}].[OPSS-QA:Status] = 'Completed'")]) +
           [count_by(PROG, "OPSS-Prog:Status", "Programmes by status", "pie", size="third"),
            count_by(QA, "OPSS-QA:Status", "Assessments by status", "pie", size="third"),
            count_by(QA, "OPSS-QA:Assessment Type", "Assessments by type", size="third"),
            table_of("Assessments under each programme",
                     f"SELECT [{PROG}].[Name], [{QA}].[Name], [{QA}].[OPSS-QA:Status] "
                     f"FROM [{PROG}] JOIN [{QA}] ON PARENT([{PROG}])"),
            rooted(PROG, "Programmes by entity", ["OPSS-Prog:Status"], direct=True)]),
]

# ---------- BCM: Business Continuity Management ----------

BCM_COLOR = "#E07A5F"
BCM = [
    report("BCM", "Business continuity plans",
           "Plans by status, type and review date, under the entity they cover",
           BCM_COLOR, "What continuity plans do we have and are they current?",
           kpis(BCP, [("Continuity plans", ""), ("Approved", f"[{BCP}].[OPSS-BCP:Status] = 'Approved'"),
                      ("In draft", f"[{BCP}].[OPSS-BCP:Status] = 'Draft'"),
                      ("Overdue for review", f"[{BCP}].[OPSS-BCP:Review Status] = 'Overdue'")]) +
           [count_by(BCP, "OPSS-BCP:Status", "Plans by status", "pie", size="third"),
            count_by(BCP, "OPSS-BCP:Plan Type", "Plans by type", "pie", size="third"),
            count_by(BCP, "OPSS-BCP:Criticality", "Plans by criticality", size="third"),
            rooted(BCP, "Plans by entity",
                   ["OPSS-BCP:Status", "OPSS-BCP:Plan Type", "OPSS-BCP:Last Review Date"], direct=True)],
           [filter_on("Plan status", BCP, "OPSS-BCP:Status")]),
    report("BCM", "Business impact analysis",
           "BIAs and the recovery objectives they set",
           BCM_COLOR, "What do our business impact analyses say about recovery?",
           kpis(BIA, [("Impact analyses", ""), ("Completed", f"[{BIA}].[OPSS-BIA:Status] = 'Completed'"),
                      ("In progress", f"[{BIA}].[OPSS-BIA:Status] = 'In Progress'")]) +
           kpis(BSVC, [("Business services", "")]) +
           [count_by(BIA, "OPSS-BIA:Status", "Analyses by status", "pie", size="third"),
            count_by(BIA, "OPSS-BIA:Criticality", "Analyses by criticality", "pie", size="third"),
            count_by(BIA, "OPSS-BIA:Recovery Time Objective", "Recovery time objective", size="third"),
            count_by_two(BIA, "OPSS-BIA:Criticality", "OPSS-BIA:Recovery Time Objective",
                         "Criticality by recovery objective", size="half"),
            rooted(BIA, "Analyses by entity", ["OPSS-BIA:Status", "OPSS-BIA:Criticality"], direct=True)]),
    report("BCM", "Business services",
           "The services we must keep running, their criticality and their evaluations",
           BCM_COLOR, "Which business services are critical, and how were they assessed?",
           kpis(BSVC, [("Business services", ""),
                       ("Critical", f"[{BSVC}].[OPSS-BSvc:Criticality] = 'Critical'"),
                       ("Active", f"[{BSVC}].[OPSS-BSvc:Status] = 'Active'")]) +
           kpis(BSEV, [("Service evaluations", "")]) +
           [count_by(BSVC, "OPSS-BSvc:Criticality", "Services by criticality", "pie", size="third"),
            count_by(BSVC, "OPSS-BSvc:Status", "Services by status", "pie", size="third"),
            count_by(BSEV, "OPSS-BSvcEval:Conclusion", "Evaluation conclusions", size="third"),
            table_of("Evaluations against each service",
                     f"SELECT [{BSVC}].[Name], [{BSEV}].[Name], [{BSEV}].[OPSS-BSvcEval:Conclusion] "
                     f"FROM [{BSVC}] JOIN [{BSEV}] ON PARENT([{BSVC}])"),
            rooted(BSVC, "Services by entity", ["OPSS-BSvc:Criticality", "OPSS-BSvc:Status"], direct=True)]),
    report("BCM", "Continuity testing",
           "Test plans against continuity plans, and whether they have been run",
           BCM_COLOR, "Have our continuity plans been tested?",
           kpis(BCTP, [("Test plans", ""), ("Scheduled", f"[{BCTP}].[OPSS-BCTest:Status] = 'Scheduled'"),
                       ("Completed", f"[{BCTP}].[OPSS-BCTest:Status] = 'Completed'")]) +
           kpis(BCP, [("Continuity plans", "")]) +
           [count_by(BCTP, "OPSS-BCTest:Status", "Test plans by status", "pie", size="third"),
            count_by(BCTP, "OPSS-BCTest:Test Type", "Tests by type", "pie", size="third"),
            count_by(BCTP, "OPSS-BCTest:Frequency", "Testing frequency", size="third"),
            table_of("Tests under each plan",
                     f"SELECT [{BCP}].[Name], [{BCTP}].[Name], [{BCTP}].[OPSS-BCTest:Status] "
                     f"FROM [{BCP}] JOIN [{BCTP}] ON PARENT([{BCP}])"),
            rooted(BCTP, "Test plans by entity", ["OPSS-BCTest:Status"])]),
    report("BCM", "Test results",
           "What continuity testing found, and whether objectives were met",
           BCM_COLOR, "Did our continuity tests meet their recovery objectives?",
           kpis(BCTR, [("Test results", ""), ("Passed", f"[{BCTR}].[OPSS-BCTestRes:Conclusion] = 'Pass'"),
                       ("Failed", f"[{BCTR}].[OPSS-BCTestRes:Conclusion] = 'Fail'"),
                       ("Objectives met", f"[{BCTR}].[OPSS-BCTestRes:Objectives Met] = 'Yes'")]) +
           [count_by(BCTR, "OPSS-BCTestRes:Conclusion", "Results by conclusion", "pie", size="third"),
            count_by(BCTR, "OPSS-BCTestRes:Status", "Results by status", "pie", size="third"),
            count_by(BCTR, "OPSS-BCTestRes:Objectives Met", "Objectives met", "pie", size="third"),
            table_of("Results under each test plan",
                     f"SELECT [{BCTP}].[Name], [{BCTR}].[Name], [{BCTR}].[OPSS-BCTestRes:Conclusion] "
                     f"FROM [{BCTP}] JOIN [{BCTR}] ON PARENT([{BCTP}])"),
            rooted(BCTR, "Results by entity", ["OPSS-BCTestRes:Conclusion"])]),
    report("BCM", "Continuity events",
           "Disruptions that actually happened, their severity and how long they lasted",
           BCM_COLOR, "What disruptions have we had, and how did we respond?",
           kpis(BCEV, [("Continuity events", ""), ("Open", f"[{BCEV}].[OPSS-BCEv:Status] = 'Open'"),
                       ("High severity", f"[{BCEV}].[OPSS-BCEv:Severity] = 'High'"),
                       ("Closed", f"[{BCEV}].[OPSS-BCEv:Status] = 'Closed'")]) +
           [count_by(BCEV, "OPSS-BCEv:Severity", "Events by severity", "pie", size="third"),
            count_by(BCEV, "OPSS-BCEv:Event Type", "Events by type", "pie", size="third"),
            count_by(BCEV, "OPSS-BCEv:Status", "Events by status", size="third"),
            rooted(BCEV, "Events by entity",
                   ["OPSS-BCEv:Severity", "OPSS-BCEv:Status", "Creation Date"], direct=True)],
           [filter_on("Occurred", BCEV, "Creation Date", "date")]),
    report("BCM", "Sites and locations",
           "The locations we operate from and the plans covering them",
           BCM_COLOR, "Which sites do we operate from, and are they covered by a plan?",
           kpis(LOC, [("Locations", ""), ("Active", f"[{LOC}].[OPSS-Loc:Status] = 'Active'"),
                      ("Critical", f"[{LOC}].[OPSS-Loc:Criticality] = 'High'")]) +
           kpis(BCP, [("Continuity plans", "")]) +
           [count_by(LOC, "OPSS-Loc:Location Type", "Locations by type", "pie", size="third"),
            count_by(LOC, "OPSS-Loc:Country", "Locations by country", size="third"),
            count_by(LOC, "OPSS-Loc:Criticality", "Locations by criticality", "pie", size="third"),
            table_of("Plans covering each location",
                     f"SELECT [{LOC}].[Name], [{BCP}].[Name], [{BCP}].[OPSS-BCP:Status] "
                     f"FROM [{LOC}] JOIN [{BCP}] ON PARENT([{LOC}])"),
            rooted(LOC, "Locations by entity", ["OPSS-Loc:Country", "OPSS-Loc:Criticality"], direct=True)]),
    report("BCM", "Dependencies",
           "The assets, vendors and processes our continuity plans depend on",
           BCM_COLOR, "What do our continuity plans depend on?",
           kpis(RES, [("Assets", ""), ("Critical", f"[{RES}].[OPSS-Res:Criticality] = 'High'")]) +
           kpis(VEN, [("Vendors", "")]) + kpis(PRC, [("Processes", "")]) +
           [count_by(RES, "OPSS-Res:Criticality", "Assets by criticality", "pie", size="third"),
            count_by(VEN, "OPSS-Vnd:Criticality", "Vendors by criticality", "pie", size="third"),
            count_by(PRC, "OPSS-Proc:Process Type", "Processes by type", size="third"),
            rooted(VEN, "Vendors by entity", ["OPSS-Vnd:Criticality", "OPSS-Vnd:Status"], direct=True),
            rooted(RES, "Assets by entity", ["OPSS-Res:Criticality"], direct=True)]),
    report("BCM", "Recovery readiness",
           "Plans, tests and events side by side, to show how ready we are",
           BCM_COLOR, "How ready are we to recover from a disruption?",
           kpis(BCP, [("Approved plans", f"[{BCP}].[OPSS-BCP:Status] = 'Approved'")]) +
           kpis(BCTP, [("Tests completed", f"[{BCTP}].[OPSS-BCTest:Status] = 'Completed'")]) +
           kpis(BCTR, [("Tests failed", f"[{BCTR}].[OPSS-BCTestRes:Conclusion] = 'Fail'")]) +
           kpis(BCEV, [("Open events", f"[{BCEV}].[OPSS-BCEv:Status] = 'Open'")]) +
           [count_by(BCP, "OPSS-BCP:Status", "Plans by status", "pie", size="third"),
            count_by(BCTP, "OPSS-BCTest:Status", "Tests by status", "pie", size="third"),
            count_by(BCTR, "OPSS-BCTestRes:Conclusion", "Test conclusions", "pie", size="third"),
            count_by(BIA, "OPSS-BIA:Recovery Time Objective", "Recovery objectives", size="half"),
            rooted(BCP, "Plans by entity", ["OPSS-BCP:Status", "OPSS-BCP:Criticality"], direct=True)]),
    report("BCM", "Continuity issues and actions",
           "Gaps found in continuity planning and the actions closing them",
           BCM_COLOR, "What gaps has continuity work found, and are they being closed?",
           kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
                      ("High priority", f"[{ISS}].[OPSS-Iss:Priority] = 'High'")]) +
           kpis(ACT, [("Open actions", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'")]) +
           kpis(BCP, [("Continuity plans", "")]) +
           [count_by(ISS, "OPSS-Iss:Status", "Issues by status", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="third"),
            count_by(ACT, "OPSS-ActItem:Status", "Actions by status", size="third"),
            table_of("Actions under each issue",
                     f"SELECT [{ISS}].[Name], [{ACT}].[Name], [{ACT}].[OPSS-ActItem:Status], "
                     f"[{ACT}].[OPSS-ActItem:Due Date] FROM [{ISS}] JOIN [{ACT}] ON PARENT([{ISS}])"),
            rooted(ISS, "Issues by entity", ["OPSS-Iss:Status", "OPSS-Iss:Priority"])]),
]

# ---------- DPM: Data Privacy Management ----------

DPM_COLOR = "#7209B7"
DPM = [
    report("DPM", "Systems holding personal data",
           "The systems in scope for privacy, their classification and criticality",
           DPM_COLOR, "Which systems hold personal data?",
           kpis(RES, [("Systems", ""), ("Active", f"[{RES}].[OPSS-Res:Status] = 'Active'"),
                      ("Holding personal data", f"[{RES}].[OPSS-Res:Personal Data] = 'Yes'"),
                      ("High criticality", f"[{RES}].[OPSS-Res:Criticality] = 'High'")]) +
           [count_by(RES, "OPSS-Res:Classification", "Systems by data classification", "pie", size="third"),
            count_by(RES, "OPSS-Res:Resource Type", "Systems by type", "pie", size="third"),
            count_by(RES, "OPSS-Res:Status", "Systems by status", size="third"),
            rooted(RES, "Systems by entity",
                   ["OPSS-Res:Classification", "OPSS-Res:Criticality", "OPSS-Res:Status"], direct=True)],
           [filter_on("Classification", RES, "OPSS-Res:Classification")]),
    report("DPM", "Data flows",
           "How personal data moves between systems, and across which borders",
           DPM_COLOR, "How does personal data flow between our systems?",
           kpis(RLINK, [("Data flows", "")]) + kpis(RES, [("Systems", "")]) +
           kpis(RLINK, [("Cross-border flows", f"[{RLINK}].[OPSS-ResLink:Cross Border] = 'Yes'")]) +
           kpis(INC, [("Privacy incidents", "")]) +
           [count_by(RLINK, "OPSS-ResLink:Link Type", "Flows by type", "pie", size="third"),
            count_by(RLINK, "OPSS-ResLink:Cross Border", "Cross-border flows", "pie", size="third"),
            count_by(RES, "OPSS-Res:Classification", "Systems by classification", size="third"),
            table_of("Flows from each system",
                     f"SELECT [{RES}].[Name], [{RLINK}].[Name], [{RLINK}].[OPSS-ResLink:Link Type] "
                     f"FROM [{RES}] JOIN [{RLINK}] ON PARENT([{RES}])"),
            rooted(RLINK, "Flows by entity", ["OPSS-ResLink:Link Type"])]),
    report("DPM", "Privacy incidents",
           "Breaches and near misses, their severity and whether they were notifiable",
           DPM_COLOR, "What privacy incidents have we had?",
           kpis(INC, [("Incidents", ""), ("Open", f"[{INC}].[OPSS-Inc:Status] = 'Open'"),
                      ("High severity", f"[{INC}].[OPSS-Inc:Severity] = 'High'"),
                      ("Notifiable", f"[{INC}].[OPSS-Inc:Notifiable] = 'Yes'")]) +
           [count_by(INC, "OPSS-Inc:Severity", "Incidents by severity", "pie", size="third"),
            count_by(INC, "OPSS-Inc:Incident Type", "Incidents by type", "pie", size="third"),
            count_by(INC, "OPSS-Inc:Status", "Incidents by status", size="third"),
            count_by(INC, "OPSS-Inc:Root Cause", "Incidents by root cause", size="half"),
            rooted(INC, "Incidents by entity",
                   ["OPSS-Inc:Severity", "OPSS-Inc:Status", "Creation Date"], direct=True)],
           [filter_on("Raised", INC, "Creation Date", "date")]),
    report("DPM", "Privacy assessments",
           "DPIAs and other privacy questionnaires, and how far through them we are",
           DPM_COLOR, "Where do our privacy impact assessments stand?",
           kpis(QA, [("Assessments", ""), ("Completed", f"[{QA}].[OPSS-QA:Status] = 'Completed'"),
                     ("In progress", f"[{QA}].[OPSS-QA:Status] = 'In Progress'")]) +
           kpis(PROG, [("Programmes", "")]) +
           [count_by(QA, "OPSS-QA:Status", "Assessments by status", "pie", size="third"),
            count_by(QA, "OPSS-QA:Assessment Type", "Assessments by type", "pie", size="third"),
            count_by(QA, "OPSS-QA:Result", "Assessment outcomes", size="third"),
            table_of("Assessments under each programme",
                     f"SELECT [{PROG}].[Name], [{QA}].[Name], [{QA}].[OPSS-QA:Status] "
                     f"FROM [{PROG}] JOIN [{QA}] ON PARENT([{PROG}])"),
            rooted(QA, "Assessments by entity", ["OPSS-QA:Status"])]),
    report("DPM", "Privacy controls",
           "The controls protecting personal data and how effective they are",
           DPM_COLOR, "How effective are the controls protecting personal data?",
           kpis(CTL, [("Controls", ""),
                      ("Ineffective", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'"),
                      ("Automated", f"[{CTL}].[OPSS-Ctl:Control Method] = 'Automated'")]) +
           kpis(CEVAL, [("Control evaluations", "")]) +
           [count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Operating effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Type", "Controls by type", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Method", "Automated or manual", "pie", size="third"),
            count_by(CEVAL, "OPSS-CtlEval:Operating Effectiveness", "Evaluated effectiveness", size="half"),
            rooted(CTL, "Controls by entity", ["OPSS-Ctl:Operating Effectiveness"])]),
    report("DPM", "Regulation applicability",
           "Which privacy regulations apply where, and on what basis",
           DPM_COLOR, "Which privacy regulations apply to us, and where?",
           kpis(REGAPP, [("Applicability decisions", ""),
                         ("Applicable", f"[{REGAPP}].[OPSS-RegApp:Applicability] = 'Applicable'"),
                         ("Not applicable", f"[{REGAPP}].[OPSS-RegApp:Applicability] = 'Not Applicable'")]) +
           kpis(MAND, [("Mandates", "")]) +
           [count_by(REGAPP, "OPSS-RegApp:Applicability", "Applicability", "pie", size="third"),
            count_by(REGAPP, "OPSS-RegApp:Status", "Decisions by status", "pie", size="third"),
            count_by(MAND, "OPSS-Man:Mandate Type", "Mandates by type", size="third"),
            rooted(REGAPP, "Applicability by entity", ["OPSS-RegApp:Applicability"])]),
    report("DPM", "Privacy regulatory change",
           "Changes to privacy law and what they mean for us",
           DPM_COLOR, "What privacy regulatory change is coming?",
           kpis(REGCH, [("Regulatory changes", ""), ("Open", f"[{REGCH}].[OPSS-RegCh:Status] <> 'Closed'"),
                        ("High impact", f"[{REGCH}].[OPSS-RegCh:Impact] = 'High'")]) +
           kpis(REGTASK, [("Tasks raised", "")]) +
           [count_by(REGCH, "OPSS-RegCh:Status", "Changes by status", "pie", size="third"),
            count_by(REGCH, "OPSS-RegCh:Impact", "Changes by impact", "pie", size="third"),
            count_by(REGCH, "OPSS-RegCh:Change Type", "Changes by type", size="third"),
            rooted(REGCH, "Changes by entity",
                   ["OPSS-RegCh:Status", "OPSS-RegCh:Impact"], direct=True)]),
    report("DPM", "Privacy tasks",
           "The work raised off privacy obligations, by status and priority",
           DPM_COLOR, "What privacy work is outstanding?",
           kpis(REGTASK, [("Regulatory tasks", ""),
                          ("Open", f"[{REGTASK}].[OPSS-RegTask:Status] = 'Open'")]) +
           kpis(ACT, [("Action items", ""), ("Open", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'")]) +
           [count_by(REGTASK, "OPSS-RegTask:Status", "Tasks by status", "pie", size="third"),
            count_by(REGTASK, "OPSS-RegTask:Priority", "Tasks by priority", "pie", size="third"),
            count_by(ACT, "OPSS-ActItem:Status", "Action items by status", size="third"),
            rooted(REGTASK, "Tasks by entity", ["OPSS-RegTask:Status", "OPSS-RegTask:Priority"])]),
    report("DPM", "Privacy baselines",
           "The privacy standards systems are measured against, and conformance to them",
           DPM_COLOR, "Do our systems meet our privacy baselines?",
           kpis(BASE, [("Baselines", ""), ("Approved", f"[{BASE}].[OPSS-Base:Status] = 'Approved'")]) +
           kpis(RES, [("Systems", "")]) + kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'")]) +
           [count_by(BASE, "OPSS-Base:Status", "Baselines by status", "pie", size="third"),
            count_by(BASE, "OPSS-Base:Baseline Type", "Baselines by type", "pie", size="third"),
            count_by(BASE, "OPSS-Base:Compliance Status", "Conformance", size="third"),
            rooted(BASE, "Baselines by entity", ["OPSS-Base:Status"])]),
    report("DPM", "Privacy issues and actions",
           "Privacy gaps and the actions closing them",
           DPM_COLOR, "What privacy issues are open?",
           kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
                      ("High priority", f"[{ISS}].[OPSS-Iss:Priority] = 'High'")]) +
           kpis(ACT, [("Open actions", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'"),
                      ("Awaiting approval", f"[{ACT}].[OPSS-ActItem:Status] = 'Awaiting Approval'")]) +
           [count_by(ISS, "OPSS-Iss:Status", "Issues by status", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Root Cause Type", "Issues by root cause", size="third"),
            count_by(ACT, "OPSS-ActItem:Status", "Actions by status", "pie", size="third"),
            table_of("Actions under each issue",
                     f"SELECT [{ISS}].[Name], [{ACT}].[Name], [{ACT}].[OPSS-ActItem:Status], "
                     f"[{ACT}].[OPSS-ActItem:Due Date] FROM [{ISS}] JOIN [{ACT}] ON PARENT([{ISS}])"),
            rooted(ISS, "Issues by entity", ["OPSS-Iss:Status", "OPSS-Iss:Priority"])]),
]

# ---------- ESG: Risk Management for ESG ----------

ESG_COLOR = "#2D6A4F"
ESG = [
    report("ESG", "ESG objectives",
           "The objectives we have set, their status and the risks against them",
           ESG_COLOR, "What ESG objectives have we set and how are they tracking?",
           kpis(OBJV, [("Objectives", ""), ("On track", f"[{OBJV}].[OPSS-Obj:Status] = 'On Track'"),
                       ("At risk", f"[{OBJV}].[OPSS-Obj:Status] = 'At Risk'")]) +
           kpis(RSK, [("Risks", "")]) +
           [count_by(OBJV, "OPSS-Obj:Status", "Objectives by status", "pie", size="third"),
            count_by(OBJV, "OPSS-Obj:Objective Type", "Objectives by pillar", "pie", size="third"),
            count_by(OBJV, "OPSS-Obj:Priority", "Objectives by priority", size="third"),
            table_of("Risk assessments under each objective",
                     f"SELECT [{OBJV}].[Name], [{RASS}].[Name], [{RASS}].[OPSS-RiskAssess:Status] "
                     f"FROM [{OBJV}] JOIN [{RASS}] ON PARENT([{OBJV}])"),
            rooted(OBJV, "Objectives by entity", ["OPSS-Obj:Status", "OPSS-Obj:Objective Type"], direct=True)]),
    report("ESG", "Disclosure statements",
           "What we have committed to disclose, and whether the statements are ready",
           ESG_COLOR, "Where do our ESG disclosure statements stand?",
           kpis(DISC, [("Disclosure statements", ""),
                       ("Approved", f"[{DISC}].[OPSS-Disc:Status] = 'Approved'"),
                       ("In draft", f"[{DISC}].[OPSS-Disc:Status] = 'Draft'")]) +
           kpis(REQ, [("Requirements", "")]) +
           [count_by(DISC, "OPSS-Disc:Status", "Statements by status", "pie", size="third"),
            count_by(DISC, "OPSS-Disc:Framework", "Statements by framework", "pie", size="third"),
            count_by(DISC, "OPSS-Disc:Disclosure Type", "Statements by type", size="third"),
            table_of("Statements under each requirement",
                     f"SELECT [{REQ}].[Name], [{DISC}].[Name], [{DISC}].[OPSS-Disc:Status] "
                     f"FROM [{REQ}] JOIN [{DISC}] ON PARENT([{REQ}])"),
            rooted(DISC, "Statements by entity", ["OPSS-Disc:Status", "OPSS-Disc:Framework"])]),
    report("ESG", "Mandates and requirements",
           "ESG frameworks we report under and the requirements they set",
           ESG_COLOR, "Which ESG frameworks apply, and what do they require?",
           kpis(MAND, [("Mandates", "")]) + kpis(SMAND, [("Sub-mandates", "")]) +
           kpis(REQ, [("Requirements", ""), ("Met", f"[{REQ}].[OPSS-Req:Status] = 'Met'")]) +
           [count_by(MAND, "OPSS-Man:Status", "Mandates by status", "pie", size="third"),
            count_by(MAND, "OPSS-Man:Mandate Type", "Mandates by framework", "pie", size="third"),
            count_by(REQ, "OPSS-Req:Status", "Requirements by status", size="third"),
            table_of("Requirements under each sub-mandate",
                     f"SELECT [{SMAND}].[Name], [{REQ}].[Name], [{REQ}].[OPSS-Req:Status] "
                     f"FROM [{SMAND}] JOIN [{REQ}] ON PARENT([{SMAND}])"),
            rooted(MAND, "Mandates by entity", ["OPSS-Man:Status"], direct=True)]),
    report("ESG", "Requirement evaluations",
           "How each ESG requirement was evaluated, and what was concluded",
           ESG_COLOR, "How did we evaluate our ESG requirements?",
           kpis("RequirementEvaluation", [("Requirement evaluations", ""),
                                          ("Met", "[RequirementEvaluation].[OPSS-ReqEval:Conclusion] = 'Met'"),
                                          ("Not met", "[RequirementEvaluation].[OPSS-ReqEval:Conclusion] = 'Not Met'")]) +
           kpis(REQ, [("Requirements", "")]) +
           [count_by("RequirementEvaluation", "OPSS-ReqEval:Conclusion", "Evaluation conclusions", "pie",
                     size="third"),
            count_by("RequirementEvaluation", "OPSS-ReqEval:Status", "Evaluations by status", "pie",
                     size="third"),
            count_by(REQ, "OPSS-Req:Requirement Type", "Requirements by type", size="third"),
            table_of("Evaluations against each requirement",
                     f"SELECT [{REQ}].[Name], [RequirementEvaluation].[Name], "
                     f"[RequirementEvaluation].[OPSS-ReqEval:Conclusion] "
                     f"FROM [{REQ}] JOIN [RequirementEvaluation] ON PARENT([{REQ}])"),
            rooted("RequirementEvaluation", "Evaluations by entity", ["OPSS-ReqEval:Conclusion"])]),
    report("ESG", "ESG obligations",
           "ESG obligations and how they were evaluated",
           ESG_COLOR, "What ESG obligations do we carry?",
           kpis(OBL, [("Obligations", ""), ("Active", f"[{OBL}].[OPSS-Obl:Status] = 'Active'")]) +
           kpis(OBLE, [("Evaluations", ""), ("Not met", f"[{OBLE}].[OPSS-OblEval:Conclusion] = 'Not Met'")]) +
           [count_by(OBL, "OPSS-Obl:Status", "Obligations by status", "pie", size="third"),
            count_by(OBL, "OPSS-Obl-DT:Functional Risk Area", "Obligations by risk area", size="third"),
            count_by(OBLE, "OPSS-OblEval:Conclusion", "Evaluation conclusions", "pie", size="third"),
            rooted(OBL, "Obligations by entity", ["OPSS-Obl:Status"])]),
    report("ESG", "ESG performance indicators",
           "The KPIs behind our ESG reporting and the values recorded",
           ESG_COLOR, "How are our ESG performance indicators tracking?",
           kpis(KPI, [("Key performance indicators", ""),
                      ("Off target", f"[{KPI}].[OPSS-KPI:Status] = 'Off Target'")]) +
           kpis(KPIV, [("KPI readings", "")]) + kpis(OBJV, [("Objectives", "")]) +
           [count_by(KPI, "OPSS-KPI:Status", "KPIs by status", "pie", size="third"),
            count_by(KPI, "OPSS-KPI:Frequency", "Collection frequency", "pie", size="third"),
            count_by(KPI, "OPSS-KPI:Unit of Measure", "KPIs by unit", size="third"),
            table_of("Readings under each KPI",
                     f"SELECT [{KPI}].[Name], [{KPIV}].[Name], [{KPIV}].[OPSS-KPIVal:Value], "
                     f"[{KPIV}].[OPSS-KPIVal:Period] FROM [{KPI}] JOIN [{KPIV}] ON PARENT([{KPI}])"),
            rooted(KPI, "Indicators by entity", ["OPSS-KPI:Status"], direct=True)]),
    report("ESG", "ESG risk indicators",
           "KRIs watching ESG risk, their breach status and trend",
           ESG_COLOR, "What do our ESG risk indicators say?",
           kpis(KRI, [("Key risk indicators", ""),
                      ("In breach", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] <> 'Within Threshold'"),
                      ("Trending worse", f"[{KRI}].[OPSS-KRI:Indicator Trend] = 'Worse'")]) +
           kpis(KRIV, [("Readings", "")]) +
           [count_by(KRI, "OPSS-KRI-Shared:Breach Status", "Breach status", "pie", size="third"),
            count_by(KRI, "OPSS-KRI:Indicator Trend", "Trend", "pie", size="third"),
            count_by(KRI, "OPSS-KRI:Frequency", "Collection frequency", size="third"),
            rooted(KRI, "Indicators by entity",
                   ["OPSS-KRI-Shared:Breach Status", "OPSS-KRI:Indicator Trend"], direct=True)]),
    report("ESG", "ESG risks and controls",
           "The risks to our ESG commitments and the controls over them",
           ESG_COLOR, "What risks threaten our ESG commitments?",
           kpis(RSK, [("Risks", ""), ("Open", f"[{RSK}].[OPSS-Risk:Status] <> 'Closed'")]) +
           kpis(CTL, [("Controls", ""),
                      ("Ineffective", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'")]) +
           [count_by(RSK, "OPSS-Risk:Residual Risk Rating", "Risks by residual rating", size="half"),
            count_by(RSK, "OPSS-Risk:Status", "Risks by status", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Control effectiveness", "pie", size="third"),
            count_by_two(RSK, "OPSS-Risk:Residual Likelihood", "OPSS-Risk:Residual Impact",
                         "Residual likelihood by impact", size="half"),
            rooted(RSK, "Risks by entity", ["OPSS-Risk:Residual Risk Rating", "OPSS-Risk:Status"])]),
    report("ESG", "Products and supply chain",
           "The products and vendors our ESG position depends on",
           ESG_COLOR, "Which products and suppliers carry our ESG exposure?",
           kpis(PROD, [("Products", ""), ("Active", f"[{PROD}].[OPSS-Prod:Status] = 'Active'")]) +
           kpis(VEN, [("Vendors", "")]) + kpis(CONT, [("Contracts", "")]) +
           [count_by(PROD, "OPSS-Prod:Status", "Products by status", "pie", size="third"),
            count_by(PROD, "OPSS-Prod:Product Type", "Products by type", "pie", size="third"),
            count_by(VEN, "OPSS-Vnd:Criticality", "Vendors by criticality", size="third"),
            rooted(PROD, "Products by entity", ["OPSS-Prod:Status", "OPSS-Prod:Product Type"], direct=True),
            rooted(VEN, "Vendors by entity", ["OPSS-Vnd:Status", "OPSS-Vnd:Criticality"], direct=True)]),
    report("ESG", "Regulatory initiatives",
           "ESG regulation on the horizon and the regulators behind it",
           ESG_COLOR, "What ESG regulation is coming our way?",
           kpis(REGI, [("Regulatory initiatives", ""),
                       ("Open", f"[{REGI}].[OPSS-RegInit:Status] <> 'Closed'")]) +
           kpis(REGCH, [("Regulatory changes", "")]) + kpis(REGL, [("Regulators", "")]) +
           [count_by(REGI, "OPSS-RegInit:Status", "Initiatives by status", "pie", size="third"),
            count_by(REGI, "OPSS-RegInit:Impact", "Initiatives by impact", "pie", size="third"),
            count_by(REGCH, "OPSS-RegCh:Status", "Changes by status", size="third"),
            rooted(REGI, "Initiatives by entity", ["OPSS-RegInit:Status", "OPSS-RegInit:Impact"])]),
]

# ---------- TPRM: Third Party Risk Management ----------

TPRM_COLOR = "#BC4749"
TPRM = [
    report("TPRM", "Vendor inventory",
           "Every vendor, by tier, criticality and status, under the entity that engaged them",
           TPRM_COLOR, "Who are our vendors and how critical are they?",
           kpis(VEN, [("Vendors", ""), ("Active", f"[{VEN}].[OPSS-Vnd:Status] = 'Active'"),
                      ("Critical", f"[{VEN}].[OPSS-Vnd:Criticality] = 'High'"),
                      ("Onboarding", f"[{VEN}].[OPSS-Vnd:Status] = 'Onboarding'")]) +
           [count_by(VEN, "OPSS-Vnd:Criticality", "Vendors by criticality", "pie", size="third"),
            count_by(VEN, "OPSS-Vnd:Vendor Type", "Vendors by type", "pie", size="third"),
            count_by(VEN, "OPSS-Vnd:Status", "Vendors by status", size="third"),
            count_by(VEN, "OPSS-Vnd:Country", "Vendors by country", size="half"),
            rooted(VEN, "Vendors by entity",
                   ["OPSS-Vnd:Criticality", "OPSS-Vnd:Vendor Type", "OPSS-Vnd:Status"], direct=True)],
           [filter_on("Criticality", VEN, "OPSS-Vnd:Criticality")]),
    report("TPRM", "Vendor risk assessments",
           "The risk assessments run on vendors and what they concluded",
           TPRM_COLOR, "How risky are our vendors?",
           kpis(RASS, [("Assessments", ""), ("Completed", f"[{RASS}].[OPSS-RiskAssess:Status] = 'Completed'"),
                       ("In progress", f"[{RASS}].[OPSS-RiskAssess:Status] = 'In Progress'")]) +
           kpis(VEN, [("Vendors", "")]) +
           [count_by(RASS, "OPSS-RiskAssess:Status", "Assessments by status", "pie", size="third"),
            count_by(RASS, "OPSS-RiskAssess:Type", "Assessments by type", "pie", size="third"),
            count_by(RSK, "OPSS-Risk:Residual Risk Rating", "Vendor risks by rating", size="third"),
            table_of("Assessments against each vendor",
                     f"SELECT [{VEN}].[Name], [{RASS}].[Name], [{RASS}].[OPSS-RiskAssess:Status] "
                     f"FROM [{VEN}] JOIN [{RASS}] ON ANCESTOR([{VEN}])"),
            rooted(RASS, "Assessments by entity", ["OPSS-RiskAssess:Status"])]),
    report("TPRM", "Contracts",
           "Vendor contracts, their status, type and renewal dates",
           TPRM_COLOR, "What vendor contracts do we hold and when do they renew?",
           kpis(CONT, [("Contracts", ""), ("Active", f"[{CONT}].[OPSS-Cont:Status] = 'Active'"),
                       ("Expired", f"[{CONT}].[OPSS-Cont:Status] = 'Expired'"),
                       ("Up for renewal", f"[{CONT}].[OPSS-Cont:Status] = 'Up for Renewal'")]) +
           [count_by(CONT, "OPSS-Cont:Status", "Contracts by status", "pie", size="third"),
            count_by(CONT, "OPSS-Cont:Contract Type", "Contracts by type", "pie", size="third"),
            count_by(CONT, "OPSS-Cont:Criticality", "Contracts by criticality", size="third"),
            table_of("Contracts with each vendor",
                     f"SELECT [{VEN}].[Name], [{CONT}].[Name], [{CONT}].[OPSS-Cont:Status], "
                     f"[{CONT}].[OPSS-Cont:End Date] FROM [{VEN}] JOIN [{CONT}] ON ANCESTOR([{VEN}])"),
            rooted(CONT, "Contracts by entity", ["OPSS-Cont:Status", "OPSS-Cont:End Date"])],
           [filter_on("Ends", CONT, "OPSS-Cont:End Date", "date")]),
    report("TPRM", "Engagements",
           "What each vendor actually does for us, and how critical that work is",
           TPRM_COLOR, "What work are our vendors doing for us?",
           kpis(ENG, [("Engagements", ""), ("Active", f"[{ENG}].[OPSS-Eng:Status] = 'Active'"),
                      ("Critical", f"[{ENG}].[OPSS-Eng:Criticality] = 'High'")]) +
           kpis(VEN, [("Vendors", "")]) +
           [count_by(ENG, "OPSS-Eng:Status", "Engagements by status", "pie", size="third"),
            count_by(ENG, "OPSS-Eng:Engagement Type", "Engagements by type", "pie", size="third"),
            count_by(ENG, "OPSS-Eng:Criticality", "Engagements by criticality", size="third"),
            table_of("Engagements with each vendor",
                     f"SELECT [{VEN}].[Name], [{ENG}].[Name], [{ENG}].[OPSS-Eng:Status], "
                     f"[{ENG}].[OPSS-Eng:Criticality] FROM [{VEN}] JOIN [{ENG}] ON ANCESTOR([{VEN}])"),
            rooted(ENG, "Engagements by entity", ["OPSS-Eng:Status", "OPSS-Eng:Criticality"])]),
    report("TPRM", "Fourth parties",
           "Subcontractors and vendor subsidiaries behind our vendors",
           TPRM_COLOR, "Who sits behind our vendors?",
           kpis(SUBC, [("Subcontractors", "")]) + kpis(VSUB, [("Vendor subsidiaries", "")]) +
           kpis(VEN, [("Vendors", "")]) +
           kpis(SUBC, [("Critical subcontractors", f"[{SUBC}].[OPSS-Subc:Criticality] = 'High'")]) +
           [count_by(SUBC, "OPSS-Subc:Status", "Subcontractors by status", "pie", size="third"),
            count_by(SUBC, "OPSS-Subc:Criticality", "Subcontractors by criticality", "pie", size="third"),
            count_by(VSUB, "OPSS-VndSub:Country", "Subsidiaries by country", size="third"),
            table_of("Subcontractors behind each vendor",
                     f"SELECT [{VEN}].[Name], [{SUBC}].[Name], [{SUBC}].[OPSS-Subc:Status] "
                     f"FROM [{VEN}] JOIN [{SUBC}] ON ANCESTOR([{VEN}])"),
            rooted(SUBC, "Subcontractors by entity", ["OPSS-Subc:Status"])]),
    report("TPRM", "Vendor incidents",
           "Incidents and disruptions caused by third parties",
           TPRM_COLOR, "What incidents have our vendors caused?",
           kpis(INC, [("Incidents", ""), ("Open", f"[{INC}].[OPSS-Inc:Status] = 'Open'"),
                      ("High severity", f"[{INC}].[OPSS-Inc:Severity] = 'High'")]) +
           kpis(BCEV, [("Continuity events", "")]) +
           [count_by(INC, "OPSS-Inc:Severity", "Incidents by severity", "pie", size="third"),
            count_by(INC, "OPSS-Inc:Incident Type", "Incidents by type", "pie", size="third"),
            count_by(INC, "OPSS-Inc:Status", "Incidents by status", size="third"),
            count_by(BCEV, "OPSS-BCEv:Severity", "Continuity events by severity", size="half"),
            rooted(INC, "Incidents by entity",
                   ["OPSS-Inc:Severity", "OPSS-Inc:Status", "Creation Date"], direct=True)],
           [filter_on("Raised", INC, "Creation Date", "date")]),
    report("TPRM", "Due diligence questionnaires",
           "The questionnaires sent to vendors and what came back",
           TPRM_COLOR, "How is vendor due diligence progressing?",
           kpis(QA, [("Assessments", ""), ("Completed", f"[{QA}].[OPSS-QA:Status] = 'Completed'"),
                     ("Outstanding", f"[{QA}].[OPSS-QA:Status] <> 'Completed'")]) +
           kpis(VEN, [("Vendors", "")]) +
           [count_by(QA, "OPSS-QA:Status", "Assessments by status", "pie", size="third"),
            count_by(QA, "OPSS-QA:Assessment Type", "Assessments by type", "pie", size="third"),
            count_by(QA, "OPSS-QA:Result", "Assessment outcomes", size="third"),
            table_of("Questionnaires sent to each vendor",
                     f"SELECT [{VEN}].[Name], [{QA}].[Name], [{QA}].[OPSS-QA:Status] "
                     f"FROM [{VEN}] JOIN [{QA}] ON PARENT([{VEN}])"),
            rooted(QA, "Assessments by entity", ["OPSS-QA:Status"])]),
    report("TPRM", "Vendor controls",
           "The controls we rely on vendors to run, and how effective they are",
           TPRM_COLOR, "How effective are the controls our vendors run?",
           kpis(CTL, [("Controls", ""),
                      ("Ineffective", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'")]) +
           kpis(CEVAL, [("Control evaluations", "")]) + kpis(VEN, [("Vendors", "")]) +
           [count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Operating effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Type", "Controls by type", "pie", size="third"),
            count_by(CEVAL, "OPSS-CtlEval:Operating Effectiveness", "Evaluated effectiveness", size="third"),
            rooted(CTL, "Controls by entity", ["OPSS-Ctl:Operating Effectiveness"])]),
    report("TPRM", "Vendor risk indicators",
           "The KRIs watching third-party risk and their readings",
           TPRM_COLOR, "What do our third-party risk indicators say?",
           kpis(KRI, [("Key risk indicators", ""),
                      ("In breach", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] <> 'Within Threshold'"),
                      ("Trending worse", f"[{KRI}].[OPSS-KRI:Indicator Trend] = 'Worse'")]) +
           kpis(KRIV, [("Readings", "")]) +
           [count_by(KRI, "OPSS-KRI-Shared:Breach Status", "Breach status", "pie", size="third"),
            count_by(KRI, "OPSS-KRI:Indicator Trend", "Trend", "pie", size="third"),
            count_by(KRI, "OPSS-KRI:Frequency", "Collection frequency", size="third"),
            rooted(KRI, "Indicators by entity", ["OPSS-KRI-Shared:Breach Status"], direct=True)]),
    report("TPRM", "Vendor issues and actions",
           "Issues raised against third parties and the actions closing them",
           TPRM_COLOR, "What issues are open against our vendors?",
           kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'"),
                      ("High priority", f"[{ISS}].[OPSS-Iss:Priority] = 'High'")]) +
           kpis(ACT, [("Open actions", f"[{ACT}].[OPSS-ActItem:Status] = 'Open'")]) +
           kpis(WAIV, [("Waivers", "")]) +
           [count_by(ISS, "OPSS-Iss:Status", "Issues by status", "pie", size="third"),
            count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="third"),
            count_by(ACT, "OPSS-ActItem:Status", "Actions by status", size="third"),
            table_of("Issues against each vendor",
                     f"SELECT [{VEN}].[Name], [{ISS}].[Name], [{ISS}].[OPSS-Iss:Status], "
                     f"[{ISS}].[OPSS-Iss:Priority] FROM [{VEN}] JOIN [{ISS}] ON ANCESTOR([{VEN}])"),
            rooted(ISS, "Issues by entity", ["OPSS-Iss:Status", "OPSS-Iss:Priority"])]),
]

MODULE_REPORTS = [*ORM, *PCM, *MRG, *IAM, *ITG, *FCM, *BCM, *DPM, *ESG, *TPRM]

# The order modules appear in, for the Templates page.
MODULES = ["ORM", "PCM", "MRG", "IAM", "ITG", "FCM", "BCM", "DPM", "ESG", "TPRM"]
MODULE_LABELS = {
    "ORM": "Operational Risk Management",
    "PCM": "Policy and Compliance Management",
    "MRG": "Model Risk Governance",
    "IAM": "Internal Audit Management",
    "ITG": "IT Governance",
    "FCM": "Financial Controls Management",
    "BCM": "Business Continuity Management",
    "DPM": "Data Privacy Management",
    "ESG": "Risk Management for ESG",
    "TPRM": "Third Party Risk Management",
}


def module_template_rows() -> list[dict]:
    """The module reports as rows for report_templates."""
    return [{"name": r["name"], "description": r["description"], "color": r["color"], "prompt": r["prompt"],
             "category": "GRC", "module": r["module"],
             "layout": {"kind": "dashboard", "source_type": "openpages", "widgets": r["widgets"],
                        "filters": r["filters"]}}
            for r in MODULE_REPORTS]
