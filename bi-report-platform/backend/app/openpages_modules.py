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

from .openpages_templates import (COUNT, ENT, Field, count_by, count_by_two, field_pairs, filter_on, heading,
                                  normalise, summary_table, table_of, total, with_entity_filter)

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
    """A list of `child` records that names the business entity each one belongs to.

    A direct child is read with a PARENT join, which may select the parent's own fields. Anything
    deeper cannot be: the Query Service's indirect join (ANCESTOR) "may only have one JOIN", must
    carry a Resource ID filter on the ancestor type, and allows no ancestor field in the SELECT
    besides it, so a list of "every X under its entity" is not a join at all. It doesn't need to
    be - [Location] is a system field on every object holding the entity path it hangs under, so
    reading one object type gives each row its entity and costs the server nothing."""
    # A column may be given as the several names installations know it by; the list is read down
    # in step, so each variant is one consistent set of names (see openpages_templates.Field).
    depth = max([len(f) for f in fields if isinstance(f, list)] or [1])
    variants = []
    for i in range(depth):
        picked = [f[min(i, len(f) - 1)] if isinstance(f, list) else f for f in fields]
        if direct:
            columns = ", ".join([f"[{ENT}].[Name]"] + [f"[{child}].[{f}]" for f in ["Name"] + picked])
            variants.append(f"SELECT {columns} FROM [{ENT}] JOIN [{child}] ON PARENT([{ENT}])")
        else:
            columns = ", ".join([f"[{child}].[Location]"] + [f"[{child}].[{f}]" for f in ["Name"] + picked])
            variants.append(f"SELECT {columns} FROM [{child}]")
    widget = table_of(title, variants[0], size=size)
    if len(variants) > 1:
        widget["alt_sql"] = variants[1:]
    return widget


def entity_section(what: str) -> list[dict]:
    """The business entity header every dashboard opens with."""
    return [heading("Business entities", f"Everything below hangs under these entities. {what}"),
            total(ENT, "Business entities", size="quarter"),
            count_by(ENT, ENT_TYPE, "Entities by type", "pie", size="third"),
            count_by(ENT, ENT_STATUS, "Entities by status", "pie", size="third")]


def report(module: str, name: str, description: str, color: str, prompt: str, body: list[dict],
           filters: list[dict] | None = None, intro: str = "", theme: str = "") -> dict:
    out = {"module": module, "name": f"{module}: {name}", "description": description, "color": color,
           "prompt": prompt, "widgets": entity_section(intro) + body,
           "filters": [ROOT_FILTER] + list(filters or [])}
    if theme:
        out["theme"] = theme
    return out


def kpis(type_name: str, items: list[tuple[str, str | list[str]]]) -> list[dict]:
    """Number tiles. A condition may be given as several, one per name the field is known by."""
    return [total(type_name, title, where) for title, where in items]


def status_set(type_name: str, prefix: str, extra: list[tuple[str, str, str, str]] = ()) -> list[dict]:
    """The three breakdowns almost every object type supports, plus whatever else is passed."""
    charts = [count_by(type_name, f"{prefix}:Status", "By status", "pie", size="third")]
    charts += [count_by(t, f, title, chart, size="third") for t, f, title, chart in extra]
    return charts


# ---------- ORM: Operational Risk Management ----------

ORM_COLOR = "#6D597A"

# ---------- ORM overview: the fields, colours and helpers it needs ----------
#
# The overview dashboard below reads eight object types at once. Beyond the fields the other ORM
# dashboards already use, it reads the ones an ORM profile adds (risk domain, tolerance, treatment,
# scope flags, KRI thresholds, action item ageing).
#
# Installations put these in different field groups, and a chart naming only one of them is dropped
# everywhere else. So each is listed under every name it is known by, newest standard first, and the
# build step tries them in turn (see openpages_templates.Field). The second names here are the ones
# an installation with the ORM profile loaded was observed to use. A field known by none of its
# names is still dropped at build time, with the reason shown.
DOMAIN = {RSK: ["OPSS-Risk:Risk Domain", "OPSS-Rsk:Domain", "OPSS-Risk:Domain"],
          CTL: ["OPSS-Ctl:Risk Domain", "OPSS-Ctl:Domain", "OPSS-Control:Domain"],
          PRC: ["OPSS-Proc:Risk Domain", "OPSS-Process:Domain", "OPSS-Proc:Domain"],
          KRI: ["OPSS-KRI:Risk Domain", "OPSS-KRI:Domain", "OPSS-KRI-Shared:Domain"],
          ISS: ["OPSS-Iss:Risk Domain", "OPSS-Iss:Domain", "OPSS-Issue:Domain"]}

# Risk ratings, tolerance and treatment: the qualitative assessment and acceptance groups hold these
# on an installation that has them.
INHERENT = ["OPSS-Risk:Inherent Risk Rating", "OPSS-Risk-Qual:Inherent Risk Rating"]
RESIDUAL = ["OPSS-Risk:Residual Risk Rating", "OPSS-Risk-Qual:Residual Risk Rating"]
RESID_LIKELIHOOD = ["OPSS-Risk:Residual Likelihood", "OPSS-Risk-Qual:Residual Likelihood"]
INHER_LIKELIHOOD = ["OPSS-Risk:Inherent Likelihood", "OPSS-Risk-Qual:Inherent Likelihood"]
TOLERANCE = ["OPSS-Risk:Within Risk Tolerance", "OPSS-Risk-Accp:Within Tolerance"]
TREATMENT = ["OPSS-Risk:Risk Treatment", "OPSS-Risk-Accp:Acceptance", "OPSS-Risk-Accp:Risk Treatment"]
RSK_STATUS = ["OPSS-Risk:Status", "OPSS-Rsk:Status"]
# The Basel event category, with and without the level suffix.
BASEL_CATEGORY = ["OPSS-Shared-Basel:Risk Category L1", "OPSS-Shared-Basel:Risk Category"]
# Loss events and indicators. Severity and the loss-collection status come from the loss-collection
# group on an installation that has it; a KRI's nature, collection status and thresholds sit in the
# KRI group or the shared one.
LOSS_SEVERITY = ["OPSS-LossEv:Severity", "OPLC-LossEvent:Severity"]
KRI_NATURE = ["OPSS-KRI:Indicator Nature", "OPSS-KRI:Nature"]
KRI_COLLECTION = ["OPSS-KRI:Collection Status", "OPSS-KRI-Shared:Collection Status"]
KRI_YELLOW = ["OPSS-KRI:Yellow Threshold", "OPSS-KRI-Shared:Yellow Threshold"]
KRI_RED = ["OPSS-KRI:Red Threshold", "OPSS-KRI-Shared:Red Threshold"]


