"""
Three reports that already ship as templates, offered on the build panel as well.

They are written from the templates' own widgets rather than from a description of them, because
the template is the thing that already builds: every object type and every field in it has run
against a real connection. A prompt derived from it asks for exactly what is known to work.

As well as, not instead of: a template is built as it stands, while a prompt is read first and can
be changed before it is sent - a tab dropped, a breakdown added, the whole thing narrowed to one
entity. The same report, one way to take it and one way to adapt it.

Generated from the templates. Regenerate if those change.
"""

from .openpages_prompts import CuratedPrompt

FROM_TEMPLATES: tuple[CuratedPrompt, ...] = (
    CuratedPrompt(
        id='curated-orm-overview',
        title='ORM overview',
        namespace='ORM',
        model_key='operational_risk_and_control/orm1',
        why='Everything operational risk holds on one page: the estate it hangs off, how the risks are rated, how well they are controlled, what has been lost and what is being watched.',
        charts=45,
        plain=r"""Build the "ORM overview" report from my IBM OpenPages data.

1. Overview
   Number tiles: total risks, total controls, total business processes, total business entities, total loss events, total kris, total issues, total action items, open issues, overdue action items, major residual risks, red breach kris.
   End this tab with a summary table of the records behind it.

2. Risk analysis
   How the risks are rated and how much of the exposure sits inside tolerance. Minor green, Moderate yellow, Significant orange, Major red.
   Charts: risks by status, risks within tolerance, risks by domain, risks by inherent risk rating, risks by residual risk rating.
   End this tab with a summary table of the records behind it.

3. Control analysis
   Coverage and effectiveness. Effective green, Partially Effective orange, Ineffective red, Not Determined grey.
   Charts: controls by status, controls by control type, controls by design effectiveness, controls by operating effectiveness.
   End this tab with a summary table of the records behind it.

4. Business process analysis
   What the risks and controls hang off, and how much of it is in scope.
   Charts: processes by status, processes by in scope, processes by domain.
   End this tab with a summary table of the records behind it.

5. Business entity analysis
   The hierarchy everything above sits under, and how much of it is assessed.
   Charts: business entities by entity type, business entities by in scope, business entities by in rcsa scope, business entities by framework.
   End this tab with a summary table of the records behind it.

6. Loss event analysis
   What actually happened. Low green, Moderate yellow, High orange, Major red.
   Charts: loss events by outcome, loss events by severity, loss events by basel risk category l1.
   End this tab with a summary table of the records behind it.

7. KRI analysis
   Breach status and trend on the indicators being watched. Green green, Yellow yellow, Red red.
   Charts: kris by status, kris by breach status, kris by frequency, kris by indicator trend.
   End this tab with a summary table of the records behind it.

8. Issue analysis
   What assessment and testing turned up. Low green, Medium yellow, High orange, Critical red.
   Charts: issues by status, issues by priority, issues by issue type, issues by domain, issues by root cause type.
   End this tab with a summary table of the records behind it.

9. Action item analysis
   What is being done about all of it. Completed green, In Progress blue, Overdue red, Pending orange. The ageing buckets run 1-10, 11-30, 31-60 and above 60 days.
   Charts: action items by status, overdue against not yet due action items, action items by ageing bucket, action items by percent complete.
   End this tab with a summary table of the records behind it.

Put each numbered section on its own tab, named as it is above. Every chart on a
tab shows only that tab's records. Every tab ends with its own summary table of the records behind
it. That table shows every field the charts above it break records down by, because clicking a
chart filters the table to the records behind the part clicked - and it can only do that for a
field the table actually shows.

How to build it: count each kind of record on its own - never two kinds together, and never count
and link in the same step. Break records down by fields that hold a fixed list of values: status,
rating, type, priority, breach status. Read the real field list first and use what is actually
there; field names differ between installations, so a missing field should cost one chart and be
reported, not fail the report. Add a filter for business entity.""",
        prompt=r"""Build the "ORM overview" dashboard on this IBM OpenPages connection.

1. OVERVIEW
   KPI cards - one COUNT of [Resource ID] per object type:
     Total risks                  COUNT [SOXRisk]
     Total controls               COUNT [SOXControl]
     Total business processes     COUNT [SOXProcess]
     Total business entities      COUNT [SOXBusEntity]
     Total loss events            COUNT [LossEvent]
     Total KRIs                   COUNT [KeyRiskIndicator]
     Total issues                 COUNT [SOXIssue]
     Total action items           COUNT [ActionItem]
     Open issues                  COUNT [SOXIssue] WHERE [SOXIssue].[OPSS-Iss:Status] = 'Open'
     Overdue action items         COUNT [ActionItem] WHERE [ActionItem].[OPSS-ActItem:Overdue] = 'Yes'
     Major residual risks         COUNT [SOXRisk] WHERE [SOXRisk].[OPSS-Risk:Residual Risk Rating] = 'Major'
     Red breach KRIs              COUNT [KeyRiskIndicator] WHERE [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status] = 'Red'
   Overview summary                   - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [ActionItem]

2. RISK ANALYSIS  - How the risks are rated and how much of the exposure sits inside tolerance. Minor green, Moderate yellow, Significant orange, Major red.
   Risks by status                    - donut  - [SOXRisk].[OPSS-Risk:Status]
   Risks within tolerance             - donut  - [SOXRisk].[OPSS-Risk:Within Risk Tolerance]
   Risks by domain                    - bar    - [SOXRisk].[OPSS-Risk:Risk Domain]
   Risks by inherent risk rating      - bar    - [SOXRisk].[OPSS-Risk:Inherent Risk Rating]
   Risks by residual risk rating      - bar    - [SOXRisk].[OPSS-Risk:Residual Risk Rating]
   Risk analysis summary              - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [SOXRisk]

3. CONTROL ANALYSIS  - Coverage and effectiveness. Effective green, Partially Effective orange, Ineffective red, Not Determined grey.
   Controls by status                 - donut  - [SOXControl].[OPSS-Ctl:Status]
   Controls by control type           - donut  - [SOXControl].[OPSS-Ctl:Control Type]
   Controls by design effectiveness   - bar    - [SOXControl].[OPSS-Ctl:Design Effectiveness]
   Controls by operating effectiveness - bar    - [SOXControl].[OPSS-Ctl:Operating Effectiveness]
   Control analysis summary           - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [SOXControl]

4. BUSINESS PROCESS ANALYSIS  - What the risks and controls hang off, and how much of it is in scope.
   Processes by status                - donut  - [SOXProcess].[OPSS-Proc:Status]
   Processes by in scope              - donut  - [SOXProcess].[OPSS-Proc:In Scope]
   Processes by domain                - bar    - [SOXProcess].[OPSS-Proc:Risk Domain]
   Business process analysis summary  - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [SOXProcess]

5. BUSINESS ENTITY ANALYSIS  - The hierarchy everything above sits under, and how much of it is assessed.
   Business entities by entity type   - donut  - [SOXBusEntity].[OPSS-Ent:Entity Type]
   Business entities by in scope      - donut  - [SOXBusEntity].[OPSS-Ent:In Scope]
   Business entities by in RCSA scope - donut  - [SOXBusEntity].[OPSS-Ent:RCSA Scope]
   Business entities by framework     - bar    - [SOXBusEntity].[OPSS-Ent:Framework]
   Business entity analysis summary   - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [SOXBusEntity]

6. LOSS EVENT ANALYSIS  - What actually happened. Low green, Moderate yellow, High orange, Major red.
   Loss events by outcome             - donut  - [LossEvent].[OPSS-LossEv:Outcome]
   Loss events by severity            - bar    - [LossEvent].[OPSS-LossEv:Severity]
   Loss events by Basel risk category L1 - bar    - [LossEvent].[OPSS-Shared-Basel:Risk Category L1]
   Loss event analysis summary        - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [LossEvent]

7. KRI ANALYSIS  - Breach status and trend on the indicators being watched. Green green, Yellow yellow, Red red.
   KRIs by status                     - donut  - [KeyRiskIndicator].[OPSS-KRI:Status]
   KRIs by breach status              - donut  - [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status]
   KRIs by frequency                  - donut  - [KeyRiskIndicator].[OPSS-KRI:Frequency]
   KRIs by indicator trend            - bar    - [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
   KRI analysis summary               - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [KeyRiskIndicator]

8. ISSUE ANALYSIS  - What assessment and testing turned up. Low green, Medium yellow, High orange, Critical red.
   Issues by status                   - donut  - [SOXIssue].[OPSS-Iss:Status]
   Issues by priority                 - donut  - [SOXIssue].[OPSS-Iss:Priority]
   Issues by issue type               - bar    - [SOXIssue].[OPSS-Iss:Issue Type]
   Issues by domain                   - bar    - [SOXIssue].[OPSS-Iss:Risk Domain]
   Issues by root cause type          - bar    - [SOXIssue].[OPSS-Iss:Root Cause Type]
   Issue analysis summary             - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [SOXIssue]

9. ACTION ITEM ANALYSIS  - What is being done about all of it. Completed green, In Progress blue, Overdue red, Pending orange. The ageing buckets run 1-10, 11-30, 31-60 and above 60 days.
   Action items by status             - donut  - [ActionItem].[OPSS-ActItem:Status]
   Overdue against not yet due action items - donut  - [ActionItem].[OPSS-ActItem:Overdue]
   Action items by ageing bucket      - bar    - [ActionItem].[OPSS-ActItem:Aging Bucket]
   Action items by percent complete   - bar    - [ActionItem].[OPSS-ActItem:Percent Complete]
   Risk summary                       - table  - SELECT [SOXRisk].[Name], [SOXRisk].[Location], [SOXRisk].[OPSS-Risk:Risk Domain], [SOXRisk].[OPSS-Risk:Inherent Risk Rating], [SOXRisk].[OPSS-Risk:Residual Risk Rating], [SOXRisk].[OPSS-Risk:Status] FROM [SOXRisk]

Put each numbered section on its own tab, named as it is above. Every chart on a tab
reads only that tab's records - a chart about one subject does not belong on another subject's
tab. Every tab ends with its own summary table of the records that tab is about, so a click on
any of its charts filters that table.

RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end.
- Every summary table is a plain SELECT of at least 5 fields FROM one object type, [Name] first,
  and it selects every field the charts on its own tab group by, plus [Location]. Clicking a
  chart filters the tables on that field, so a tab whose table leaves it out cannot be drilled
  into: the selection is made and nothing happens.
- Add a "Business entity" filter on [Location].
- If a field above does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-events-indicators-and-remediation',
        title='Events, indicators and remediation',
        namespace='ORM',
        model_key='operational_risk_and_control/orm1',
        why='What happened and what is being done about it: loss events with their impacts, the indicators watching for the next one, and the issues and action items raised off both.',
        charts=43,
        plain=r"""Build the "Events, indicators and remediation" report from my IBM OpenPages data.

1. Business entities
   Everything below hangs under these entities. Every loss event, indicator, issue and action below hangs under them.
   Number tiles: business entities, loss events, key risk indicators, kris in red breach, issues, open issues, action items, overdue action items.
   Charts: entities by type, entities by status.
   End this tab with a summary table of the records behind it.

2. Loss experience
   What actually happened. Low green, Moderate yellow, High orange, Major red.
   Charts: loss events by outcome, loss events by severity, loss events by basel category, outcome against severity.
   End this tab with a summary table of the records behind it.

3. Indicator performance
   Breach status, trend and collection. Green green, Yellow yellow, Red red.
   Charts: kris by status, kris by breach status, kris by domain, kris by frequency, kris by trend, kris by collection status, kris by nature, kri values against their thresholds.
   End this tab with a summary table of the records behind it.

4. Issue management
   What assessment and testing turned up. Low green, Medium yellow, High orange, Critical red.
   Charts: issues by status, issues by priority, issues by type, issues by domain, issues by impact, issues by probability, issues by root cause, issue status against priority.
   End this tab with a summary table of the records behind it.

5. Remediation
   What is being done about all of it. Completed green, In Progress blue, Overdue red, Pending orange.
   Charts: action items by status, action items by percent complete, action item ageing, action items by approval status, overdue against not yet due, action items falling due by month.
   End this tab with a summary table of the records behind it.

6. Across ORM
   How the object types line up against each other. OpenPages counts one object type per query, so these are joins down the hierarchy rather than one chart of everything; the number tiles at the top are the object-wise distribution.
   Charts: risks raised by month, issues raised by month, loss events raised by month.
   End this tab with a summary table of the records behind it.

Put each numbered section on its own tab, named as it is above. Every chart on a
tab shows only that tab's records. Every tab ends with its own summary table of the records behind
it. That table shows every field the charts above it break records down by, because clicking a
chart filters the table to the records behind the part clicked - and it can only do that for a
field the table actually shows.

How to build it: count each kind of record on its own - never two kinds together, and never count
and link in the same step. Break records down by fields that hold a fixed list of values: status,
rating, type, priority, breach status. Read the real field list first and use what is actually
there; field names differ between installations, so a missing field should cost one chart and be
reported, not fail the report. Add a filter for business entity.""",
        prompt=r"""Build the "Events, indicators and remediation" dashboard on this IBM OpenPages connection.

1. BUSINESS ENTITIES  - Everything below hangs under these entities. Every loss event, indicator, issue and action below hangs under them.
   KPI cards - one COUNT of [Resource ID] per object type:
     Business entities            COUNT [SOXBusEntity]
     Loss events                  COUNT [LossEvent]
     Key risk indicators          COUNT [KeyRiskIndicator]
     KRIs in red breach           COUNT [KeyRiskIndicator] WHERE [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status] = 'Red'
     Issues                       COUNT [SOXIssue]
     Open issues                  COUNT [SOXIssue] WHERE [SOXIssue].[OPSS-Iss:Status] = 'Open'
     Action items                 COUNT [ActionItem]
     Overdue action items         COUNT [ActionItem] WHERE [ActionItem].[OPSS-ActItem:Overdue] = 'Yes'
   Entities by type                   - donut  - [SOXBusEntity].[OPSS-Ent:Entity Type]
   Entities by status                 - donut  - [SOXBusEntity].[OPSS-Ent:Status]
   Business entities summary          - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [SOXBusEntity]

2. LOSS EXPERIENCE  - What actually happened. Low green, Moderate yellow, High orange, Major red.
   Loss events by outcome             - donut  - [LossEvent].[OPSS-LossEv:Outcome]
   Loss events by severity            - bar    - [LossEvent].[OPSS-LossEv:Severity]
   Loss events by Basel category      - bar    - [LossEvent].[OPSS-Shared-Basel:Risk Category L1]
   Outcome against severity           - heatmap - [LossEvent].[OPSS-LossEv:Outcome]
   Loss experience summary            - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [LossEvent]

3. INDICATOR PERFORMANCE  - Breach status, trend and collection. Green green, Yellow yellow, Red red.
   KRIs by status                     - donut  - [KeyRiskIndicator].[OPSS-KRI:Status]
   KRIs by breach status              - donut  - [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status]
   KRIs by domain                     - bar    - [KeyRiskIndicator].[OPSS-KRI:Risk Domain]
   KRIs by frequency                  - bar    - [KeyRiskIndicator].[OPSS-KRI:Frequency]
   KRIs by trend                      - donut  - [KeyRiskIndicator].[OPSS-KRI:Indicator Trend]
   KRIs by collection status          - donut  - [KeyRiskIndicator].[OPSS-KRI:Collection Status]
   KRIs by nature                     - donut  - [KeyRiskIndicator].[OPSS-KRI:Indicator Nature]
   KRI values against their thresholds - bar    - [KeyRiskIndicator].[Name]
   Indicator performance summary      - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [KeyRiskIndicator]

4. ISSUE MANAGEMENT  - What assessment and testing turned up. Low green, Medium yellow, High orange, Critical red.
   Issues by status                   - donut  - [SOXIssue].[OPSS-Iss:Status]
   Issues by priority                 - donut  - [SOXIssue].[OPSS-Iss:Priority]
   Issues by type                     - bar    - [SOXIssue].[OPSS-Iss:Issue Type]
   Issues by domain                   - bar    - [SOXIssue].[OPSS-Iss:Risk Domain]
   Issues by impact                   - bar    - [SOXIssue].[OPSS-Iss:Impact]
   Issues by probability              - bar    - [SOXIssue].[OPSS-Iss:Probability]
   Issues by root cause               - bar    - [SOXIssue].[OPSS-Iss:Root Cause Type]
   Issue status against priority      - heatmap - [SOXIssue].[OPSS-Iss:Status]
   Issue management summary           - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [SOXIssue]

5. REMEDIATION  - What is being done about all of it. Completed green, In Progress blue, Overdue red, Pending orange.
   Action items by status             - donut  - [ActionItem].[OPSS-ActItem:Status]
   Action items by percent complete   - bar    - [ActionItem].[OPSS-ActItem:Percent Complete]
   Action item ageing                 - bar    - [ActionItem].[OPSS-ActItem:Aging Bucket]
   Action items by approval status    - donut  - [ActionItem].[OPSS-ActItem:Approval Status]
   Overdue against not yet due        - donut  - [ActionItem].[OPSS-ActItem:Overdue]
   Action items falling due by month  - line   - [ActionItem].[OPSS-ActItem:Due Date]
   Remediation summary                - table  - SELECT [Name], [Description], [Location] and at least three more fields FROM [ActionItem]

6. ACROSS ORM  - How the object types line up against each other. OpenPages counts one object type per query, so these are joins down the hierarchy rather than one chart of everything; the number tiles at the top are the object-wise distribution.
   Risks raised by month              - line   - [SOXRisk].[Creation Date]
   Issues raised by month             - line   - [SOXIssue].[Creation Date]
   Loss events raised by month        - line   - [LossEvent].[Creation Date]
   Controls on each risk              - table  - SELECT [SOXRisk].[Name], [SOXRisk].[OPSS-Risk:Residual Risk Rating], [SOXControl].[Name], [SOXControl].[OPSS-Ctl:Operating Effectiveness] FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
   KRIs on each risk                  - table  - SELECT [SOXRisk].[Name], [SOXRisk].[OPSS-Risk:Residual Risk Rating], [KeyRiskIndicator].[Name], [KeyRiskIndicator].[OPSS-KRI-Shared:Breach Status] FROM [SOXRisk] JOIN [KeyRiskIndicator] ON PARENT([SOXRisk])
   Action items under each issue      - table  - SELECT [SOXIssue].[Name], [SOXIssue].[OPSS-Iss:Priority], [ActionItem].[Name], [ActionItem].[OPSS-ActItem:Status], [ActionItem].[OPSS-ActItem:Due Date] FROM [SOXIssue] JOIN [ActionItem] ON PARENT([SOXIssue])
   Risks by entity                    - table  - SELECT [SOXRisk].[Location], [SOXRisk].[Name], [SOXRisk].[OPSS-Risk:Residual Risk Rating], [SOXRisk].[OPSS-Risk:Status] FROM [SOXRisk]

Put each numbered section on its own tab, named as it is above. Every chart on a tab
reads only that tab's records - a chart about one subject does not belong on another subject's
tab. Every tab ends with its own summary table of the records that tab is about, so a click on
any of its charts filters that table.

RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end.
- Every summary table is a plain SELECT of at least 5 fields FROM one object type, [Name] first,
  and it selects every field the charts on its own tab group by, plus [Location]. Clicking a
  chart filters the tables on that field, so a tab whose table leaves it out cannot be drilled
  into: the selection is made and nothing happens.
- Add a "Business entity" filter on [Location].
- If a field above does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
    CuratedPrompt(
        id='curated-audit-plan-item-overview',
        title='Audit plan item overview',
        namespace='OpenPages',
        model_key='assurance_and_testing/aud1',
        why='The audit plan broken down six ways - status, type, risk level, priority, planned quarter and auditable unit - with every plan item listed by the effort it is estimated to take.',
        charts=7,
        plain=r"""Build the "Audit plan item overview" report from my IBM OpenPages data.

1. Overview
   Charts: audit plan item - status, audit plan item - type, audit plan item - risk level, audit plan item - priority, audit plan item - planned quarter, audit plan item - auditable unit.
   End this tab with a summary table of the records behind it.

Put each numbered section on its own tab, named as it is above. Every chart on a
tab shows only that tab's records. Every tab ends with its own summary table of the records behind
it. That table shows every field the charts above it break records down by, because clicking a
chart filters the table to the records behind the part clicked - and it can only do that for a
field the table actually shows.

How to build it: count each kind of record on its own - never two kinds together, and never count
and link in the same step. Break records down by fields that hold a fixed list of values: status,
rating, type, priority, breach status. Read the real field list first and use what is actually
there; field names differ between installations, so a missing field should cost one chart and be
reported, not fail the report. Add a filter for business entity.""",
        prompt=r"""Build the "Audit plan item overview" dashboard on this IBM OpenPages connection.

1. OVERVIEW
   Audit plan item - status           - donut  - [Audit Plan Item].[IAM-PlanItem-FG:Status]
   Audit plan item - type             - donut  - [Audit Plan Item].[IAM-PlanItem-FG:Type]
   Audit plan item - risk level       - bar    - [Audit Plan Item].[IAM-PlanItem-FG:RskLvl]
   Audit plan item - priority         - bar    - [Audit Plan Item].[IAM-PlanItem-FG:Prty]
   Audit plan item - planned quarter  - donut  - [Audit Plan Item].[IAM-PlanItem-FG:PlnQtr]
   Audit plan item - auditable unit   - bar    - [Audit Plan Item].[IAM-PlanItem-FG:AudUnt]
   Audit plans by estimated effort, largest first - table  - SELECT [Audit Plan Item].[Name], [Audit Plan Item].[Description], [Audit Plan Item].[IAM-PlanItem-FG:Status], [Audit Plan Item].[IAM-PlanItem-FG:EstmtdEfrt], [Audit Plan Item].[IAM-PlanItem-FG:PlnQtr], [Audit Plan Item].[IAM-PlanItem-FG:Prty], [Audit Plan Item].[IAM-PlanItem-FG:PlndStrt], [Audit Plan Item].[IAM-PlanIte

Put each numbered section on its own tab, named as it is above. Every chart on a tab
reads only that tab's records - a chart about one subject does not belong on another subject's
tab. Every tab ends with its own summary table of the records that tab is about, so a click on
any of its charts filters that table.

RULES - IBM OpenPages Query Service SQL
- [brackets] around every object type and every field. No AS, no SUM, no CASE, no subqueries,
  no date functions, no LIMIT and no TOP.
- COUNT works on ONE object type and never alongside a JOIN. Every count therefore reads a single
  object type, so no record is counted twice and no two tiles share a query.
- Relationship tables use FROM [Parent] JOIN [Child] ON PARENT([Parent]) - direct parent/child
  only, exactly as this namespace's object model lists the pair.
- [Location] is a system field on every object holding the business-entity path it sits under, so
  a plain SELECT already tells you which entity a record belongs to - no join needed.
- Group only by the named field, order largest first unless a sequence is given.
- Donut = ring with the total in the middle and a legend listing each slice with its count and
  share. Bar = horizontal rows with the count written at the end.
- Every summary table is a plain SELECT of at least 5 fields FROM one object type, [Name] first,
  and it selects every field the charts on its own tab group by, plus [Location]. Clicking a
  chart filters the tables on that field, so a tab whose table leaves it out cannot be drilled
  into: the selection is made and nothing happens.
- Add a "Business entity" filter on [Location].
- If a field above does not exist on this connection, drop that one chart or column and say which,
  instead of failing the dashboard.""",
    ),
)
