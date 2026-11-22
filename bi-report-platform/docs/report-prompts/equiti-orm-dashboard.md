# Prompts: Equiti ORM dashboard

Prompts for **Ask a question > Build a report** that rebuild the Equiti "Consolidated Risk Dashboard"
(`equiti_orm_dashboard.html`) on an IBM OpenPages connection. Build a report makes at most 8 charts per
dashboard, so the dashboard is three prompts, one per section. Choose the OpenPages connection and an AI
model, paste a prompt, then **Build dashboard**.

The connection must share these object types (Connections > Choose tables): KeyRiskIndicator, SOXRisk,
SOXControl, SOXBusEntity, Incident, LossEvent.

**Quicker:** the same dashboard is a built-in template. On **Templates**, click **OpenPages: Equiti ORM dashboard**,
choose the connection and **Build dashboard**: all three sections in one dashboard, with headings and filters, and no
AI model needed. Use these prompts when you want the AI to adapt the charts, or to rebuild one section on its own.

## 1. KRI overview and status

```text
Equiti ORM – KRI overview and status. Use the KeyRiskIndicator object type only. Build exactly these 8 charts:
1. KPI "Total KRIs tracked": count of all KRIs.
2. KPI "KRIs in Red": count where [OPSS-KRI-Shared:Breach Status] = 'Red'.
3. KPI "KRIs in Amber": count where [OPSS-KRI-Shared:Breach Status] = 'Yellow'.
4. Pie "KRIs by indicator status": count by [OPSS-KRI-Shared:Breach Status].
5. Table "KRIs by Level 1 taxonomy and status": count by [OPSS-Shared-Basel:Risk Category] and [OPSS-KRI-Shared:Breach Status].
6. Bar "KRIs by Level 2 taxonomy": count by [OPSS-Shared-Basel:Risk Subcategory], largest first, leave out empty values.
7. Pie "KRI trend": count by [OPSS-KRI:Indicator Trend].
8. Table "KRI values against thresholds": Name, Breach Status, [OPSS-KRI:Value], [OPSS-KRI-Shared:Yellow Threshold], [OPSS-KRI-Shared:Red Threshold], Indicator Trend and [OPSS-KRI:Value Date], ordered by Breach Status.
```

## 2. Risk register and control assessment (RCSA)

```text
Equiti ORM – Risk register and control assessment (RCSA). Use SOXRisk for risks and SOXControl for controls. Build exactly these 8 charts:
1. KPI "Total risks": count of all SOXRisk.
2. KPI "Major risks": count of SOXRisk where [Eval-FG:Res Rating] = 'Major'.
3. KPI "Significant risks": count of SOXRisk where [Eval-FG:Res Rating] = 'Significant'.
4. Bar "Inherent risk rating": count of SOXRisk by [OPSS-Risk-Qual:Inherent Risk Rating].
5. Bar "Residual risk rating": count of SOXRisk by [OPSS-Risk-Qual:Residual Risk Rating].
6. Table "Residual risk heat map": count of SOXRisk by [OPSS-Risk-Qual:Residual Impact] and [OPSS-Risk-Qual:Residual Likelihood], leaving out empty values.
7. Bar "Risks by Level 2 taxonomy": count of SOXRisk by [OPSS-Shared-Basel:Risk Subcategory], largest first, leaving out empty values.
8. Pie "Controls by method": count of SOXControl by [OPSS-Ctl:Control Method], leaving out empty values.
```

## 3. Risk incidents overview

```text
Equiti ORM – Risk incidents overview. Use Incident and LossEvent. Build exactly these 8 charts:
1. KPI "Open incidents": count of Incident where [OPSS-Inc:Closed Date] IS NULL.
2. KPI "Major incidents": count of Incident where [OPSS-Inc:Criticality] IN ('Critical', 'High').
3. KPI "Loss events": count of all LossEvent.
4. Bar "Incidents by theme": count of Incident by [OPSS-Inc:Category], largest first.
5. Pie "Incidents by rating": count of Incident by [OPSS-Inc:Criticality].
6. Bar "Incidents by severity": count of Incident by [OPSS-Inc:Severity].
7. Table "Top major incidents": Incident Name, Description, Category, Criticality, [OPSS-Inc:Occurrence Date], [OPSS-Inc:Loss Amount], [OPSS-Inc:Exec_Status] and [OPSS-Inc:Closed Date], ordered by Loss Amount, largest first.
8. Table "Loss events and financial impact": LossEvent Name, [OPSS-Shared-Basel:Risk Category], [OPSS-LossEv:Gross Loss], [OPSS-LossEv:Net Loss], [OPSS-LossEv:Status] and [OPSS-LossEv:Occurrence Date], ordered by Net Loss, largest first.
```

## Extra charts (Add a chart by asking, in edit mode)

- `Table of risks under each business entity: SOXBusEntity Name, SOXRisk Name and Residual Risk Rating, using JOIN [SOXRisk] ON PARENT([SOXBusEntity]).` (the department and territory summary)
- `Table of open loss events with Gross Loss and Net Loss, largest Net Loss first.`

## What OpenPages can't do, and what to use instead

| Equiti chart | Why | Instead |
|---|---|---|
| Amber and Red breaches, monthly trend | OpenPages SQL has no date functions to group by month | Turn on **auto-refresh** (daily) on the KRI dashboard: number tiles then show the change and a trend line, and the **History** button draws each chart over time |
| Net financial impact (YTD) as one number | OpenPages SQL can only COUNT, not SUM | The "Loss events and financial impact" table lists each loss; **Download Excel** totals it |
| Inherent vs residual in one chart | Two different fields need two queries | Charts 4 and 5 of the RCSA prompt, side by side (set each to half width) |
| 5×5 heat map | The app has no heat-map chart | The heat-map table counts risks per impact and likelihood |
| Expected to close by month | No date functions | Add "Target Remediation Date" or "Closed Date" to the incident table and sort by it |
| Counts per entity or territory | COUNT can't be combined with JOIN | The "risks under each business entity" table (extra chart above) |

After building, add filters with **Add a custom filter** (for example Breach Status, Residual Risk Rating,
Criticality), and use card colours and headings to match the Equiti look.