# Processes: the shorter "OPSS-Proc" group and the spelled-out "OPSS-Process" one both occur.
PRC_STATUS = ["OPSS-Proc:Status", "OPSS-Process:Status"]
PRC_SCOPE = ["OPSS-Proc:In Scope", "OPSS-Process:In Scope"]
PRC_CATEGORY = ["OPSS-Proc:Process Category", "OPSS-Process:Category", "OPSS-Process:Process Category"]
PRC_SOX = ["OPSS-Proc:SOX Status", "OPSS-Process:SOX Status", "OPSS-FCM-cert:Certification Status"]

# Controls and business entities.
CTL_FREQUENCY = ["OPSS-Ctl:Control Frequency", "OPSS-Ctl:Frequency"]
ENT_TYPE = ["OPSS-Ent:Entity Type", "OPSS-BusEnt:Entity Type", "OPSS-BE:Entity Type"]
ENT_STATUS = ["OPSS-Ent:Status", "OPSS-BusEnt:Status"]
ENT_SCOPE = ["OPSS-Ent:In Scope", "OPSS-BusEnt:In Scope", "OPSS-BE:Entity In Scope"]
ENT_RCSA = ["OPSS-Ent:RCSA Scope", "OPSS-BusEnt:In RCSA Scope", "OPSS-BusEnt:RCSA Scope"]
# The framework an entity is assessed against is often an add-on field group named for the
# regulation itself, so the installation's own name is the last thing tried.
ENT_FRAMEWORK = ["OPSS-Ent:Framework", "OPSS-BusEnt:Framework", "SEBI CSCRF BE:Framework"]

# Colour coding, as asked for, in the steps the dashboard's design settled on. The obvious hues
# (#1E8E3E / #F2C200 / #E8740C / #C5192D) failed two checks on a white card: the yellow sat at
# 1.64:1 against the background, and yellow against orange came out under 10 ΔE, which colour-vision
# deficiency and ordinary screens both lose. These steps pass the lightness, chroma and separation
# checks; every chart that uses them also shows its counts, so colour is never the only cue.
GREEN, AMBER, ORANGE, RED = "#2E7D4F", "#D9A520", "#CC5A11", "#A61326"
GREY, BLUE = "#6B7785", "#1C6FD0"
# The neutral breakdowns (type, method, domain, frequency) carry no rating, so they stay in the
# module's own plum rather than borrowing a rating colour: one hue for bars, its tints for rings.
PLUM, PLUM_SET = ORM_COLOR, [ORM_COLOR, "#A595AE", BLUE, GREY]

# ruleColor in the viewer matches a rule when the category *contains* the rule's text, first rule
# first, so the narrower name has to come first: "Ineffective" and "Partially Effective" both
# contain "Effective", and would otherwise all come out green.
RISK_COLOURS = [{"match": "Minor", "color": GREEN}, {"match": "Moderate", "color": AMBER},
                {"match": "Significant", "color": ORANGE}, {"match": "Major", "color": RED}]
CTL_COLOURS = [{"match": "Not Determined", "color": GREY}, {"match": "Ineffective", "color": RED},
               {"match": "Partially Effective", "color": ORANGE}, {"match": "Effective", "color": GREEN}]
KRI_COLOURS = [{"match": "Green", "color": GREEN}, {"match": "Yellow", "color": AMBER},
               {"match": "Red", "color": RED}]
ISS_COLOURS = [{"match": "Critical", "color": RED}, {"match": "High", "color": ORANGE},
               {"match": "Medium", "color": AMBER}, {"match": "Low", "color": GREEN}]
ACT_COLOURS = [{"match": "Completed", "color": GREEN}, {"match": "In Progress", "color": BLUE},
               {"match": "Overdue", "color": RED}, {"match": "Pending", "color": ORANGE}]
LOSS_COLOURS = [{"match": "Low", "color": GREEN}, {"match": "Moderate", "color": AMBER},
                {"match": "High", "color": ORANGE}, {"match": "Major", "color": RED}]


# Scales the design colours that are not one of the six named ratings. Longer names come first,
# because a rule matches when the category contains its text: "Unlikely" has to be tried before
# "Likely", and "Within tolerance" before a bare "No".
TOLERANCE_COLOURS = [{"match": "Within", "color": GREEN}, {"match": "Outside", "color": RED},
                     {"match": "Yes", "color": GREEN}, {"match": "No", "color": RED}]
SCOPE_COLOURS = [{"match": "Under review", "color": AMBER}, {"match": "Deferred", "color": AMBER},
                 {"match": "Out of scope", "color": GREY}, {"match": "In scope", "color": GREEN},
                 {"match": "Yes", "color": GREEN}, {"match": "No", "color": GREY}]
TREND_COLOURS = [{"match": "Improving", "color": GREEN}, {"match": "Better", "color": GREEN},
                 {"match": "Stable", "color": BLUE}, {"match": "Worse", "color": RED}]
COLLECT_COLOURS = [{"match": "Not started", "color": GREY}, {"match": "Overdue", "color": RED},
                   {"match": "Collected", "color": GREEN}]
APPROVAL_COLOURS = [{"match": "Not submitted", "color": GREY}, {"match": "Awaiting", "color": AMBER},
                    {"match": "Rejected", "color": RED}, {"match": "Approved", "color": GREEN}]
AGEING_COLOURS = [{"match": "Above 60", "color": RED}, {"match": "31", "color": ORANGE},
                  {"match": "11", "color": AMBER}, {"match": "10", "color": GREEN}]
PROB_COLOURS = [{"match": "Unlikely", "color": GREEN}, {"match": "Rare", "color": GREEN},
                {"match": "Possible", "color": AMBER}, {"match": "Almost certain", "color": RED},
                {"match": "Likely", "color": ORANGE}]


# ---------- the look the ORM overview was designed with ----------
#
# The design these two dashboards come from draws every breakdown one of two ways: a ring with the
# total in the middle and a legend listing each slice with its count and share, or a row of
# horizontal bars with the figure at the end. Both are shapes the viewer already draws; the styles
# here ask for them, and the "plex" theme (frontend app.css) carries the typography, the cards and
# the section rules. A chart styled this way still reads correctly under any other theme.
RING = {"ringLegend": True, "legend": True}
ROW = {"horizontal": True, "showValues": True}


