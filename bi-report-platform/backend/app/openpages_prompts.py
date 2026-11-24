"""
The ten reference dashboards for IBM OpenPages, one per namespace of the reporting framework.

These are not worked out from the connection: they are written against the published object model,
each one naming only the parent/child pairs its own namespace actually lists. That is the whole
point of them - a prompt written for ORM2 does not work against ORM1, and the relationship tables
are where the difference shows. They are offered ahead of anything derived from the connection
because a hand-written prompt that names the real pairs beats a guess at them every time.

Source: Openpages_model/OpenPages Report Prompts.docx, with one correction. The document's
cross-namespace report said its relationship tables used "only the pairs every namespace shares";
checked against Openpages_model/openpagesobjectmodelnamespace, no pair is in all nine namespaces
and only [SOXBusEntity] is in all of them. That section now uses [Location] and no joins, which is
what actually survives any namespace. test_openpages_prompts.py checks every join in every prompt
against the object model, so the next edit cannot reintroduce one.

Each prompt is self-contained - it carries
its own rules for the OpenPages Query Service - so it can be edited in the box before building
without losing the constraints that make it run.

Each is 30 to 50 widgets, which is why MAX_WIDGETS (schemas.py) is 60.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CuratedPrompt:
    """One reference dashboard: what it is, which namespace it reads, and the request itself."""

    id: str
    title: str
    # The namespace of the reporting framework it is written against.
    namespace: str
    # That namespace as openpages_model keys it, so picking this report also sets the data model
    # and the query writer is given the real parent/child pairs instead of guessing at them.
    # Empty for the cross-namespace report, which is written to need no joins at all.
    model_key: str
    why: str
    prompt: str
    charts: int


CURATED: tuple[CuratedPrompt, ...] = (
    CuratedPrompt(
        id='curated-enterprise-grc-control-tower',
        title='Enterprise GRC Control Tower',
        namespace='Operational_Risk_and_Control / DEFAULT',
        model_key='operational_risk_and_control/default',
        why='The whole default model on one page: what the organisation is made of, how well it is controlled, what it has lost and what is being watched. This is the board-level read.',
        charts=42,
        prompt=r"""Build an "Enterprise GRC Control Tower" dashboard on this IBM OpenPages connection, using
the DEFAULT namespace of the Operational Risk and Control model.
 
1. KPI CARDS - 12 "kpi" widgets, each a COUNT of [Resource ID] on one object type
   Business Entities   COUNT [SOXBusEntity]
   Processes           COUNT [SOXProcess]
   Sub-processes       COUNT [SOXSubprocess]
   Risks               COUNT [SOXRisk]
   Controls            COUNT [SOXControl]
   Control Tests       COUNT [SOXTest]
   Test Results        COUNT [SOXTestResult]
   Loss Events         COUNT [LossEvent]
   Key Risk Indicators COUNT [KeyRiskIndicator]
   Risk Assessments    COUNT [RiskAssessment]
   Ineffective Controls COUNT [SOXControl] WHERE [SOXControl].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'
   Major Residual Risks COUNT [SOXRisk] WHERE [SOXRisk].[OPSS-Risk:Residual Risk Rating] = 'Major'
   Ink the last two red and mark them good when they fall.
 
2. ENTITY AND PROCESS STRUCTURE
   Entities by Entity Type  - donut - [SOXBusEntity].[OPSS-Ent:Entity Type]
   Entities by In Scope     - donut - [SOXBusEntity].[OPSS-Ent:In Scope]
   Processes by Status      - donut - [SOXProcess].[OPSS-Proc:Status]
   Processes by Category    - bar   - [SOXProcess].[OPSS-Proc:Process Category]
   Sub-processes by Status  - bar   - [SOXSubprocess].[OPSS-Subproc:Status]
   Entity Summary - table - SELECT [Name], [OPSS-Ent:Entity Type], [OPSS-Ent:In Scope],
     [OPSS-Ent:RCSA Scope], [OPSS-Ent:Country], [OPSS-Ent:Status] FROM [SOXBusEntity]
 
3. RISK AND CONTROL
   Risks by Residual Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risks by Inherent Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Risks by Status               - donut - [SOXRisk].[OPSS-Risk:Status]
   Controls by Operating Effectiveness - bar   - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Controls by Design Effectiveness    - bar   - [SOXControl].[OPSS-Ctl:Design Effectiveness]
   Controls by Classification          - donut - [SOXControl].[OPSS-Ctl:Classification]
   Colour: Minor green, Moderate yellow, Significant orange, Major red; Effective green,
   Partially Effective orange, Ineffective red, Not Determined grey.
   Risk Summary - table - SELECT [Name], [OPSS-Risk:Risk Domain], [OPSS-Risk:Inherent Risk Rating],
     [OPSS-Risk:Residual Risk Rating], [OPSS-Risk:Status], [Location] FROM [SOXRisk]
   Control Summary - table - SELECT [Name], [OPSS-Ctl:Control Type], [OPSS-Ctl:Control Method],
     [OPSS-Ctl:Design Effectiveness], [OPSS-Ctl:Operating Effectiveness], [OPSS-Ctl:Status],
     [Location] FROM [SOXControl]
 
4. TESTING
   Tests by Status          - donut - [SOXTest].[OPSS-Test:Status]
   Tests by Test Type       - donut - [SOXTest].[OPSS-Test:Test Type]
   Test Results by Conclusion - bar - [SOXTestResult].[OPSS-TestRes:Conclusion]
   Test Results by Exceptions - bar - [SOXTestResult].[OPSS-TestRes:Exceptions]
   Test Summary - table - SELECT [Name], [OPSS-Test:Test Type], [OPSS-Test:Frequency],
     [OPSS-Test:Status], [Creation Date], [Location] FROM [SOXTest]
 
5. LOSS EXPERIENCE
   Loss Events by Outcome  - donut - [LossEvent].[OPSS-LossEv:Outcome]
   Loss Events by Severity - bar   - [LossEvent].[OPSS-LossEv:Severity]
   Loss Events by Basel Risk Category L1 - bar - [LossEvent].[OPSS-Shared-Basel:Risk Category L1]
   Loss Impacts by Impact Category       - donut - [LossImpact].[OPSS-LossImp:Impact Category]
   Loss Recoveries by Recovery Category  - donut - [LossRecovery].[OPSS-LossRec:Recovery Category]
   Loss Event Summary - table - SELECT [Name], [OPSS-LossEv:Status], [OPSS-LossEv:Outcome],
     [OPSS-LossEv:Severity], [OPSS-LossEv:Gross Loss], [OPSS-LossEv:Net Loss],
     [OPSS-LossEv:Occurrence Date], [Location] FROM [LossEvent]
 