def ring(widget: dict) -> dict:
    """A pie becomes the design's ring: hole in the middle, legend down the side."""
    widget["chart"] = {**(widget.get("chart") or {}), "type": "donut"}
    widget["style"] = {**(widget.get("style") or {}), **RING}
    return widget


def _kri_thresholds(i: int) -> str:
    """The indicator list, written against one pairing of the threshold field names."""
    return (f"SELECT [{KRI}].[Name], [{KRI}].[OPSS-KRI:Value], [{KRI}].[{KRI_YELLOW[i]}], "
            f"[{KRI}].[{KRI_RED[i]}] FROM [{KRI}] "
            f"WHERE [{KRI}].[OPSS-KRI:Value] IS NOT NULL ORDER BY [{KRI}].[Name]")


def paired(title: str, build, size: str = "half") -> dict:
    """A list whose SQL names the residual rating, written once per name that field is known by."""
    widget = table_of(title, build(RESIDUAL[0]), size=size)
    widget["alt_sql"] = [build(name) for name in RESIDUAL[1:]]
    return widget


def tint(widget: dict, rules: list[dict]) -> dict:
    """The rating colours on one chart, keeping whatever style the builder already set."""
    widget["style"] = {**(widget.get("style") or {}), "colorRules": rules, "showValues": True}
    kind = (widget.get("chart") or {}).get("type")
    if kind == "bar":
        widget["style"].update(ROW)
        return widget
    return ring(widget) if kind in ("pie", "donut") else widget


def plain(widget: dict) -> dict:
    """A breakdown that carries no rating: one plum hue, the count at the end of each bar."""
    widget["style"] = {**(widget.get("style") or {}), "color": PLUM, "colorMode": "single", **ROW}
    return widget


def mix(widget: dict) -> dict:
    """A ring whose slices mean nothing in particular: the plum tints, in order."""
    widget["style"] = {**(widget.get("style") or {}), "palette": PLUM_SET, "colorMode": "palette"}
    return ring(widget)


def by_month(widget: dict, field: str, title: str = "") -> dict:
    """A date chart counted per month. OpenPages SQL has no date functions, so the query still
    groups by the date itself and the rows are folded to mm/yyyy after they come back (see
    date_rollup); the chart's x stays the same field, so nothing else about the chart changes."""
    widget["rollup"] = {"column": field, "to": "month", "format": "mm/yyyy"}
    if title:
        widget["title"] = widget["question"] = title
    return widget


def heat(type_name: str, row_field: Field, col_field: Field, title: str, size: str = "half",
         question: str = "") -> dict:
    """A real heat map: one cell per pair of values, pale to deep plum for how many records fall in
    it. count_by_two draws the same query as a table; this draws the grid.

    Either field may be a list of the names different installations file it under. The grid has to
    name the one pair that actually ran - a list would leave the renderer looking for a column
    called "['OPSS-Risk:Residual Risk Rating', ...]", finding none, and falling back to the rows.
    So the first pair goes on the chart and the rest ride along as alt_x/alt_legend, which the
    build step swaps in beside the query it keeps (see routers/templates.first_that_runs)."""
    widget = count_by_two(type_name, row_field, col_field, title, size=size,
                          question=question or f"{title}. Count in each cell; darker means more.")
    pairs = field_pairs(row_field, col_field)
    widget["chart"] = {"type": "heatmap", "x": pairs[0][0], "y": [COUNT], "legend": pairs[0][1]}
    widget["alt_x"] = [r for r, _ in pairs[1:]]
    widget["alt_legend"] = [c for _, c in pairs[1:]]
    # The design writes the count in each cell and leaves the colour scale off the card, so the
    # grid reads as a table that happens to be shaded.
    widget["style"] = {"showValues": True, "color": PLUM, "legend": False}
    return widget


# A section's own card colour: the plum the design uses, at the weight a table can be read on.
SUMMARY_LOOK = {"cardBg": "#F5F1F9", "headBg": "#EDE7F1"}


def summary(type_name: str, title: str, fields: list[Field], question: str) -> dict:
    """The table that closes a section: one row per record, with the fields that section is about.

    It carries the section's own background so it reads as the band's summary rather than as one
    more chart, and its columns can be widened or taken off on the report itself."""
    widget = summary_table(type_name, title, fields, size="full", question=question)
    widget["style"] = dict(SUMMARY_LOOK)
    return widget


# The ORM overview is two dashboards, the way the design it comes from is two pages: the first
# covers the standing picture (risks, controls, processes and the entities they hang under), the
# second what happened and what is being done about it (loss events, indicators, issues, action
# items). Together they are one reading of a connection, but ~30 charts each is already a long page,
# and the second half answers a different question from the first.

def where_any(type_name: str, field: list[str] | str, test: str | list[str]) -> list[str]:
    """The same condition written against each name the field is known by, and each way the value
    may be worded, so a number tile is not lost on an installation that files the field somewhere
    else or ends a lifecycle on a different word.

    OpenPages refuses a query naming an enum value it doesn't have ("'Closed' is not a valid value
    for this enum"), so a wrong guess fails loudly and the next is tried - it never quietly counts
    the wrong thing."""
    names = [field] if isinstance(field, str) else field
    tests = [test] if isinstance(test, str) else test
    return [f"[{type_name}].[{name}] {t}" for t in tests for name in names]


ORM_FIRST_KPIS = (
    # "Open" is whatever the risk lifecycle has not finished at: some installations close a risk,
    # others end at approved.
    kpis(RSK, [("Risks", ""), ("Open risks", where_any(RSK, RSK_STATUS, ["<> 'Closed'", "<> 'Approved'"])),
               ("Major residual risks", where_any(RSK, RESIDUAL, "= 'Major'"))]) +
    kpis(CTL, [("Controls", ""),
               ("Ineffective controls", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'")]) +
    kpis(PRC, [("Business processes", "")]) +
    kpis(ENT, [("Entities in RCSA scope", where_any(ENT, ENT_RCSA, "= 'Yes'"))]))

ORM_SECOND_KPIS = (
    kpis(LOSS, [("Loss events", "")]) +
    kpis(KRI, [("Key risk indicators", ""),
               ("KRIs in red breach", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] = 'Red'")]) +
    kpis(ISS, [("Issues", ""), ("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'")]) +
    kpis(ACT, [("Action items", ""),
               ("Overdue action items", f"[{ACT}].[OPSS-ActItem:Overdue] = 'Yes'")]))

ORM_FIRST_BODY = (
    # ---- risks ----
    [heading("Risk profile", "Where the risks stand, how they are rated and how they are being treated. "
                      "Minor green, Moderate yellow, Significant orange, Major red."),
     mix(count_by(RSK, RSK_STATUS, "Risks by status", "pie", size="third")),
     plain(count_by(RSK, DOMAIN[RSK], "Risks by domain", size="third")),
     plain(count_by(RSK, BASEL_CATEGORY, "Risks by category", size="third")),
     tint(count_by(RSK, INHERENT, "Risks by inherent rating", size="third"), RISK_COLOURS),
     tint(count_by(RSK, RESIDUAL, "Risks by residual rating", size="third"), RISK_COLOURS),
     mix(count_by(RSK, TREATMENT, "Risks by treatment", "pie", size="third")),
     tint(count_by(RSK, TOLERANCE, "Risks within tolerance", "pie", size="third"), TOLERANCE_COLOURS),
     heat(RSK, RESIDUAL, RESID_LIKELIHOOD, "Residual rating against residual likelihood",
          size="twothird",
          question="Count of risks in each cell. Darker means more risks sitting there."),
     summary(RSK, "Risk summary", ["Name", DOMAIN[RSK], INHERENT, RESIDUAL, RSK_STATUS, TREATMENT],
             "One row per risk, with the fields this section is about. Drag a column's edge to "
             "widen it, or take a column off with the cross in its heading."),
     # ---- controls ----
     heading("Control effectiveness", "Coverage and effectiveness. Effective green, Partially Effective orange, "
                         "Ineffective red, Not Determined grey."),
     mix(count_by(CTL, "OPSS-Ctl:Status", "Controls by status", "pie", size="third")),
     plain(count_by(CTL, "OPSS-Ctl:Control Type", "Controls by type", size="third")),
     mix(count_by(CTL, "OPSS-Ctl:Control Method", "Controls by method", "pie", size="third")),
     plain(count_by(CTL, DOMAIN[CTL], "Controls by domain", size="third")),
     tint(count_by(CTL, "OPSS-Ctl:Design Effectiveness", "Design effectiveness", "pie", size="third"), CTL_COLOURS),
     tint(count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Operating effectiveness", "pie", size="third"),
          CTL_COLOURS),
     mix(count_by(CTL, "OPSS-Ctl:Classification", "Controls by classification", "pie", size="half")),
     plain(count_by(CTL, CTL_FREQUENCY, "Controls by frequency", size="half")),
     summary(CTL, "Control summary",
             ["Name", DOMAIN[CTL], "OPSS-Ctl:Control Type", "OPSS-Ctl:Control Method",
              "OPSS-Ctl:Design Effectiveness", "OPSS-Ctl:Operating Effectiveness", "OPSS-Ctl:Status"],
             "One row per control, with its type, method and how effective it was found to be."),
     # ---- business processes ----
     heading("Process coverage", "What the risks and controls hang off, and how much of it is in scope."),
     mix(count_by(PRC, PRC_STATUS, "Processes by status", "pie", size="third")),
     plain(count_by(PRC, DOMAIN[PRC], "Processes by domain", size="third")),
     plain(count_by(PRC, PRC_CATEGORY, "Processes by category", size="third")),
     tint(count_by(PRC, PRC_SCOPE, "Processes in scope", "pie", size="half"), SCOPE_COLOURS),
     tint(count_by(PRC, PRC_SOX, "Processes by SOX status", "pie", size="half"), SCOPE_COLOURS),
     summary(PRC, "Process summary", ["Name", DOMAIN[PRC], PRC_CATEGORY, PRC_STATUS, PRC_SCOPE, PRC_SOX],
             "One row per business process, with what it covers and whether it is in scope."),
     # ---- business entities ----
     heading("Business entity scope", "The hierarchy everything above sits under, and how much of it is "
                                      "assessed."),
     tint(count_by(ENT, ENT_SCOPE, "Entities in scope", "pie", size="third"), SCOPE_COLOURS),
     tint(count_by(ENT, ENT_RCSA, "Entities in RCSA scope", "pie", size="third"), SCOPE_COLOURS),
     plain(count_by(ENT, ENT_FRAMEWORK, "Entities by framework", size="third")),
     heat(ENT, ENT_TYPE, ENT_RCSA, "Entity type against RCSA scope", size="half"),
     summary(ENT, "Business entity summary", ["Name", ENT_TYPE, ENT_SCOPE, ENT_RCSA, ENT_FRAMEWORK],
             "One row per business entity, with its type, scope and framework.")])

ORM_SECOND_BODY = (
    # ---- loss events ----
    [heading("Loss experience", "What actually happened. Low green, Moderate yellow, High orange, Major red."),
     mix(count_by(LOSS, "OPSS-LossEv:Outcome", "Loss events by outcome", "pie", size="third")),
     tint(count_by(LOSS, LOSS_SEVERITY, "Loss events by severity", size="third"), LOSS_COLOURS),
     plain(count_by(LOSS, BASEL_CATEGORY, "Loss events by Basel category", size="third")),
     heat(LOSS, "OPSS-LossEv:Outcome", LOSS_SEVERITY, "Outcome against severity", size="half"),
     # ---- key risk indicators ----
     heading("Indicator performance", "Breach status, trend and collection. Green green, Yellow yellow, Red red."),
     mix(count_by(KRI, "OPSS-KRI:Status", "KRIs by status", "pie", size="third")),
     tint(count_by(KRI, "OPSS-KRI-Shared:Breach Status", "KRIs by breach status", "pie", size="third"), KRI_COLOURS),
     plain(count_by(KRI, DOMAIN[KRI], "KRIs by domain", size="third")),
     plain(count_by(KRI, "OPSS-KRI:Frequency", "KRIs by frequency", size="third")),
     tint(count_by(KRI, "OPSS-KRI:Indicator Trend", "KRIs by trend", "pie", size="third"), TREND_COLOURS),
     tint(count_by(KRI, KRI_COLLECTION, "KRIs by collection status", "pie", size="third"), COLLECT_COLOURS),
     mix(count_by(KRI, KRI_NATURE, "KRIs by nature", "pie", size="third")),
     # The thresholds move between the KRI's own group and the shared one, so this query is written
     # once per pair and the build step keeps the one that runs.
     {"title": "KRI values against their thresholds", "question": "KRI values against their thresholds",
      "sql": _kri_thresholds(0), "alt_sql": [_kri_thresholds(1)],
      "size": "twothird", "height": 320,
      "chart": {"type": "bar", "x": "Name",
                "y": ["OPSS-KRI:Value", KRI_YELLOW[0], KRI_RED[0]]},
      "style": {"palette": [BLUE, AMBER, RED], "legend": True}},
     # ---- issues ----
     heading("Issue management", "What assessment and testing turned up. Low green, Medium yellow, High orange, "
                       "Critical red."),
     mix(count_by(ISS, "OPSS-Iss:Status", "Issues by status", "pie", size="third")),
     tint(count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="third"), ISS_COLOURS),
     plain(count_by(ISS, "OPSS-Iss:Issue Type", "Issues by type", size="third")),
     plain(count_by(ISS, DOMAIN[ISS], "Issues by domain", size="third")),
     tint(count_by(ISS, "OPSS-Iss:Impact", "Issues by impact", size="third"), ISS_COLOURS),
     tint(count_by(ISS, "OPSS-Iss:Probability", "Issues by probability", size="third"), PROB_COLOURS),
     plain(count_by(ISS, "OPSS-Iss:Root Cause Type", "Issues by root cause", size="half")),
     # A heat map colours by count, not by category, so the rating colours don't apply to it.
     heat(ISS, "OPSS-Iss:Status", "OPSS-Iss:Priority", "Issue status against priority", size="half"),
     # ---- action items ----
     heading("Remediation", "What is being done about all of it. Completed green, In Progress blue, "
                             "Overdue red, Pending orange."),
     tint(count_by(ACT, "OPSS-ActItem:Status", "Action items by status", "pie", size="third"), ACT_COLOURS),
     plain(count_by(ACT, "OPSS-ActItem:Percent Complete", "Action items by percent complete", size="third",
              by_value=True)),
     tint(count_by(ACT, "OPSS-ActItem:Aging Bucket", "Action item ageing", size="third"), AGEING_COLOURS),
     tint(count_by(ACT, "OPSS-ActItem:Approval Status", "Action items by approval status", "pie", size="third"), APPROVAL_COLOURS),
     tint(count_by(ACT, "OPSS-ActItem:Overdue", "Overdue against not yet due", "pie", size="third"), ACT_COLOURS),
     by_month(count_by(ACT, "OPSS-ActItem:Due Date", "Action items by due date", "line", size="third",
                       by_value=True), "OPSS-ActItem:Due Date", "Action items falling due by month"),
     # ---- across the ORM objects ----
     heading("Across ORM", "How the object types line up against each other. OpenPages counts one object "
                           "type per query, so these are joins down the hierarchy rather than one chart of "
                           "everything; the number tiles at the top are the object-wise distribution."),
     by_month(count_by(RSK, "Creation Date", "Risks raised over time", "line", size="third",
                       by_value=True), "Creation Date", "Risks raised by month"),
     by_month(count_by(ISS, "Creation Date", "Issues raised over time", "line", size="third",
                       by_value=True), "Creation Date", "Issues raised by month"),
     by_month(count_by(LOSS, "Creation Date", "Loss events raised over time", "line", size="third",
                       by_value=True), "Creation Date", "Loss events raised by month"),
     paired("Controls on each risk", lambda r:
            f"SELECT [{RSK}].[Name], [{RSK}].[{r}], [{CTL}].[Name], "
            f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] FROM [{RSK}] JOIN [{CTL}] ON PARENT([{RSK}])"),
     paired("KRIs on each risk", lambda r:
            f"SELECT [{RSK}].[Name], [{RSK}].[{r}], [{KRI}].[Name], "
            f"[{KRI}].[OPSS-KRI-Shared:Breach Status] FROM [{RSK}] JOIN [{KRI}] ON PARENT([{RSK}])"),
     table_of("Action items under each issue",
              f"SELECT [{ISS}].[Name], [{ISS}].[OPSS-Iss:Priority], [{ACT}].[Name], "
              f"[{ACT}].[OPSS-ActItem:Status], [{ACT}].[OPSS-ActItem:Due Date] "
              f"FROM [{ISS}] JOIN [{ACT}] ON PARENT([{ISS}])", size="half"),
     rooted(RSK, "Risks by entity", [RESIDUAL, "OPSS-Risk:Status"], size="half")])


ORM_OVERVIEW = report(
    "ORM", "Operational Risk Management — overview",
    "Risks, controls, processes and the business entities they hang under, rated and scoped",
    ORM_COLOR,
    "Show the operational risk picture: risks by rating and treatment, control effectiveness, "
    "process coverage and how much of the entity hierarchy is in scope",
    ORM_FIRST_KPIS + ORM_FIRST_BODY,
    [filter_on("Residual rating", RSK, RESIDUAL),
     filter_on("Control effectiveness", CTL, "OPSS-Ctl:Operating Effectiveness")],
    "Every risk, control and process below hangs under them.", theme="plex")

ORM_EVENTS = report(
    "ORM", "Events, indicators and remediation",
    "Loss events, key risk indicators, issues and action items, and how they join up",
    ORM_COLOR,
    "Show what went wrong, what is being watched, what was raised and what is being done about it: "
    "loss events, key risk indicators, issues and action items",
    ORM_SECOND_KPIS + ORM_SECOND_BODY,
    [filter_on("Breach status", KRI, "OPSS-KRI-Shared:Breach Status"),
     filter_on("Issue priority", ISS, "OPSS-Iss:Priority"),
     filter_on("Action item status", ACT, "OPSS-ActItem:Status")],
    "Every loss event, indicator, issue and action below hangs under them.", theme="plex")


# The number tiles and the trend lines take their ink from what they count: an exception count is
# red and reads better when it falls, the rest stays in the module's own plum or the page's ink.
KPI_INK = {"Major residual risks": RED, "Ineffective controls": RED, "KRIs in red breach": RED,
           "Overdue action items": RED, "Open issues": ORANGE, "Open risks": PLUM}
LINE_INK = {"Risks raised by month": PLUM, "Issues raised by month": ORANGE,
            "Loss events raised by month": PLUM, "Action items falling due by month": BLUE}
for _w in ORM_OVERVIEW["widgets"] + ORM_EVENTS["widgets"]:
    _colour = KPI_INK.get(_w["title"]) or LINE_INK.get(_w["title"])
    if _colour:
        _w["style"] = {**(_w.get("style") or {}), "color": _colour}
    if _w["title"] in KPI_INK and _colour == RED:
        _w["style"]["goodWhen"] = "down"


# ---------- the single-page ORM overview ----------
#
# The two dashboards above are one design across two pages. This is the one-page reading of the
# same object types asked for as an "ORM Overview": twelve number tiles across the top, then one
# band per object type, each drawn as the rings and bar rows the design uses.
#
# Every tile counts its own object type and nothing else - COUNT in OpenPages SQL works on a single
# object type and never alongside a JOIN - so no record is counted twice and no two tiles share a
# query. Charts whose field this installation doesn't have are dropped at build time with the
# reason shown, so the page degrades rather than failing.

ORM_OVERVIEW_KPIS = (
    kpis(RSK, [("Total risks", "")]) +
    kpis(CTL, [("Total controls", "")]) +
    kpis(PRC, [("Total business processes", "")]) +
    kpis(ENT, [("Total business entities", "")]) +
    kpis(LOSS, [("Total loss events", "")]) +
    kpis(KRI, [("Total KRIs", "")]) +
    kpis(ISS, [("Total issues", "")]) +
    kpis(ACT, [("Total action items", "")]) +
    kpis(ISS, [("Open issues", f"[{ISS}].[OPSS-Iss:Status] = 'Open'")]) +
    # Overdue is a stored flag on the action item: OpenPages SQL has no date arithmetic, so
    # "past its due date" cannot be worked out in the query.
    kpis(ACT, [("Overdue action items", f"[{ACT}].[OPSS-ActItem:Overdue] = 'Yes'")]) +
    kpis(RSK, [("Major residual risks", where_any(RSK, RESIDUAL, "= 'Major'"))]) +
    kpis(KRI, [("Red breach KRIs", f"[{KRI}].[OPSS-KRI-Shared:Breach Status] = 'Red'")]))

ORM_OVERVIEW_BODY = [
    # ---- risks ----
    heading("Risk analysis", "How the risks are rated and how much of the exposure sits inside "
                             "tolerance. Minor green, Moderate yellow, Significant orange, Major red."),
    mix(count_by(RSK, RSK_STATUS, "Risks by status", "pie", size="third")),
    tint(count_by(RSK, TOLERANCE, "Risks within tolerance", "pie", size="third"), TOLERANCE_COLOURS),
    plain(count_by(RSK, DOMAIN[RSK], "Risks by domain", size="third")),
    tint(count_by(RSK, INHERENT, "Risks by inherent risk rating", size="half"), RISK_COLOURS),
    tint(count_by(RSK, RESIDUAL, "Risks by residual risk rating", size="half"), RISK_COLOURS),
    # ---- controls ----
    heading("Control analysis", "Coverage and effectiveness. Effective green, Partially Effective "
                                "orange, Ineffective red, Not Determined grey."),
    mix(count_by(CTL, "OPSS-Ctl:Status", "Controls by status", "pie", size="half")),
    mix(count_by(CTL, "OPSS-Ctl:Control Type", "Controls by control type", "pie", size="half")),
    tint(count_by(CTL, "OPSS-Ctl:Design Effectiveness", "Controls by design effectiveness", size="half"),
         CTL_COLOURS),
    tint(count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Controls by operating effectiveness",
                  size="half"), CTL_COLOURS),
    # ---- business processes ----
    heading("Business process analysis", "What the risks and controls hang off, and how much of it "
                                         "is in scope."),
    mix(count_by(PRC, PRC_STATUS, "Processes by status", "pie", size="third")),
    tint(count_by(PRC, PRC_SCOPE, "Processes by in scope", "pie", size="third"), SCOPE_COLOURS),
    plain(count_by(PRC, DOMAIN[PRC], "Processes by domain", size="third")),
    # ---- business entities ----
    heading("Business entity analysis", "The hierarchy everything above sits under, and how much "
                                        "of it is assessed."),
    mix(count_by(ENT, ENT_TYPE, "Business entities by entity type", "pie", size="third")),
    tint(count_by(ENT, ENT_SCOPE, "Business entities by in scope", "pie", size="third"), SCOPE_COLOURS),
    tint(count_by(ENT, ENT_RCSA, "Business entities by in RCSA scope", "pie", size="third"),
         SCOPE_COLOURS),
    plain(count_by(ENT, ENT_FRAMEWORK, "Business entities by framework", size="full")),
    # ---- loss events ----
    heading("Loss event analysis", "What actually happened. Low green, Moderate yellow, High orange, "
                                   "Major red."),
    mix(count_by(LOSS, "OPSS-LossEv:Outcome", "Loss events by outcome", "pie", size="third")),
    tint(count_by(LOSS, LOSS_SEVERITY, "Loss events by severity", size="third"), LOSS_COLOURS),
    plain(count_by(LOSS, BASEL_CATEGORY, "Loss events by Basel risk category L1", size="third")),
    # ---- key risk indicators ----
    heading("KRI analysis", "Breach status and trend on the indicators being watched. Green green, "
                            "Yellow yellow, Red red."),
    mix(count_by(KRI, "OPSS-KRI:Status", "KRIs by status", "pie", size="third")),
    tint(count_by(KRI, "OPSS-KRI-Shared:Breach Status", "KRIs by breach status", "pie", size="third"),
         KRI_COLOURS),
    mix(count_by(KRI, "OPSS-KRI:Frequency", "KRIs by frequency", "pie", size="third")),
    tint(count_by(KRI, "OPSS-KRI:Indicator Trend", "KRIs by indicator trend", size="full"),
         TREND_COLOURS),
    # ---- issues ----
    heading("Issue analysis", "What assessment and testing turned up. Low green, Medium yellow, "
                              "High orange, Critical red."),
    mix(count_by(ISS, "OPSS-Iss:Status", "Issues by status", "pie", size="half")),
    tint(count_by(ISS, "OPSS-Iss:Priority", "Issues by priority", "pie", size="half"), ISS_COLOURS),
    plain(count_by(ISS, "OPSS-Iss:Issue Type", "Issues by issue type", size="third")),
    plain(count_by(ISS, DOMAIN[ISS], "Issues by domain", size="third")),
    plain(count_by(ISS, "OPSS-Iss:Root Cause Type", "Issues by root cause type", size="third")),
    # ---- action items ----
    heading("Action item analysis", "What is being done about all of it. Completed green, In Progress "
                                    "blue, Overdue red, Pending orange. The ageing buckets run "
                                    "1-10, 11-30, 31-60 and above 60 days."),
    tint(count_by(ACT, "OPSS-ActItem:Status", "Action items by status", "pie", size="third"),
         ACT_COLOURS),
    tint(count_by(ACT, "OPSS-ActItem:Overdue", "Overdue against not yet due action items", "pie",
                  size="third"), ACT_COLOURS),
    tint(count_by(ACT, "OPSS-ActItem:Aging Bucket", "Action items by ageing bucket", size="third"),
         AGEING_COLOURS),
    plain(count_by(ACT, "OPSS-ActItem:Percent Complete", "Action items by percent complete",
                   size="full", by_value=True)),
]

ORM_SINGLE_OVERVIEW = {
    "module": "ORM",
    "name": "ORM: ORM overview",
    "description": "One page across risks, controls, processes, entities, loss events, KRIs, issues "
                   "and action items, with the twelve ORM counts across the top",
    "color": ORM_COLOR,
    "prompt": "Give me a single operational risk overview: total risks, controls, business processes, "
              "business entities, loss events, KRIs, issues and action items, with open issues, "
              "overdue actions, major residual risks and red breach KRIs, then a breakdown of each",
    # The one page closes the way every other dashboard does: the records behind the charts, with
    # the entity each one hangs under. It was the only template that ended on a chart.
    "widgets": ORM_OVERVIEW_KPIS + ORM_OVERVIEW_BODY + [
        summary(RSK, "Risk summary", ["Name", "Location", DOMAIN[RSK], INHERENT, RESIDUAL, RSK_STATUS],
                "Every risk with its entity, domain, ratings and status")],
    "filters": [ROOT_FILTER,
                filter_on("Residual rating", RSK, RESIDUAL),
                filter_on("Breach status", KRI, "OPSS-KRI-Shared:Breach Status"),
                filter_on("Action item status", ACT, "OPSS-ActItem:Status")],
    "theme": "plex",
}

# The exception tiles read in the colour of what they count, and fall rather than rise.
for _w in ORM_SINGLE_OVERVIEW["widgets"]:
    _ink = {"Major residual risks": RED, "Red breach KRIs": RED, "Overdue action items": RED,
            "Open issues": ORANGE}.get(_w["title"])
    if _ink:
        _w["style"] = {**(_w.get("style") or {}), "color": _ink, "goodWhen": "down"}


ORM = [
    ORM_SINGLE_OVERVIEW,
    ORM_OVERVIEW,
    ORM_EVENTS,
    report("ORM", "Risk and control profile",
           "Risks and the controls on them, by category, rating and effectiveness, under each entity",
           ORM_COLOR, "Show our operational risk and control profile by business entity",
           kpis(RSK, [("Risks", ""), ("Open risks", f"[{RSK}].[OPSS-Risk:Status] <> 'Closed'")]) +
           kpis(CTL, [("Controls", ""),
                      ("Ineffective controls", f"[{CTL}].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'")]) +
           [count_by(RSK, BASEL_CATEGORY, "Risks by Basel category", size="half"),
            count_by(RSK, RESIDUAL, "Risks by residual rating", size="half"),
            count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Control effectiveness", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Control Method", "Automated or manual", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Classification", "Key against standard controls", "pie", size="third"),
            count_by_two(RSK, RESID_LIKELIHOOD, "OPSS-Risk:Residual Impact",
                         "Residual likelihood by impact", size="half"),
            rooted(RSK, "Risks by entity", [RESIDUAL, "OPSS-Risk:Status"])],
           [filter_on("Residual rating", RSK, RESIDUAL)]),
    report("ORM", "Loss events",
           "Loss events by status, Basel category, business line and outcome, with impacts and recoveries",
           ORM_COLOR, "Show operational loss events and their impacts by business entity",
           kpis(LOSS, [("Loss events", ""), ("Open loss events", f"[{LOSS}].[OPSS-LossEv:Status] = 'Open'"),
                       ("Near misses", f"[{LOSS}].[OPSS-LossEv:Outcome] = 'Near Miss'"),
                       ("Approved", f"[{LOSS}].[OPSS-LossEv:Approval Status] = 'Approved'")]) +
           [count_by(LOSS, BASEL_CATEGORY, "Loss events by Basel category", size="half"),
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
            count_by(SCEN, BASEL_CATEGORY, "Scenarios by Basel category", size="third"),
            count_by(SRES, "OPSS-ScenRes:Severity", "Results by severity", size="half"),
            rooted(SCEN, "Scenarios by entity", ["OPSS-ScenAn:Status", "OPSS-ScenAn:Scenario Type"],
                   direct=True)]),
    report("ORM", "Process and sub-process coverage",
           "Which processes carry risks and controls, and which are still unassessed",
           ORM_COLOR, "Which processes and sub-processes are covered by risks and controls?",
           kpis(PRC, [("Processes", "")]) + kpis(SUB, [("Sub-processes", "")]) +
           kpis(RSK, [("Risks", "")]) + kpis(CTL, [("Controls", "")]) +
           [count_by(PRC, PRC_STATUS, "Processes by status", "pie", size="third"),
            count_by(PRC, "OPSS-Proc:Process Type", "Processes by type", "pie", size="third"),
            count_by(SUB, "OPSS-Subproc:Status", "Sub-processes by status", "pie", size="third"),
            count_by(PEVAL, "OPSS-ProcEval:Conclusion", "Process evaluation conclusions", size="half"),
            rooted(PRC, "Processes by entity", [PRC_STATUS, "OPSS-Proc:Process Type"], direct=True),
            # A risk hangs directly off its process in every shipped object model, so this is a
            # direct join, which may select the process's own name. An indirect (ANCESTOR) join
            # may not - see rooted().
            table_of("Risks under each process",
                     f"SELECT [{PRC}].[Name], [{RSK}].[Name], [{RSK}].[{RESIDUAL[0]}] "
                     f"FROM [{PRC}] JOIN [{RSK}] ON PARENT([{PRC}])")]),
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
           [count_by(ORX, BASEL_CATEGORY, "ORX losses by Basel category", size="half"),
            count_by(FIRST, BASEL_CATEGORY, "FIRST losses by Basel category", size="half"),
            count_by(ORX, "OPSS-ORXLoss:Business Line", "ORX losses by business line", size="half"),
            count_by(LOSS, "OPSS-LossEv:Business Line", "Our losses by business line", size="half"),
            rooted(ORX, "External losses by entity", [BASEL_CATEGORY], direct=True)]),
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
            table_of("Attestations, with the entity each sits under",
                     f"SELECT [{ATT}].[Location], [{ATT}].[Name], [{ATT}].[OPSS-Att:Status], [{ATT}].[OPSS-Att:Response] FROM [{ATT}]"),
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
            table_of("Requirements, with the entity each sits under",
                     f"SELECT [{REQ}].[Location], [{REQ}].[Name], [{REQ}].[OPSS-Req:Status] FROM [{REQ}]"),
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
            table_of("Regulatory tasks, with the entity each sits under",
                     f"SELECT [{REGTASK}].[Location], [{REGTASK}].[Name], [{REGTASK}].[OPSS-RegTask:Status], [{REGTASK}].[OPSS-RegTask:Priority] FROM [{REGTASK}]"),
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
            table_of("Procedures, with the entity each sits under",
                     f"SELECT [{PRCD}].[Location], [{PRCD}].[Name], [{PRCD}].[OPSS-Prcd:Approval Status] FROM [{PRCD}]"),
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
            table_of("Model reviews, with the entity each sits under",
                     f"SELECT [{REVIEW}].[Location], [{REVIEW}].[Name], [{REVIEW}].[OPSS-Rev:Status], [{REVIEW}].[OPSS-Rev:Outcome] FROM [{REVIEW}]"),
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
            table_of("Change requests, with the entity each sits under",
                     f"SELECT [{CHG}].[Location], [{CHG}].[Name], [{CHG}].[OPSS-ChgReq:Status], [{CHG}].[OPSS-ChgReq:Change Type] FROM [{CHG}]"),
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
            table_of("Model attestations, with the entity each sits under",
                     f"SELECT [{MATT}].[Location], [{MATT}].[Name], [{MATT}].[OPSS-MdlAtt:Status] FROM [{MATT}]"),
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
            table_of("Issues, with the entity each sits under",
                     f"SELECT [{ISS}].[Location], [{ISS}].[Name], [{ISS}].[OPSS-Iss:Status], [{ISS}].[OPSS-Iss:Priority] FROM [{ISS}]"),
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
            table_of("Findings, with the entity each sits under",
                     f"SELECT [{FND}].[Location], [{FND}].[Name], [{FND}].[OPSS-Finding:Status] FROM [{FND}]")]),
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
            table_of("Baselines, with the entity each sits under",
                     f"SELECT [{BASE}].[Location], [{BASE}].[Name], [{BASE}].[OPSS-Base:Status] FROM [{BASE}]"),
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
            table_of("Procedures, with the entity each sits under",
                     f"SELECT [{PRCD}].[Location], [{PRCD}].[Name], [{PRCD}].[OPSS-Prcd:Approval Status] FROM [{PRCD}]"),
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
           [count_by(PRC, PRC_STATUS, "Processes by status", "pie", size="third"),
            count_by(PRC, "OPSS-Proc:Process Type", "Processes by type", "pie", size="third"),
            count_by(SUB, "OPSS-Subproc:Status", "Sub-processes by status", size="third"),
            table_of("Sub-processes under each process",
                     f"SELECT [{PRC}].[Name], [{SUB}].[Name], [{SUB}].[OPSS-Subproc:Status] "
                     f"FROM [{PRC}] JOIN [{SUB}] ON PARENT([{PRC}])"),
            rooted(PRC, "Processes by entity", [PRC_STATUS], direct=True)]),
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
            count_by_two(RSK, RESID_LIKELIHOOD, "OPSS-Risk:Residual Impact",
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
           [count_by(RSK, RESIDUAL, "Risks by residual rating", size="half"),
            count_by(RSK, "OPSS-Risk:Status", "Risks by status", "pie", size="third"),
            count_by(CTL, "OPSS-Ctl:Operating Effectiveness", "Control effectiveness", "pie", size="third"),
            count_by_two(RSK, RESID_LIKELIHOOD, "OPSS-Risk:Residual Impact",
                         "Residual likelihood by impact", size="half"),
            rooted(RSK, "Risks by entity", [RESIDUAL, "OPSS-Risk:Status"])]),
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
            count_by(RSK, RESIDUAL, "Vendor risks by rating", size="third"),
            table_of("Risk assessments, with the entity each sits under",
                     f"SELECT [{RASS}].[Location], [{RASS}].[Name], [{RASS}].[OPSS-RiskAssess:Status] FROM [{RASS}]"),
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
            table_of("Contracts, with the entity each sits under",
                     f"SELECT [{CONT}].[Location], [{CONT}].[Name], [{CONT}].[OPSS-Cont:Status], [{CONT}].[OPSS-Cont:End Date] FROM [{CONT}]"),
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
            table_of("Engagements, with the entity each sits under",
                     f"SELECT [{ENG}].[Location], [{ENG}].[Name], [{ENG}].[OPSS-Eng:Status], [{ENG}].[OPSS-Eng:Criticality] FROM [{ENG}]"),
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
            table_of("Subcontractors, with the entity each sits under",
                     f"SELECT [{SUBC}].[Location], [{SUBC}].[Name], [{SUBC}].[OPSS-Subc:Status] FROM [{SUBC}]"),
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
            table_of("Issues, with the entity each sits under",
                     f"SELECT [{ISS}].[Location], [{ISS}].[Name], [{ISS}].[OPSS-Iss:Status], [{ISS}].[OPSS-Iss:Priority] FROM [{ISS}]"),
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
    """The module reports as rows for report_templates.

    They go through the same tidy-up as the shorter templates (openpages_templates.normalise): a
    full dashboard where the fields allow it, the summary table last, and a business entity filter
    on every one. These already satisfied all three by hand - running them through it is what
    keeps that true of the next one somebody writes.
    """
    return [{"name": r["name"], "description": r["description"], "color": r["color"], "prompt": r["prompt"],
             "category": "GRC", "module": r["module"],
             "layout": {"kind": "dashboard", "source_type": "openpages",
                        "widgets": normalise(r["widgets"]),
                        "filters": with_entity_filter(r["filters"]),
                        **({"theme": r["theme"]} if r.get("theme") else {})}}
            for r in MODULE_REPORTS]