6. INDICATORS AND ACCOUNTS
   KRIs by Breach Status  - donut - [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status]
   KRIs by Indicator Trend - bar  - [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
   KPIs by Status         - donut - [KeyPerfIndicator].[OPSS-KPI:Status]
   Accounts by Significance - donut - [SOXAccount].[OPSS-Acc:Significant]
   KRI Summary - table - SELECT [Name], [OPSS-KRI:Status], [OPSS-KRI-Shared:Breach Status],
     [OPSS-KRI:Indicator Trend], [OPSS-KRI:Frequency], [OPSS-KRI:Value],
     [OPSS-KRI:Unit of Measure] FROM [KeyRiskIndicator]
 
7. RELATIONSHIP TABLES - one per pair in the namespace's object model, each a direct parent join
   Processes under each entity   - SELECT [SOXBusEntity].[Name], [SOXProcess].[Name],
     [SOXProcess].[OPSS-Proc:Status], [SOXProcess].[OPSS-Proc:Process Category]
     FROM [SOXBusEntity] JOIN [SOXProcess] ON PARENT([SOXBusEntity])
   Risks under each sub-process  - SELECT [SOXSubprocess].[Name], [SOXRisk].[Name],
     [SOXRisk].[OPSS-Risk:Residual Risk Rating], [SOXRisk].[OPSS-Risk:Status]
     FROM [SOXSubprocess] JOIN [SOXRisk] ON PARENT([SOXSubprocess])
   Controls on each risk         - SELECT [SOXRisk].[Name], [SOXRisk].[OPSS-Risk:Residual Risk Rating],
     [SOXControl].[Name], [SOXControl].[OPSS-Ctl:Operating Effectiveness]
     FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
   Tests on each control         - SELECT [SOXControl].[Name], [SOXTest].[Name],
     [SOXTest].[OPSS-Test:Test Type], [SOXTest].[OPSS-Test:Status]
     FROM [SOXControl] JOIN [SOXTest] ON PARENT([SOXControl])
   Results of each test          - SELECT [SOXTest].[Name], [SOXTestResult].[Name],
     [SOXTestResult].[OPSS-TestRes:Conclusion], [SOXTestResult].[OPSS-TestRes:Exceptions]
     FROM [SOXTest] JOIN [SOXTestResult] ON PARENT([SOXTest])
   Impacts of each loss event    - SELECT [LossEvent].[Name], [LossImpact].[Name],
     [LossImpact].[OPSS-LossImp:Impact Category], [LossImpact].[OPSS-LossImp:Effect Subcategory]
     FROM [LossEvent] JOIN [LossImpact] ON PARENT([LossEvent])
   Readings of each KRI          - SELECT [KeyRiskIndicator].[Name], [KeyRiskIndicatorValue].[Name],
     [KeyRiskIndicatorValue].[OPSS-KRIVal:Period], [KeyRiskIndicatorValue].[OPSS-KRIVal:Value]
     FROM [KeyRiskIndicator] JOIN [KeyRiskIndicatorValue] ON PARENT([KeyRiskIndicator])
   Sub-accounts and assertions   - SELECT [SOXAccount].[Name], [SOXSubaccount].[Name],
     [SOXSubaccount].[OPSS-Subacc:Status] FROM [SOXAccount] JOIN [SOXSubaccount] ON PARENT([SOXAccount])
 
Filters: business entity on [Location], residual risk rating, control operating effectiveness,
loss event severity.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-operational-loss-incident-and-scenario-b',
        title='Operational Loss, Incident and Scenario Book',
        namespace='Operational_Risk_and_Control / ORM1',
        model_key='operational_risk_and_control/orm1',
        why='Everything that actually went wrong and everything modelled as possibly going wrong: losses, their impacts and recoveries, incidents, external ORX losses, scenarios and their results, with the evaluations behind the risk and control ratings.',
        charts=36,
        prompt=r"""Build an "Operational Loss, Incident and Scenario Book" dashboard on this IBM OpenPages
connection, using the ORM1 namespace.
 
1. KPI CARDS - 10 "kpi" widgets
   Loss Events        COUNT [LossEvent]
   Loss Impacts       COUNT [LossImpact]
   Loss Recoveries    COUNT [LossRecovery]
   External ORX Losses COUNT [ORXLoss]
   Incidents          COUNT [Incident]
   Scenario Analyses  COUNT [ScenarioAnalysis]
   Scenario Results   COUNT [ScenarioResult]
   Risk Evaluations   COUNT [RiskEval]
   Control Evaluations COUNT [CtlEval]
   Open Incidents     COUNT [Incident] WHERE [Incident].[OPSS-Inc:Status] = 'Open'
   Ink Open Incidents red and mark it good when it falls.
 
2. LOSS EVENTS
   Loss Events by Outcome   - donut - [LossEvent].[OPSS-LossEv:Outcome]
   Loss Events by Status    - donut - [LossEvent].[OPSS-LossEv:Status]
   Loss Events by Severity  - bar   - [LossEvent].[OPSS-LossEv:Severity]
   Loss Events by Business Line - bar - [LossEvent].[OPSS-LossEv:Business Line]
   Loss Events by Basel Risk Category L1 - bar - [LossEvent].[OPSS-Shared-Basel:Risk Category L1]
   Colour: Low green, Moderate yellow, High orange, Major red.
   Loss Event Summary - table - SELECT [Name], [OPSS-LossEv:Status], [OPSS-LossEv:Outcome],
     [OPSS-LossEv:Severity], [OPSS-LossEv:Gross Loss], [OPSS-LossEv:Net Loss],
     [OPSS-LossEv:Occurrence Date], [Location] FROM [LossEvent]
 
3. IMPACT AND RECOVERY
   Impacts by Impact Category    - donut - [LossImpact].[OPSS-LossImp:Impact Category]
   Impacts by Effect Subcategory - bar   - [LossImpact].[OPSS-LossImp:Effect Subcategory]
   Recoveries by Recovery Category - donut - [LossRecovery].[OPSS-LossRec:Recovery Category]
   Recoveries by Status          - donut - [LossRecovery].[OPSS-LossRec:Status]
   Impact Summary - table - SELECT [Name], [OPSS-LossImp:Impact Category],
     [OPSS-LossImp:Effect Subcategory], [Creation Date], [Location] FROM [LossImpact]
   Add [Description] as a fifth column if the object type has it.
 
4. INCIDENTS
   Incidents by Severity      - bar   - [Incident].[OPSS-Inc:Severity]
   Incidents by Status        - donut - [Incident].[OPSS-Inc:Status]
   Incidents by Incident Type - donut - [Incident].[OPSS-Inc:Incident Type]
   Incidents by Root Cause    - bar   - [Incident].[OPSS-Inc:Root Cause]
   Incidents by Notifiable    - donut - [Incident].[OPSS-Inc:Notifiable]
   Incident Summary - table - SELECT [Name], [OPSS-Inc:Incident Type], [OPSS-Inc:Severity],
     [OPSS-Inc:Status], [OPSS-Inc:Root Cause], [OPSS-Inc:Loss Amount],
     [OPSS-Inc:Occurrence Date], [Location] FROM [Incident]
 
5. SCENARIO ANALYSIS
   Scenarios by Scenario Type - donut - [ScenarioAnalysis].[OPSS-ScenAn:Scenario Type]
   Scenarios by Status        - donut - [ScenarioAnalysis].[OPSS-ScenAn:Status]
   Scenario Results by Severity - bar - [ScenarioResult].[OPSS-ScenRes:Severity]
   Scenario Summary - table - SELECT [Name], [OPSS-ScenAn:Scenario Type], [OPSS-ScenAn:Status],
     [Description], [Creation Date], [Location] FROM [ScenarioAnalysis]
 
6. EVALUATIONS BEHIND THE RATINGS
   Risk Evaluations by Residual Risk Rating - bar - [RiskEval].[OPSS-RiskEval:Residual Risk Rating]
   Risk Evaluations by Inherent Risk Rating - bar - [RiskEval].[OPSS-RiskEval:Inherent Risk Rating]
   Control Evaluations by Operating Effectiveness - bar - [CtlEval].[OPSS-CtlEval:Operating Effectiveness]
   Control Evaluations by Design Effectiveness    - bar - [CtlEval].[OPSS-CtlEval:Design Effectiveness]
   External ORX Losses by Business Line - bar - [ORXLoss].[OPSS-ORXLoss:Business Line]
 
7. RELATIONSHIP TABLES
   Impacts of each loss event    - SELECT [LossEvent].[Name], [LossEvent].[OPSS-LossEv:Severity],
     [LossImpact].[Name], [LossImpact].[OPSS-LossImp:Impact Category]
     FROM [LossEvent] JOIN [LossImpact] ON PARENT([LossEvent])
   Recoveries of each loss event - SELECT [LossEvent].[Name], [LossRecovery].[Name],
     [LossRecovery].[OPSS-LossRec:Recovery Category], [LossRecovery].[OPSS-LossRec:Status]
     FROM [LossEvent] JOIN [LossRecovery] ON PARENT([LossEvent])
   Results of each scenario      - SELECT [ScenarioAnalysis].[Name],
     [ScenarioAnalysis].[OPSS-ScenAn:Scenario Type], [ScenarioResult].[Name],
     [ScenarioResult].[OPSS-ScenRes:Severity]
     FROM [ScenarioAnalysis] JOIN [ScenarioResult] ON PARENT([ScenarioAnalysis])
   Evaluations of each risk      - SELECT [SOXRisk].[Name], [RiskEval].[Name],
     [RiskEval].[OPSS-RiskEval:Residual Risk Rating], [RiskEval].[OPSS-RiskEval:Status]
     FROM [SOXRisk] JOIN [RiskEval] ON PARENT([SOXRisk])
   Root cause analyses per control - SELECT [SOXControl].[Name], [RootCauseAnalysis].[Name],
     [RootCauseAnalysis].[Description] FROM [SOXControl] JOIN [RootCauseAnalysis] ON PARENT([SOXControl])
 
Filters: business entity on [Location], loss event severity, incident status, scenario type.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-risk-appetite-and-indicator-monitoring',
        title='Risk Appetite and Indicator Monitoring',
        namespace='Operational_Risk_and_Control / ORM2',
        model_key='operational_risk_and_control/orm2',
        why='The namespace where indicators and losses hang off the risk itself rather than the entity. The report reads appetite: which risks are watched, what the readings say, and which risks have actually produced losses.',
        charts=32,
        prompt=r"""Build a "Risk Appetite and Indicator Monitoring" dashboard on this IBM OpenPages connection,
using the ORM2 namespace, where KeyRiskIndicator and LossEvent are children of SOXRisk.
 
1. KPI CARDS - 10 "kpi" widgets
   Risks                COUNT [SOXRisk]
   Controls             COUNT [SOXControl]
   Key Risk Indicators  COUNT [KeyRiskIndicator]
   KRI Readings         COUNT [KeyRiskIndicatorValue]
   Loss Events          COUNT [LossEvent]
   Processes            COUNT [SOXProcess]
   Sub-processes        COUNT [SOXSubprocess]
   Red Breach KRIs      COUNT [KeyRiskIndicator] WHERE [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status] = 'Red'
   KRIs Trending Worse  COUNT [KeyRiskIndicator] WHERE [KeyRiskIndicator].[OPSS-KRI:Indicator Trend] = 'Worse'
   Major Residual Risks COUNT [SOXRisk] WHERE [SOXRisk].[OPSS-Risk:Residual Risk Rating] = 'Major'
   Ink the last three red and mark them good when they fall.
 
2. RISK APPETITE
   Risks by Residual Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risks by Inherent Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Risks Within Tolerance        - donut - [SOXRisk].[OPSS-Risk:Within Risk Tolerance]
   Risks by Risk Treatment       - donut - [SOXRisk].[OPSS-Risk:Risk Treatment]
   Risks by Domain               - bar   - [SOXRisk].[OPSS-Risk:Risk Domain]
   Risk Summary - table - SELECT [Name], [OPSS-Risk:Risk Domain], [OPSS-Risk:Inherent Risk Rating],
     [OPSS-Risk:Residual Risk Rating], [OPSS-Risk:Within Risk Tolerance],
     [OPSS-Risk:Risk Treatment], [OPSS-Risk:Status] FROM [SOXRisk]
 
3. INDICATORS
   KRIs by Breach Status    - donut - [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status]
   KRIs by Indicator Trend  - bar   - [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
   KRIs by Frequency        - donut - [KeyRiskIndicator].[OPSS-KRI:Frequency]
   KRIs by Collection Status - donut - [KeyRiskIndicator].[OPSS-KRI-Shared:Collection Status]
   Colour: Green green, Yellow yellow, Red red; Improving green, Stable blue, Worse red.
   KRI value against thresholds - bar - SELECT [KeyRiskIndicator].[Name],
     [KeyRiskIndicator].[OPSS-KRI:Value], [KeyRiskIndicator].[OPSS-KRI-Shared:Yellow Threshold],
     [KeyRiskIndicator].[OPSS-KRI-Shared:Red Threshold] FROM [KeyRiskIndicator]
     WHERE [KeyRiskIndicator].[OPSS-KRI:Value] IS NOT NULL ORDER BY [KeyRiskIndicator].[Name]
     Three series on one chart: value blue, yellow threshold amber, red threshold red.
   KRI Summary - table - SELECT [Name], [OPSS-KRI:Status], [OPSS-KRI-Shared:Breach Status],
     [OPSS-KRI:Indicator Trend], [OPSS-KRI:Frequency], [OPSS-KRI:Value],
     [OPSS-KRI:Unit of Measure], [OPSS-KRI:Value Date] FROM [KeyRiskIndicator]
 
4. READINGS
   Readings by Period - bar - [KeyRiskIndicatorValue].[OPSS-KRIVal:Period], kept in period order
   Reading Summary - table - SELECT [Name], [OPSS-KRIVal:Period], [OPSS-KRIVal:Value],
     [Creation Date], [Location] FROM [KeyRiskIndicatorValue] ORDER BY [OPSS-KRIVal:Period]
 
5. LOSSES AGAINST THOSE RISKS
   Loss Events by Outcome  - donut - [LossEvent].[OPSS-LossEv:Outcome]
   Loss Events by Severity - bar   - [LossEvent].[OPSS-LossEv:Severity]
   Loss Event Summary - table - SELECT [Name], [OPSS-LossEv:Status], [OPSS-LossEv:Outcome],
     [OPSS-LossEv:Severity], [OPSS-LossEv:Gross Loss], [OPSS-LossEv:Occurrence Date]
     FROM [LossEvent]
 
6. CONTROLS AND EVALUATIONS
   Controls by Operating Effectiveness - bar - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Controls by Control Type            - donut - [SOXControl].[OPSS-Ctl:Control Type]
   Control Evaluations by Operating Effectiveness - bar - [CtlEval].[OPSS-CtlEval:Operating Effectiveness]
   Risk Evaluations by Residual Risk Rating       - bar - [RiskEval].[OPSS-RiskEval:Residual Risk Rating]
   Control Summary - table - SELECT [Name], [OPSS-Ctl:Control Type], [OPSS-Ctl:Control Method],
     [OPSS-Ctl:Design Effectiveness], [OPSS-Ctl:Operating Effectiveness], [OPSS-Ctl:Status]
     FROM [SOXControl]
 
7. RELATIONSHIP TABLES - these three are what makes ORM2 different from ORM1, so include them all
   KRIs on each risk          - SELECT [SOXRisk].[Name], [SOXRisk].[OPSS-Risk:Residual Risk Rating],
     [KeyRiskIndicator].[Name], [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status],
     [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
     FROM [SOXRisk] JOIN [KeyRiskIndicator] ON PARENT([SOXRisk])
   Loss events on each risk   - SELECT [SOXRisk].[Name], [SOXRisk].[OPSS-Risk:Residual Risk Rating],
     [LossEvent].[Name], [LossEvent].[OPSS-LossEv:Severity], [LossEvent].[OPSS-LossEv:Outcome]
     FROM [SOXRisk] JOIN [LossEvent] ON PARENT([SOXRisk])
   Controls on each risk      - SELECT [SOXRisk].[Name], [SOXControl].[Name],
     [SOXControl].[OPSS-Ctl:Operating Effectiveness], [SOXControl].[OPSS-Ctl:Control Type]
     FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
   Readings of each KRI       - SELECT [KeyRiskIndicator].[Name], [KeyRiskIndicatorValue].[Name],
     [KeyRiskIndicatorValue].[OPSS-KRIVal:Period], [KeyRiskIndicatorValue].[OPSS-KRIVal:Value]
     FROM [KeyRiskIndicator] JOIN [KeyRiskIndicatorValue] ON PARENT([KeyRiskIndicator])
 
Filters: business entity on [Location], KRI breach status, residual risk rating, loss severity.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-conduct-risk-complaints-investigations-a',
        title='Conduct Risk: Complaints, Investigations and Redress',
        namespace='Operational_Risk_and_Control / ORM3',
        model_key='operational_risk_and_control/orm3',
        why='The conduct chain: a complaint, what was found when it was investigated, and what the customer was given. Plus the scenario-to-loss link that only ORM3 carries.',
        charts=30,
        prompt=r"""Build a "Conduct Risk: Complaints, Investigations and Redress" dashboard on this IBM
OpenPages connection, using the ORM3 namespace.
 
Customer Complaint, Investigation and Outcome and Redress are solution objects whose object type
names contain spaces - write them as [Customer Complaint], [Investigation] and
[Outcome and Redress], brackets included, exactly as shown. Read each object type's own field list
before writing its charts and use the status, type, category and date fields it actually has; do
not guess an OPSS field group name for them. Every chart below names the field by its meaning, so
substitute the real field name you find.
 
1. KPI CARDS - 9 "kpi" widgets
   Customer Complaints  COUNT [Customer Complaint]
   Investigations       COUNT [Investigation]
   Outcomes and Redress COUNT [Outcome and Redress]
   Scenario Analyses    COUNT [ScenarioAnalysis]
   Scenario Results     COUNT [ScenarioResult]
   Loss Events          COUNT [LossEvent]
   Loss Impacts         COUNT [LossImpact]
   Loss Recoveries      COUNT [LossRecovery]
   Open Complaints      COUNT [Customer Complaint] WHERE its status field is the open value
   Ink Open Complaints red and mark it good when it falls.
 
2. COMPLAINTS
   Complaints by Status            - donut - the complaint status field
   Complaints by Complaint Type / Category - donut - the complaint type or category field
   Complaints by Product           - bar   - the product field, if present
   Complaints by Root Cause        - bar   - the root cause field, if present
   Complaints by Channel           - donut - the channel or source field, if present
   Complaint Summary - table - SELECT [Name], [Description], the status field, the type field,
     the product field, [Creation Date], [Location] FROM [Customer Complaint]
     At least 5 columns; drop any that does not exist and say so.
 
3. INVESTIGATIONS
   Investigations by Status   - donut - the investigation status field
   Investigations by Outcome / Finding - bar - the outcome or finding field
   Investigations by Type     - donut - the investigation type field
   Investigation Summary - table - SELECT [Name], [Description], the status field,
     the outcome field, [Creation Date], [Location] FROM [Investigation]
 
4. OUTCOME AND REDRESS
   Redress by Outcome Type    - donut - the outcome type field
   Redress by Status          - donut - the status field
   Redress by Upheld / Not Upheld - donut - the upheld field, if present
   Redress Summary - table - SELECT [Name], [Description], the outcome type field,
     the status field, the redress amount field, [Creation Date] FROM [Outcome and Redress]
 
5. SCENARIOS AND THE LOSSES MODELLED UNDER THEM
   Scenarios by Scenario Type   - donut - [ScenarioAnalysis].[OPSS-ScenAn:Scenario Type]
   Scenarios by Status          - donut - [ScenarioAnalysis].[OPSS-ScenAn:Status]
   Scenario Results by Severity - bar   - [ScenarioResult].[OPSS-ScenRes:Severity]
   Loss Events by Outcome       - donut - [LossEvent].[OPSS-LossEv:Outcome]
   Loss Events by Severity      - bar   - [LossEvent].[OPSS-LossEv:Severity]
   Scenario Summary - table - SELECT [Name], [Description], [OPSS-ScenAn:Scenario Type],
     [OPSS-ScenAn:Status], [Creation Date], [Location] FROM [ScenarioAnalysis]
   Loss Event Summary - table - SELECT [Name], [OPSS-LossEv:Status], [OPSS-LossEv:Outcome],
     [OPSS-LossEv:Severity], [OPSS-LossEv:Gross Loss], [OPSS-LossEv:Occurrence Date]
     FROM [LossEvent]
 
6. RELATIONSHIP TABLES
   Investigations per complaint - SELECT [Customer Complaint].[Name], [Investigation].[Name],
     [Investigation].[Description] and the investigation status field
     FROM [Customer Complaint] JOIN [Investigation] ON PARENT([Customer Complaint])
   Redress per complaint        - SELECT [Customer Complaint].[Name], [Outcome and Redress].[Name],
     the outcome type field and the redress amount field
     FROM [Customer Complaint] JOIN [Outcome and Redress] ON PARENT([Customer Complaint])
   Loss events under each scenario - SELECT [ScenarioAnalysis].[Name],
     [ScenarioAnalysis].[OPSS-ScenAn:Scenario Type], [LossEvent].[Name],
     [LossEvent].[OPSS-LossEv:Severity]
     FROM [ScenarioAnalysis] JOIN [LossEvent] ON PARENT([ScenarioAnalysis])
     This is the ORM3-only pairing - losses sit under the scenario here, not under the entity.
   Results of each scenario     - SELECT [ScenarioAnalysis].[Name], [ScenarioResult].[Name],
     [ScenarioResult].[OPSS-ScenRes:Severity]
     FROM [ScenarioAnalysis] JOIN [ScenarioResult] ON PARENT([ScenarioAnalysis])
 
Filters: business entity on [Location], complaint status, investigation outcome, scenario type.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-project-delivery-and-project-risk',
        title='Project Delivery and Project Risk',
        namespace='Operational_Risk_and_Control / PM',
        model_key='operational_risk_and_control/pm',
        why='Delivery and the risk carried by it in one place: projects under each entity, the risks and controls on those projects, and the milestone / deliverable / task breakdown.',
        charts=32,
        prompt=r"""Build a "Project Delivery and Project Risk" dashboard on this IBM OpenPages connection,
using the PM namespace.
 
Project, Milestone, Deliverable, Task and Sub-Task are solution objects. [Sub-Task] has a hyphen in
its type name - keep it inside the brackets exactly as written. Read each object type's own field
list first and use the status, type, priority, percent-complete and date fields it actually has;
do not guess an OPSS field group name. Where a chart below names a field by meaning, substitute the
real field name you find.
 
1. KPI CARDS - 9 "kpi" widgets
   Projects       COUNT [Project]
   Milestones     COUNT [Milestone]
   Deliverables   COUNT [Deliverable]
   Tasks          COUNT [Task]
   Sub-Tasks      COUNT [Sub-Task]
   Project Risks  COUNT [SOXRisk]
   Project Controls COUNT [SOXControl]
   Major Residual Risks COUNT [SOXRisk] WHERE [SOXRisk].[OPSS-Risk:Residual Risk Rating] = 'Major'
   Overdue Tasks  COUNT [Task] WHERE its overdue or past-due field says so, if such a field exists
   Ink the last two red and mark them good when they fall.
 
2. PROJECTS
   Projects by Status    - donut - the project status field
   Projects by Type      - donut - the project type field
   Projects by Priority  - bar   - the priority field
   Projects by Phase / Stage - bar - the phase field, if present
   Project Summary - table - SELECT [Name], [Description], the status field, the priority field,
     the start date field, the end date field, [Location] FROM [Project]
 
3. MILESTONES AND DELIVERABLES
   Milestones by Status  - donut - the milestone status field
   Milestones by Due Period - bar - the milestone due date field, rolled up to month as mm/yyyy
   Deliverables by Status - donut - the deliverable status field
   Deliverables by Type  - bar   - the deliverable type field
   Milestone Summary - table - SELECT [Name], [Description], the status field, the due date field,
     [Creation Date], [Location] FROM [Milestone]
   OpenPages SQL has no date functions, so the month chart groups by the raw date and the rows are
   rolled up to mm/yyyy after the query runs - do not try to write a month expression in SQL.
 
4. TASKS
   Tasks by Status           - donut - the task status field
   Tasks by Priority         - donut - the priority field
   Tasks by Percent Complete - bar   - the percent complete field, in value order
   Tasks by Assignee / Owner - bar   - the owner field, if present
   Sub-Tasks by Status       - donut - the sub-task status field
   Task Summary - table - SELECT [Name], [Description], the status field, the priority field,
     the percent complete field, the due date field FROM [Task]
 
5. PROJECT RISK AND CONTROL
   Risks by Residual Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risks by Inherent Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Risks by Status               - donut - [SOXRisk].[OPSS-Risk:Status]
   Controls by Operating Effectiveness - bar - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Controls by Control Type      - donut - [SOXControl].[OPSS-Ctl:Control Type]
   Colour: Minor green, Moderate yellow, Significant orange, Major red; Effective green,
   Partially Effective orange, Ineffective red.
   Risk Summary - table - SELECT [Name], [OPSS-Risk:Risk Domain], [OPSS-Risk:Inherent Risk Rating],
     [OPSS-Risk:Residual Risk Rating], [OPSS-Risk:Status], [Location] FROM [SOXRisk]
   Control Summary - table - SELECT [Name], [OPSS-Ctl:Control Type], [OPSS-Ctl:Design Effectiveness],
     [OPSS-Ctl:Operating Effectiveness], [OPSS-Ctl:Status], [Location] FROM [SOXControl]
 
6. RELATIONSHIP TABLES
   Projects under each entity - SELECT [SOXBusEntity].[Name], [Project].[Name],
     [Project].[Description] and the project status field
     FROM [SOXBusEntity] JOIN [Project] ON PARENT([SOXBusEntity])
   Risks on each project      - SELECT [Project].[Name], [SOXRisk].[Name],
     [SOXRisk].[OPSS-Risk:Residual Risk Rating], [SOXRisk].[OPSS-Risk:Status]
     FROM [Project] JOIN [SOXRisk] ON PARENT([Project])
   Controls on each risk      - SELECT [SOXRisk].[Name], [SOXControl].[Name],
     [SOXControl].[OPSS-Ctl:Operating Effectiveness]
     FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
   Milestones on each project - SELECT [Project].[Name], [Milestone].[Name] and the milestone
     status and due date fields FROM [Project] JOIN [Milestone] ON PARENT([Project])
   Tasks under each deliverable - SELECT [Deliverable].[Name], [Task].[Name] and the task status
     and percent complete fields FROM [Deliverable] JOIN [Task] ON PARENT([Deliverable])
   Sub-tasks under each task  - SELECT [Task].[Name], [Sub-Task].[Name] and the sub-task status
     field FROM [Task] JOIN [Sub-Task] ON PARENT([Task])
 
Filters: business entity on [Location], project status, task status, residual risk rating.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-risk-assessment-assurance-chain',
        title='Risk Assessment Assurance Chain',
        namespace='Operational_Risk_and_Control / RA1',
        model_key='operational_risk_and_control/ra1',
        why='One clean chain, assessment to test result. The report follows it link by link and shows where it breaks: assessments with no risks, risks with no controls, controls never tested, tests with exceptions.',
        charts=36,
        prompt=r"""Build a "Risk Assessment Assurance Chain" dashboard on this IBM OpenPages connection, using
the RA1 namespace: SOXBusEntity to RiskAssessment to SOXRisk to SOXControl to SOXTest to
SOXTestResult, with RiskEval under the risk and CtlEval under the control.
 
1. KPI CARDS - 10 "kpi" widgets
   Business Entities   COUNT [SOXBusEntity]
   Risk Assessments    COUNT [RiskAssessment]
   Risks               COUNT [SOXRisk]
   Controls            COUNT [SOXControl]
   Control Tests       COUNT [SOXTest]
   Test Results        COUNT [SOXTestResult]
   Risk Evaluations    COUNT [RiskEval]
   Control Evaluations COUNT [CtlEval]
   Ineffective Controls COUNT [SOXControl] WHERE [SOXControl].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'
   Test Results with Exceptions COUNT [SOXTestResult] WHERE [SOXTestResult].[OPSS-TestRes:Exceptions] = 'Yes'
   Ink the last two red and mark them good when they fall.
 
2. ASSESSMENTS
   Risk Assessments by Status - donut - [RiskAssessment].[OPSS-RiskAssess:Status]
   Risk Assessments by Type   - donut - [RiskAssessment].[OPSS-RiskAssess:Type]
   Assessment Summary - table - SELECT [Name], [Description], [OPSS-RiskAssess:Type],
     [OPSS-RiskAssess:Status], [Creation Date], [Location] FROM [RiskAssessment]
 
3. RISKS IN THOSE ASSESSMENTS
   Risks by Inherent Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Risks by Residual Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risks by Status               - donut - [SOXRisk].[OPSS-Risk:Status]
   Risks by Assessment Method    - donut - [SOXRisk].[OPSS-Risk:Assessment Method]
   Risk Summary - table - SELECT [Name], [OPSS-Risk:Assessment Method],
     [OPSS-Risk:Inherent Risk Rating], [OPSS-Risk:Residual Risk Rating], [OPSS-Risk:Status],
     [Location] FROM [SOXRisk]
 
4. CONTROLS
   Controls by Design Effectiveness    - bar   - [SOXControl].[OPSS-Ctl:Design Effectiveness]
   Controls by Operating Effectiveness - bar   - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Controls by Control Type            - donut - [SOXControl].[OPSS-Ctl:Control Type]
   Controls by Control Method          - donut - [SOXControl].[OPSS-Ctl:Control Method]
   Controls by Classification          - donut - [SOXControl].[OPSS-Ctl:Classification]
   Control Summary - table - SELECT [Name], [OPSS-Ctl:Control Type], [OPSS-Ctl:Control Method],
     [OPSS-Ctl:Classification], [OPSS-Ctl:Design Effectiveness],
     [OPSS-Ctl:Operating Effectiveness], [OPSS-Ctl:Status] FROM [SOXControl]
 
5. TESTING AND RESULTS
   Tests by Status            - donut - [SOXTest].[OPSS-Test:Status]
   Tests by Test Type         - donut - [SOXTest].[OPSS-Test:Test Type]
   Tests by Frequency         - bar   - [SOXTest].[OPSS-Test:Frequency]
   Test Results by Conclusion - bar   - [SOXTestResult].[OPSS-TestRes:Conclusion]
   Test Results by Result Type - donut - [SOXTestResult].[OPSS-TestRes:Result Type]
   Test Results by Exceptions - donut - [SOXTestResult].[OPSS-TestRes:Exceptions]
   Test Summary - table - SELECT [Name], [OPSS-Test:Test Type], [OPSS-Test:Frequency],
     [OPSS-Test:Status], [Creation Date], [Location] FROM [SOXTest]
   Test Result Summary - table - SELECT [Name], [OPSS-TestRes:Result Type],
     [OPSS-TestRes:Conclusion], [OPSS-TestRes:Exceptions], [OPSS-TestRes:Status],
     [Creation Date] FROM [SOXTestResult]
 
6. EVALUATIONS
   Risk Evaluations by Residual Risk Rating       - bar - [RiskEval].[OPSS-RiskEval:Residual Risk Rating]
   Risk Evaluations by Status                     - donut - [RiskEval].[OPSS-RiskEval:Status]
   Control Evaluations by Operating Effectiveness - bar - [CtlEval].[OPSS-CtlEval:Operating Effectiveness]
   Control Evaluations by Status                  - donut - [CtlEval].[OPSS-CtlEval:Status]
 
7. THE CHAIN, LINK BY LINK - one relationship table per pair, in order
   Assessments under each entity - SELECT [SOXBusEntity].[Name], [RiskAssessment].[Name],
     [RiskAssessment].[OPSS-RiskAssess:Type], [RiskAssessment].[OPSS-RiskAssess:Status]
     FROM [SOXBusEntity] JOIN [RiskAssessment] ON PARENT([SOXBusEntity])
   Risks in each assessment      - SELECT [RiskAssessment].[Name], [SOXRisk].[Name],
     [SOXRisk].[OPSS-Risk:Inherent Risk Rating], [SOXRisk].[OPSS-Risk:Residual Risk Rating]
     FROM [RiskAssessment] JOIN [SOXRisk] ON PARENT([RiskAssessment])
   Controls on each risk         - SELECT [SOXRisk].[Name], [SOXRisk].[OPSS-Risk:Residual Risk Rating],
     [SOXControl].[Name], [SOXControl].[OPSS-Ctl:Operating Effectiveness]
     FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
   Tests on each control         - SELECT [SOXControl].[Name],
     [SOXControl].[OPSS-Ctl:Operating Effectiveness], [SOXTest].[Name],
     [SOXTest].[OPSS-Test:Test Type], [SOXTest].[OPSS-Test:Status]
     FROM [SOXControl] JOIN [SOXTest] ON PARENT([SOXControl])
   Results of each test          - SELECT [SOXTest].[Name], [SOXTestResult].[Name],
     [SOXTestResult].[OPSS-TestRes:Conclusion], [SOXTestResult].[OPSS-TestRes:Exceptions]
     FROM [SOXTest] JOIN [SOXTestResult] ON PARENT([SOXTest])
   Evaluations of each control   - SELECT [SOXControl].[Name], [CtlEval].[Name],
     [CtlEval].[OPSS-CtlEval:Design Effectiveness], [CtlEval].[OPSS-CtlEval:Operating Effectiveness]
     FROM [SOXControl] JOIN [CtlEval] ON PARENT([SOXControl])
 
Filters: business entity on [Location], assessment status, residual risk rating, control operating
effectiveness, test result conclusion.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-rcsa-coverage-and-outcome',
        title='RCSA Coverage and Outcome',
        namespace='Operational_Risk_and_Control / RA2',
        model_key='operational_risk_and_control/ra2',
        why='RA2 runs the assessment over processes rather than straight to risks, so this is the RCSA report: how much of the process estate is assessed, what the assessment found, and whether the indicators and losses underneath agree with it.',
        charts=37,
        prompt=r"""Build an "RCSA Coverage and Outcome" dashboard on this IBM OpenPages connection, using the
RA2 namespace, where RiskAssessment is the parent of SOXProcess.
 
1. KPI CARDS - 11 "kpi" widgets
   Business Entities    COUNT [SOXBusEntity]
   Risk Assessments     COUNT [RiskAssessment]
   Processes Assessed   COUNT [SOXProcess]
   Sub-processes        COUNT [SOXSubprocess]
   Risks                COUNT [SOXRisk]
   Controls             COUNT [SOXControl]
   Key Risk Indicators  COUNT [KeyRiskIndicator]
   Loss Events          COUNT [LossEvent]
   Major Residual Risks COUNT [SOXRisk] WHERE [SOXRisk].[OPSS-Risk:Residual Risk Rating] = 'Major'
   Risks Outside Tolerance COUNT [SOXRisk] WHERE [SOXRisk].[OPSS-Risk:Within Risk Tolerance] = 'No'
   Red Breach KRIs      COUNT [KeyRiskIndicator] WHERE [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status] = 'Red'
   Ink the last three red and mark them good when they fall.
 
2. ASSESSMENT COVERAGE
   Risk Assessments by Status - donut - [RiskAssessment].[OPSS-RiskAssess:Status]
   Risk Assessments by Type   - donut - [RiskAssessment].[OPSS-RiskAssess:Type]
   Entities by RCSA Scope     - donut - [SOXBusEntity].[OPSS-Ent:RCSA Scope]
   Entities by Entity Type    - donut - [SOXBusEntity].[OPSS-Ent:Entity Type]
   Assessment Summary - table - SELECT [Name], [Description], [OPSS-RiskAssess:Type],
     [OPSS-RiskAssess:Status], [Creation Date], [Location] FROM [RiskAssessment]
 
3. PROCESS ESTATE
   Processes by Status           - donut - [SOXProcess].[OPSS-Proc:Status]
   Processes by In Scope         - donut - [SOXProcess].[OPSS-Proc:In Scope]
   Processes by Process Category - bar   - [SOXProcess].[OPSS-Proc:Process Category]
   Processes by Risk Domain      - bar   - [SOXProcess].[OPSS-Proc:Risk Domain]
   Sub-processes by Status       - donut - [SOXSubprocess].[OPSS-Subproc:Status]
   Process Summary - table - SELECT [Name], [OPSS-Proc:Risk Domain], [OPSS-Proc:Process Category],
     [OPSS-Proc:In Scope], [OPSS-Proc:Status], [Location] FROM [SOXProcess]
 
4. WHAT THE ASSESSMENT FOUND
   Risks by Inherent Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Risks by Residual Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risks Within Tolerance        - donut - [SOXRisk].[OPSS-Risk:Within Risk Tolerance]
   Risks by Risk Treatment       - donut - [SOXRisk].[OPSS-Risk:Risk Treatment]
   Controls by Operating Effectiveness - bar - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Controls by Design Effectiveness    - bar - [SOXControl].[OPSS-Ctl:Design Effectiveness]
   Risk Summary - table - SELECT [Name], [OPSS-Risk:Risk Domain], [OPSS-Risk:Inherent Risk Rating],
     [OPSS-Risk:Residual Risk Rating], [OPSS-Risk:Within Risk Tolerance], [OPSS-Risk:Status],
     [Location] FROM [SOXRisk]
   Control Summary - table - SELECT [Name], [OPSS-Ctl:Control Type], [OPSS-Ctl:Control Method],
     [OPSS-Ctl:Design Effectiveness], [OPSS-Ctl:Operating Effectiveness], [OPSS-Ctl:Status]
     FROM [SOXControl]
 
5. DOES THE EVIDENCE AGREE
   KRIs by Breach Status   - donut - [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status]
   KRIs by Indicator Trend - bar   - [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
   Loss Events by Severity - bar   - [LossEvent].[OPSS-LossEv:Severity]
   Loss Events by Outcome  - donut - [LossEvent].[OPSS-LossEv:Outcome]
   Loss Impacts by Impact Category - donut - [LossImpact].[OPSS-LossImp:Impact Category]
   KRI Summary - table - SELECT [Name], [OPSS-KRI:Status], [OPSS-KRI-Shared:Breach Status],
     [OPSS-KRI:Indicator Trend], [OPSS-KRI:Frequency], [OPSS-KRI:Value] FROM [KeyRiskIndicator]
   Loss Event Summary - table - SELECT [Name], [OPSS-LossEv:Status], [OPSS-LossEv:Outcome],
     [OPSS-LossEv:Severity], [OPSS-LossEv:Gross Loss], [OPSS-LossEv:Occurrence Date]
     FROM [LossEvent]
 
6. RELATIONSHIP TABLES
   Processes in each assessment - SELECT [RiskAssessment].[Name], [SOXProcess].[Name],
     [SOXProcess].[OPSS-Proc:Status], [SOXProcess].[OPSS-Proc:In Scope]
     FROM [RiskAssessment] JOIN [SOXProcess] ON PARENT([RiskAssessment])
     This is the RA2-only pairing - the assessment owns the process here.
   Risks on each process        - SELECT [SOXProcess].[Name], [SOXRisk].[Name],
     [SOXRisk].[OPSS-Risk:Residual Risk Rating], [SOXRisk].[OPSS-Risk:Within Risk Tolerance]
     FROM [SOXProcess] JOIN [SOXRisk] ON PARENT([SOXProcess])
   Risks on each sub-process    - SELECT [SOXSubprocess].[Name], [SOXRisk].[Name],
     [SOXRisk].[OPSS-Risk:Residual Risk Rating]
     FROM [SOXSubprocess] JOIN [SOXRisk] ON PARENT([SOXSubprocess])
   Controls on each risk        - SELECT [SOXRisk].[Name], [SOXControl].[Name],
     [SOXControl].[OPSS-Ctl:Operating Effectiveness]
     FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
   KRIs on each risk            - SELECT [SOXRisk].[Name], [KeyRiskIndicator].[Name],
     [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status], [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
     FROM [SOXRisk] JOIN [KeyRiskIndicator] ON PARENT([SOXRisk])
   Loss events on each risk     - SELECT [SOXRisk].[Name], [LossEvent].[Name],
     [LossEvent].[OPSS-LossEv:Severity], [LossEvent].[OPSS-LossEv:Outcome]
     FROM [SOXRisk] JOIN [LossEvent] ON PARENT([SOXRisk])
 
Filters: business entity on [Location], assessment status, process in scope, residual risk rating,
KRI breach status.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-sox-financial-control-certification',
        title='SOX Financial Control Certification',
        namespace='Operational_Risk_and_Control / SOX1',
        model_key='operational_risk_and_control/sox1',
        why='The financial reporting view: the account structure and its assertions on one side, the process-risk-control-test chain on the other, and the three evaluation objects that carry the certification conclusions.',
        charts=43,
        prompt=r"""Build a "SOX Financial Control Certification" dashboard on this IBM OpenPages connection,
using the SOX1 namespace.
 
1. KPI CARDS - 12 "kpi" widgets
   Business Entities    COUNT [SOXBusEntity]
   Processes            COUNT [SOXProcess]
   Sub-processes        COUNT [SOXSubprocess]
   Risks                COUNT [SOXRisk]
   Controls             COUNT [SOXControl]
   Control Tests        COUNT [SOXTest]
   Test Results         COUNT [SOXTestResult]
   Accounts             COUNT [SOXAccount]
   Sub-accounts         COUNT [SOXSubaccount]
   Assertions           COUNT [Assertion]
   Significant Accounts COUNT [SOXAccount] WHERE [SOXAccount].[OPSS-Acc:Significant] = 'Yes'
   Ineffective Controls COUNT [SOXControl] WHERE [SOXControl].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'
   Ink Ineffective Controls red and mark it good when it falls.
 
2. SCOPE AND CERTIFICATION
   Processes by SOX Status      - donut - [SOXProcess].[OPSS-Proc:SOX Status]
   Processes by In Scope        - donut - [SOXProcess].[OPSS-Proc:In Scope]
   Processes by Status          - donut - [SOXProcess].[OPSS-Proc:Status]
   Processes by Process Category - bar  - [SOXProcess].[OPSS-Proc:Process Category]
   Sub-processes by Status      - bar   - [SOXSubprocess].[OPSS-Subproc:Status]
   Process Summary - table - SELECT [Name], [OPSS-Proc:Process Category], [OPSS-Proc:In Scope],
     [OPSS-Proc:SOX Status], [OPSS-Proc:Status], [Location] FROM [SOXProcess]
 
3. ACCOUNT STRUCTURE
   Accounts by Account Type   - donut - [SOXAccount].[OPSS-Acc:Account Type]
   Accounts by Significance   - donut - [SOXAccount].[OPSS-Acc:Significant]
   Accounts by Status         - donut - [SOXAccount].[OPSS-Acc:Status]
   Sub-accounts by Status     - bar   - [SOXSubaccount].[OPSS-Subacc:Status]
   Assertions by Assertion Type - bar - [Assertion].[OPSS-Asrt:Assertion Type]
   Account Summary - table - SELECT [Name], [Description], [OPSS-Acc:Account Type],
     [OPSS-Acc:Significant], [OPSS-Acc:Status], [Location] FROM [SOXAccount]
   Assertion Summary - table - SELECT [Name], [Description], [OPSS-Asrt:Assertion Type],
     [Creation Date], [Location] FROM [Assertion]
 
4. RISK AND CONTROL
   Risks by Residual Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risks by Inherent Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Controls by Design Effectiveness    - bar   - [SOXControl].[OPSS-Ctl:Design Effectiveness]
   Controls by Operating Effectiveness - bar   - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Controls by Classification          - donut - [SOXControl].[OPSS-Ctl:Classification]
   Controls by COSO Component          - bar   - [SOXControl].[OPSS-Ctl-Fin:COSO Component]
   Controls by Control Frequency       - bar   - [SOXControl].[OPSS-Ctl:Control Frequency]
   Control Summary - table - SELECT [Name], [OPSS-Ctl:Control Type], [OPSS-Ctl:Control Method],
     [OPSS-Ctl:Classification], [OPSS-Ctl:Control Frequency], [OPSS-Ctl:Design Effectiveness],
     [OPSS-Ctl:Operating Effectiveness], [OPSS-Ctl:Status] FROM [SOXControl]
 
5. TESTING
   Tests by Status             - donut - [SOXTest].[OPSS-Test:Status]
   Tests by Test Type          - donut - [SOXTest].[OPSS-Test:Test Type]
   Test Results by Conclusion  - bar   - [SOXTestResult].[OPSS-TestRes:Conclusion]
   Test Results by Exceptions  - donut - [SOXTestResult].[OPSS-TestRes:Exceptions]
   Test Result Summary - table - SELECT [Name], [OPSS-TestRes:Result Type],
     [OPSS-TestRes:Conclusion], [OPSS-TestRes:Exceptions], [OPSS-TestRes:Status], [Creation Date]
     FROM [SOXTestResult]
 
6. EVALUATIONS
   Process Evaluations by Conclusion - bar - [ProcessEval].[OPSS-ProcEval:Conclusion]
   Process Evaluations by Status     - donut - [ProcessEval].[OPSS-ProcEval:Status]
   Control Evaluations by Operating Effectiveness - bar - [CtlEval].[OPSS-CtlEval:Operating Effectiveness]
   Control Evaluations by Design Effectiveness    - bar - [CtlEval].[OPSS-CtlEval:Design Effectiveness]
   Risk Evaluations by Residual Risk Rating       - bar - [RiskEval].[OPSS-RiskEval:Residual Risk Rating]
 
7. RELATIONSHIP TABLES
   Processes under each entity - SELECT [SOXBusEntity].[Name], [SOXProcess].[Name],
     [SOXProcess].[OPSS-Proc:SOX Status], [SOXProcess].[OPSS-Proc:In Scope]
     FROM [SOXBusEntity] JOIN [SOXProcess] ON PARENT([SOXBusEntity])
   Accounts under each process - SELECT [SOXProcess].[Name], [SOXAccount].[Name],
     [SOXAccount].[OPSS-Acc:Account Type], [SOXAccount].[OPSS-Acc:Significant]
     FROM [SOXProcess] JOIN [SOXAccount] ON PARENT([SOXProcess])
     This is the SOX1-only pairing - the process owns the account here.
   Sub-accounts of each account - SELECT [SOXAccount].[Name], [SOXSubaccount].[Name],
     [SOXSubaccount].[OPSS-Subacc:Status] FROM [SOXAccount] JOIN [SOXSubaccount] ON PARENT([SOXAccount])
   Assertions on each sub-account - SELECT [SOXSubaccount].[Name], [Assertion].[Name],
     [Assertion].[OPSS-Asrt:Assertion Type] FROM [SOXSubaccount] JOIN [Assertion] ON PARENT([SOXSubaccount])
   Risks on each process       - SELECT [SOXProcess].[Name], [SOXRisk].[Name],
     [SOXRisk].[OPSS-Risk:Residual Risk Rating] FROM [SOXProcess] JOIN [SOXRisk] ON PARENT([SOXProcess])
   Controls on each risk       - SELECT [SOXRisk].[Name], [SOXControl].[Name],
     [SOXControl].[OPSS-Ctl:Operating Effectiveness], [SOXControl].[OPSS-Ctl:Classification]
     FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
   Tests on each control       - SELECT [SOXControl].[Name], [SOXTest].[Name],
     [SOXTest].[OPSS-Test:Test Type], [SOXTest].[OPSS-Test:Status]
     FROM [SOXControl] JOIN [SOXTest] ON PARENT([SOXControl])
   Results of each test        - SELECT [SOXTest].[Name], [SOXTestResult].[Name],
     [SOXTestResult].[OPSS-TestRes:Conclusion], [SOXTestResult].[OPSS-TestRes:Exceptions]
     FROM [SOXTest] JOIN [SOXTestResult] ON PARENT([SOXTest])
 
Filters: business entity on [Location], process SOX status, account significance, control
operating effectiveness, test result conclusion.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-mandate-to-obligation-compliance-coverag',
        title='Mandate-to-Obligation Compliance Coverage',
        namespace='Platform_Reporting / DEFAULT (Folders)',
        model_key='platform_reporting/default',
        why='The regulatory spine: mandate down to obligation with an evaluation at each end, the questionnaire programme that collects the evidence, and the generic folder hierarchy (LevelOne / LevelTwo / LevelThree) the platform uses to file it all.',
        charts=38,
        prompt=r"""Build a "Mandate-to-Obligation Compliance Coverage" dashboard on this IBM OpenPages
connection, using the DEFAULT (Folders) namespace of the Platform Reporting model.
 
LevelOne, LevelTwo and LevelThree are the platform's generic folder objects. Read their own field
lists before writing their charts; if they carry nothing but [Name], [Description] and
[Creation Date], give them a count tile and a summary table only, and say so.
 
1. KPI CARDS - 12 "kpi" widgets
   Business Entities  COUNT [SOXBusEntity]
   Mandates           COUNT [Mandate]
   Submandates        COUNT [Submandate]
   Requirements       COUNT [Requirement]
   Requirement Evaluations COUNT [ReqEval]
   Obligations        COUNT [Obligation]
   Obligation Evaluations  COUNT [OblEval]
   Programs           COUNT [Program]
   Questionnaire Assessments COUNT [QuestionnaireAssessment]
   Question Templates COUNT [QuestionTemplate]
   Risks              COUNT [SOXRisk]
   Controls           COUNT [SOXControl]
 
2. MANDATES AND REQUIREMENTS
   Mandates by Mandate Type     - donut - [Mandate].[OPSS-Man:Mandate Type]
   Mandates by Status           - donut - [Mandate].[OPSS-Man:Status]
   Requirements by Requirement Type - bar - [Requirement].[OPSS-Req:Requirement Type]
   Requirements by Status       - donut - [Requirement].[OPSS-Req:Status]
   Requirement Evaluations by Conclusion - bar - [ReqEval].[OPSS-ReqEval:Conclusion]
   Mandate Summary - table - SELECT [Name], [Description], [OPSS-Man:Mandate Type],
     [OPSS-Man:Status], [Creation Date], [Location] FROM [Mandate]
   Requirement Summary - table - SELECT [Name], [Description], [OPSS-Req:Requirement Type],
     [OPSS-Req:Status], [Creation Date], [Location] FROM [Requirement]
 
3. OBLIGATIONS
   Obligations by Obligation Type - donut - [Obligation].[OPSS-Obl:Obligation Type]
   Obligations by Status          - donut - [Obligation].[OPSS-Obl:Status]
   Obligations by Functional Risk Area - bar - [Obligation].[OPSS-Obl-DT:Functional Risk Area]
   Obligation Evaluations by Conclusion - bar - [OblEval].[OPSS-OblEval:Conclusion]
   Obligation Summary - table - SELECT [Name], [Description], [OPSS-Obl:Obligation Type],
     [OPSS-Obl:Status], [OPSS-Obl-DT:Functional Risk Area], [Creation Date], [Location]
     FROM [Obligation]
 
4. EVIDENCE PROGRAMME
   Programs by Status                  - donut - [Program].[OPSS-Prog:Status]
   Questionnaire Assessments by Status - donut - [QuestionnaireAssessment].[OPSS-QA:Status]
   Questionnaire Assessments by Type   - donut - [QuestionnaireAssessment].[OPSS-QA:Assessment Type]
   Questionnaire Assessments by Result - bar   - [QuestionnaireAssessment].[OPSS-QA:Result]
   Assessment Summary - table - SELECT [Name], [Description], [OPSS-QA:Assessment Type],
     [OPSS-QA:Status], [OPSS-QA:Result], [Creation Date], [Location]
     FROM [QuestionnaireAssessment]
 
5. RISK, CONTROL AND TESTING UNDER THE ENTITY
   Risks by Residual Risk Rating - bar - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Controls by Operating Effectiveness - bar - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Tests by Status               - donut - [SOXTest].[OPSS-Test:Status]
   Test Results by Conclusion    - bar   - [SOXTestResult].[OPSS-TestRes:Conclusion]
   Loss Events by Outcome        - donut - [LossEvent].[OPSS-LossEv:Outcome]
   Risk Summary - table - SELECT [Name], [OPSS-Risk:Risk Domain], [OPSS-Risk:Inherent Risk Rating],
     [OPSS-Risk:Residual Risk Rating], [OPSS-Risk:Status], [Location] FROM [SOXRisk]
 
6. FOLDER HIERARCHY
   LevelOne Summary   - table - SELECT [Name], [Description], [Creation Date], [Location]
     plus any status or type field the object type has FROM [LevelOne]
   LevelTwo Summary   - table - same shape FROM [LevelTwo]
   LevelThree Summary - table - same shape FROM [LevelThree]
 
7. RELATIONSHIP TABLES - the regulatory spine, link by link
   Mandates under each entity   - SELECT [SOXBusEntity].[Name], [Mandate].[Name],
     [Mandate].[OPSS-Man:Mandate Type], [Mandate].[OPSS-Man:Status]
     FROM [SOXBusEntity] JOIN [Mandate] ON PARENT([SOXBusEntity])
   Submandates of each mandate  - SELECT [Mandate].[Name], [Submandate].[Name],
     [Submandate].[Description] FROM [Mandate] JOIN [Submandate] ON PARENT([Mandate])
   Requirements of each submandate - SELECT [Submandate].[Name], [Requirement].[Name],
     [Requirement].[OPSS-Req:Requirement Type], [Requirement].[OPSS-Req:Status]
     FROM [Submandate] JOIN [Requirement] ON PARENT([Submandate])
   Obligations of each requirement - SELECT [Requirement].[Name], [Obligation].[Name],
     [Obligation].[OPSS-Obl:Obligation Type], [Obligation].[OPSS-Obl:Status]
     FROM [Requirement] JOIN [Obligation] ON PARENT([Requirement])
   Evaluations of each obligation - SELECT [Obligation].[Name], [OblEval].[Name],
     [OblEval].[OPSS-OblEval:Conclusion] FROM [Obligation] JOIN [OblEval] ON PARENT([Obligation])
   Assessments in each programme - SELECT [Program].[Name], [QuestionnaireAssessment].[Name],
     [QuestionnaireAssessment].[OPSS-QA:Status], [QuestionnaireAssessment].[OPSS-QA:Result]
     FROM [Program] JOIN [QuestionnaireAssessment] ON PARENT([Program])
   Sections of each questionnaire template - SELECT [QuestionnaireTemplate].[Name],
     [SectionTemplate].[Name], [SectionTemplate].[Description]
     FROM [QuestionnaireTemplate] JOIN [SectionTemplate] ON PARENT([QuestionnaireTemplate])
   Questions in each sub-section - SELECT [SubSectionTemplate].[Name], [QuestionTemplate].[Name],
     [QuestionTemplate].[Description]
     FROM [SubSectionTemplate] JOIN [QuestionTemplate] ON PARENT([SubSectionTemplate])
 
Filters: business entity on [Location], mandate status, obligation status, questionnaire
assessment result.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-cross-namespace-executive-grc-summary',
        title='Cross-Namespace Executive GRC Summary',
        namespace='Every namespace - the shared backbone only',
        model_key='',
        why='One page that survives whichever namespace a connection is pointed at, because it only uses the objects and the parent/child pairs that every namespace shares. Use it as the landing page and link the nine specialised reports off it.',
        charts=41,
        prompt=r"""Build a "Cross-Namespace Executive GRC Summary" dashboard on this IBM OpenPages connection.
 
Use only the object types and relationships that every namespace in this reporting framework has in
common: the SOXBusEntity hierarchy, SOXProcess, SOXSubprocess, SOXRisk and SOXControl, plus
LossEvent, KeyRiskIndicator, SOXIssue and ActionItem read as standalone object types. Do not use
RiskAssessment, Project, Customer Complaint, Mandate, SOXAccount or any other object that only some
namespaces carry - this page must build unchanged against any of them.
 
1. KPI CARDS - 12 "kpi" widgets, each a COUNT of [Resource ID] on one object type
   Business Entities    COUNT [SOXBusEntity]
   Processes            COUNT [SOXProcess]
   Sub-processes        COUNT [SOXSubprocess]
   Risks                COUNT [SOXRisk]
   Controls             COUNT [SOXControl]
   Loss Events          COUNT [LossEvent]
   Key Risk Indicators  COUNT [KeyRiskIndicator]
   Issues               COUNT [SOXIssue]
   Action Items         COUNT [ActionItem]
   Major Residual Risks COUNT [SOXRisk] WHERE [SOXRisk].[OPSS-Risk:Residual Risk Rating] = 'Major'
   Ineffective Controls COUNT [SOXControl] WHERE [SOXControl].[OPSS-Ctl:Operating Effectiveness] = 'Ineffective'
   Overdue Action Items COUNT [ActionItem] WHERE [ActionItem].[OPSS-ActItem:Overdue] = 'Yes'
   Ink the last three red and mark them good when they fall.
 
2. WHERE THE EXPOSURE IS
   Risks by Residual Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risks by Inherent Risk Rating - bar   - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Risks Within Tolerance        - donut - [SOXRisk].[OPSS-Risk:Within Risk Tolerance]
   Risks by Domain               - bar   - [SOXRisk].[OPSS-Risk:Risk Domain]
   Risks by Status               - donut - [SOXRisk].[OPSS-Risk:Status]
   Colour: Minor green, Moderate yellow, Significant orange, Major red.
   Risk Summary - table - SELECT [Name], [OPSS-Risk:Risk Domain], [OPSS-Risk:Inherent Risk Rating],
     [OPSS-Risk:Residual Risk Rating], [OPSS-Risk:Within Risk Tolerance], [OPSS-Risk:Status],
     [Location] FROM [SOXRisk]
 
3. HOW WELL IT IS CONTROLLED
   Controls by Design Effectiveness    - bar   - [SOXControl].[OPSS-Ctl:Design Effectiveness]
   Controls by Operating Effectiveness - bar   - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Controls by Control Type            - donut - [SOXControl].[OPSS-Ctl:Control Type]
   Controls by Status                  - donut - [SOXControl].[OPSS-Ctl:Status]
   Colour: Effective green, Partially Effective orange, Ineffective red, Not Determined grey.
   Control Summary - table - SELECT [Name], [OPSS-Ctl:Control Type], [OPSS-Ctl:Control Method],
     [OPSS-Ctl:Design Effectiveness], [OPSS-Ctl:Operating Effectiveness], [OPSS-Ctl:Status],
     [Location] FROM [SOXControl]
 
4. WHAT IT COST AND WHAT IS WATCHED
   Loss Events by Outcome  - donut - [LossEvent].[OPSS-LossEv:Outcome]
   Loss Events by Severity - bar   - [LossEvent].[OPSS-LossEv:Severity]
   KRIs by Breach Status   - donut - [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status]
   KRIs by Indicator Trend - bar   - [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
   Loss Event Summary - table - SELECT [Name], [OPSS-LossEv:Status], [OPSS-LossEv:Outcome],
     [OPSS-LossEv:Severity], [OPSS-LossEv:Gross Loss], [OPSS-LossEv:Occurrence Date], [Location]
     FROM [LossEvent]
   KRI Summary - table - SELECT [Name], [OPSS-KRI:Status], [OPSS-KRI-Shared:Breach Status],
     [OPSS-KRI:Indicator Trend], [OPSS-KRI:Frequency], [OPSS-KRI:Value] FROM [KeyRiskIndicator]
 
5. WHAT IS BEING DONE ABOUT IT
   Issues by Status        - donut - [SOXIssue].[OPSS-Iss:Status]
   Issues by Priority      - donut - [SOXIssue].[OPSS-Iss:Priority]
   Action Items by Status  - donut - [ActionItem].[OPSS-ActItem:Status]
   Action Items by Ageing Bucket - bar - [ActionItem].[OPSS-ActItem:Aging Bucket], kept in the
     order 1-10 Days, 11-30 Days, 31-60 Days, Above 60 Days
   Overdue vs Not Yet Due  - donut - [ActionItem].[OPSS-ActItem:Overdue]
   Issue Summary - table - SELECT [Name], [OPSS-Iss:Status], [OPSS-Iss:Priority],
     [OPSS-Iss:Issue Type], [OPSS-Iss:Root Cause Type], [Creation Date], [Location]
     FROM [SOXIssue]
   Action Item Summary - table - SELECT [Name], [Description], [OPSS-ActItem:Status],
     [OPSS-ActItem:Percent Complete], [OPSS-ActItem:Start Date], [OPSS-ActItem:Due Date],
     [OPSS-ActItem:Overdue] FROM [ActionItem]
 
6. STRUCTURE
   Entities by Entity Type - donut - [SOXBusEntity].[OPSS-Ent:Entity Type]
   Entities by In Scope    - donut - [SOXBusEntity].[OPSS-Ent:In Scope]
   Processes by Status     - donut - [SOXProcess].[OPSS-Proc:Status]
   Processes by Domain     - bar   - [SOXProcess].[OPSS-Proc:Risk Domain]
   Entity Summary - table - SELECT [Name], [OPSS-Ent:Entity Type], [OPSS-Ent:In Scope],
     [OPSS-Ent:RCSA Scope], [OPSS-Ent:Framework], [OPSS-Ent:Status] FROM [SOXBusEntity]
 
7. RECORDS UNDER EACH ENTITY - no joins at all
   Use NO relationship table in this report. There is no parent/child pair that every namespace
   carries: [SOXRisk]|[SOXControl] is in eight of the nine, [SOXBusEntity]|[SOXBusEntity] in
   seven, and [SOXProcess]|[SOXSubprocess] in five. The only object type every namespace has is
   [SOXBusEntity]. A join written here is therefore a join that fails on some connection this
   report is meant to survive.
   [Location] is a system field on every object holding the business-entity path it sits under,
   so a plain SELECT already says which entity a record belongs to - which is what the tables
   below were for.
   Processes by entity - table - SELECT [Name], [OPSS-Proc:Status], [Location] FROM [SOXProcess]
   Risks by entity     - table - SELECT [Name], [OPSS-Risk:Residual Risk Rating], [Location]
     FROM [SOXRisk]
   Controls by entity  - table - SELECT [Name], [OPSS-Ctl:Operating Effectiveness], [Location]
     FROM [SOXControl]
   Losses by entity    - table - SELECT [Name], [Description], [Location] FROM [LossEvent]
   Drop any of these whose object type this connection does not share, and say which.
 
Filters: business entity on [Location], residual risk rating, control operating effectiveness,
KRI breach status, action item status.
 
RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair. Never invent a relationship the
  object model does not contain.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, skip NULLs, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end. Always show the figures as well
  as the colour.
- Every section ends with a full-width summary table: a plain SELECT of at least 5 fields FROM
  that one object type, [Name] first. No COUNT, no GROUP BY, no JOIN in a summary table.
- Add a "Business entity" filter on [Location].
- If a field below does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
)
