# Backend expansion prompts — detail reports

When a user types a short request, the backend sends the matching prompt below
to the model instead of the user's one line. Every prompt builds the same shape:
3–4 KPI cards, 12–15 charts three to a row, one detail summary table after each
group of six charts, and drill-down on everything.

The shared blocks (LAYOUT, DRILL-DOWN, HOUSE RULES) are repeated inside each
prompt so each one can be sent on its own.

---

## Shared blocks

### LAYOUT

```
LAYOUT
- Put 3 to 4 KPI cards across the top. Each card counts one kind of record only -
  never add two kinds together and never count a record twice.
- Below the cards, build 12 to 15 charts, laid out three per row.
- After every six charts, place one detail summary table across the full width,
  with at least eight columns, showing the records those six charts were built
  from.
- Give the report a subtitle that states the date window it covers and the date
  it was run.
- Put a business entity filter and a date-range filter at the top of the page,
  with the date range pre-set to the window named in this prompt.
```

### DRILL-DOWN

```
DRILL-DOWN
- Every KPI card, every chart slice and every bar is clickable.
- Clicking a KPI card filters the whole page to the records behind that number.
- Clicking a chart slice or bar filters the rest of the page to that value and
  scrolls to the detail table underneath, already filtered the same way.
- Clicking a row in a detail table opens the full record, with its parent record
  named and linked.
- A second click on the same slice or bar clears that filter.
- Show the filters currently applied as removable chips under the report title.
```

### HOUSE RULES

```
HOUSE RULES
- Count one kind of record at a time. Do not count and link to a related record
  in the same step.
- Only link records that are directly related as parent and child. If two records
  are related through a third one, go through it step by step.
- Break records down by fields that hold a fixed list of values - status, rating,
  type, severity, priority, yes or no. Do not sort by one of those fields; sort by
  the count instead.
- Read plain dates and roll them up to day, week, month or quarter when building
  the chart. Do not group dates while reading the data.
- Bring back amounts and total them when building the chart.
- Read the real field list of each record type first and use the fields that are
  actually there. If a field a chart needs is missing, drop that one chart, note
  which field was missing, and build the rest of the page.
- Never invent a value for a dropdown field. Read the values the field really has.
```

---

## 1. "Get me control test report for past 3 months"

```
Build a detail report called "Control Testing - Last 3 Months" from my IBM
OpenPages data.

Cover only control tests whose test date, completion date or scheduled date
falls in the last three months from today, together with the test results
underneath them and the controls they belong to.

Records to use: control tests, test results, controls, risks, processes and
business entities. A control belongs to a risk, a risk sits under a process, a
process sits under a business entity, a control holds its tests, and a test
holds its results.

KPI CARDS
- Tests carried out in the window.
- Test results recorded in the window.
- Results that failed or raised an exception.
- Controls covered by at least one test in the window.

CHARTS - first six
1. Tests by status.
2. Test results by outcome, passed against failed.
3. Tests by month of test date across the window.
4. Tests by test method.
5. Controls tested by control type.
6. Tests by business entity, most first.

DETAIL TABLE - control tests
Columns: test name, the control tested, the risk that control mitigates,
business entity, test method, scheduled date, completed date, tester, status.

CHARTS - next six
7. Failed results by deficiency severity.
8. Tests by week of completion, to show the testing run-rate.
9. Tested controls split automated against manual.
10. Failed results by process, most first.
11. Tests by control frequency.
12. Exceptions by remediation status.

DETAIL TABLE - test results and exceptions
Columns: result name, the test, the control, result date, outcome, deficiency
severity, exception note, remediation owner, remediation status.

CHARTS - closing row
13. Controls tested against controls not tested in the window.
14. Tests completed on time against tests completed late.
15. Pass rate by business entity.

LAYOUT
- Put 3 to 4 KPI cards across the top. Each card counts one kind of record only -
  never add two kinds together and never count a record twice.
- Below the cards, build 12 to 15 charts, laid out three per row.
- After every six charts, place one detail summary table across the full width,
  with at least eight columns, showing the records those six charts were built
  from.
- Give the report a subtitle that states the date window it covers and the date
  it was run.
- Put a business entity filter and a date-range filter at the top of the page,
  with the date range pre-set to the window named in this prompt.

DRILL-DOWN
- Every KPI card, every chart slice and every bar is clickable.
- Clicking a KPI card filters the whole page to the records behind that number.
- Clicking a chart slice or bar filters the rest of the page to that value and
  scrolls to the detail table underneath, already filtered the same way.
- Clicking a row in a detail table opens the full record, with its parent record
  named and linked.
- A second click on the same slice or bar clears that filter.
- Show the filters currently applied as removable chips under the report title.
- From a failed result, the drill path runs result to test to control to risk to
  process to business entity, and every step is clickable.

HOUSE RULES
- Count one kind of record at a time. Do not count and link to a related record
  in the same step.
- Only link records that are directly related as parent and child. If two records
  are related through a third one, go through it step by step.
- Break records down by fields that hold a fixed list of values - status, rating,
  type, severity, priority, yes or no. Do not sort by one of those fields; sort by
  the count instead.
- Read plain dates and roll them up to day, week, month or quarter when building
  the chart. Do not group dates while reading the data.
- Bring back amounts and total them when building the chart.
- Read the real field list of each record type first and use the fields that are
  actually there. If a field a chart needs is missing, drop that one chart, note
  which field was missing, and build the rest of the page.
- Never invent a value for a dropdown field. Read the values the field really has.
```

---

## 2. "Get me risk report for past 2 months"

```
Build a detail report called "Risk Register - Last 2 Months" from my IBM
OpenPages data.

Cover only risks created, last assessed or last updated in the last two months
from today, together with the controls under them and the evaluations behind
their ratings.

Records to use: risks, controls, risk evaluations, processes, sub-processes and
business entities. A risk sits under a process or a sub-process, a process sits
under a business entity, a risk holds its controls, and a risk holds its
evaluations.

KPI CARDS
- Risks added or updated in the window.
- Risks rated high or critical on residual rating.
- Risks sitting outside tolerance.
- Controls attached to those risks.

CHARTS - first six
1. Risks by residual risk rating.
2. Risks by inherent risk rating.
3. Risks by whether they sit within tolerance.
4. Risks by risk category or domain.
5. Risks by status.
6. Risks by business entity, most first.

DETAIL TABLE - risks
Columns: risk name, business entity, process, inherent rating, residual rating,
within tolerance, risk category, owner, last assessed date, status.

CHARTS - next six
7. Inherent rating against residual rating side by side, to show the effect of
   controls.
8. Risks added by week across the window.
9. Number of controls under each risk, most first.
10. Risks with no control beneath them against risks with at least one.
11. Controls by effectiveness rating.
12. Controls split automated against manual.

DETAIL TABLE - controls on those risks
Columns: control name, the risk it mitigates, business entity, control type,
automation, frequency, effectiveness, last tested date, owner, status.

CHARTS - closing row
13. Risk evaluations by rating given.
14. Risks by owner, most first.
15. Risks by review due month over the next six months.

LAYOUT
- Put 3 to 4 KPI cards across the top. Each card counts one kind of record only -
  never add two kinds together and never count a record twice.
- Below the cards, build 12 to 15 charts, laid out three per row.
- After every six charts, place one detail summary table across the full width,
  with at least eight columns, showing the records those six charts were built
  from.
- Give the report a subtitle that states the date window it covers and the date
  it was run.
- Put a business entity filter and a date-range filter at the top of the page,
  with the date range pre-set to the window named in this prompt.

DRILL-DOWN
- Every KPI card, every chart slice and every bar is clickable.
- Clicking a KPI card filters the whole page to the records behind that number.
- Clicking a chart slice or bar filters the rest of the page to that value and
  scrolls to the detail table underneath, already filtered the same way.
- Clicking a row in a detail table opens the full record, with its parent record
  named and linked.
- A second click on the same slice or bar clears that filter.
- Show the filters currently applied as removable chips under the report title.
- From a risk, the drill path runs risk to its controls to those controls' tests,
  and upwards risk to process to business entity.

HOUSE RULES
- Count one kind of record at a time. Do not count and link to a related record
  in the same step.
- Only link records that are directly related as parent and child. If two records
  are related through a third one, go through it step by step.
- Break records down by fields that hold a fixed list of values - status, rating,
  type, severity, priority, yes or no. Do not sort by one of those fields; sort by
  the count instead.
- Read plain dates and roll them up to day, week, month or quarter when building
  the chart. Do not group dates while reading the data.
- Bring back amounts and total them when building the chart.
- Read the real field list of each record type first and use the fields that are
  actually there. If a field a chart needs is missing, drop that one chart, note
  which field was missing, and build the rest of the page.
- Never invent a value for a dropdown field. Read the values the field really has.
```

---

## 3. "Show me KRI trend report for past 6 months"

```
Build a detail report called "Key Risk Indicator Trend - Last 6 Months" from my
IBM OpenPages data.

Cover indicator readings whose reading date falls in the last six months from
today, together with the indicators they belong to and the risks those
indicators monitor. This report is about movement over time, so most charts are
lines across the six months.

Records to use: key risk indicators, indicator readings, risks, business
entities and loss events. An indicator holds its readings, an indicator monitors
a risk or sits under a business entity, and a risk holds its loss events.

KPI CARDS
- Indicators with at least one reading in the window.
- Readings recorded in the window.
- Indicators currently in red breach.
- Readings that were in breach when taken.

CHARTS - first six
1. Line chart of the number of readings in breach, by month across the six
   months.
2. Line chart of average reading value by month, for the ten most-read
   indicators.
3. Indicators by current breach status, red against amber against green.
4. Indicators by measurement frequency.
5. Indicators by business entity, split by breach status.
6. Bar chart of readings by month, showing total readings against breached ones.

DETAIL TABLE - indicators
Columns: indicator name, the risk it monitors, business entity, threshold,
latest value, breach status, direction of travel over the window, frequency,
owner, last reading date.

CHARTS - next six
7. Line chart of breach count by week, for the last thirteen weeks.
8. Indicators that moved from green to red during the window.
9. Indicators that improved from red to green during the window.
10. Number of readings per indicator, most first.
11. Indicators overdue for a reading against those up to date.
12. Readings by who recorded them, most first.

DETAIL TABLE - readings
Columns: the indicator, reading date, value recorded, threshold at the time,
breach status, variance against threshold, business entity, recorded by,
comment.

CHARTS - closing row
13. Line chart comparing breached readings against loss events, by month.
14. Indicators by risk category.
15. Breach count by business entity, most first.

LAYOUT
- Put 3 to 4 KPI cards across the top. Each card counts one kind of record only -
  never add two kinds together and never count a record twice.
- Below the cards, build 12 to 15 charts, laid out three per row.
- After every six charts, place one detail summary table across the full width,
  with at least eight columns, showing the records those six charts were built
  from.
- Give the report a subtitle that states the date window it covers and the date
  it was run.
- Put a business entity filter and a date-range filter at the top of the page,
  with the date range pre-set to the window named in this prompt.

DRILL-DOWN
- Every KPI card, every chart slice and every bar is clickable.
- Clicking a KPI card filters the whole page to the records behind that number.
- Clicking a chart slice or bar filters the rest of the page to that value and
  scrolls to the detail table underneath, already filtered the same way.
- Clicking a row in a detail table opens the full record, with its parent record
  named and linked.
- A second click on the same slice or bar clears that filter.
- Show the filters currently applied as removable chips under the report title.
- Clicking a point on any trend line filters the page to that month and lists the
  readings taken in it.
- From a reading, the drill path runs reading to indicator to risk to business
  entity.

HOUSE RULES
- Count one kind of record at a time. Do not count and link to a related record
  in the same step.
- Only link records that are directly related as parent and child. If two records
  are related through a third one, go through it step by step.
- Break records down by fields that hold a fixed list of values - status, rating,
  type, severity, priority, yes or no. Do not sort by one of those fields; sort by
  the count instead.
- Read plain dates and roll them up to day, week, month or quarter when building
  the chart. Do not group dates while reading the data.
- Bring back amounts and total them when building the chart.
- Read the real field list of each record type first and use the fields that are
  actually there. If a field a chart needs is missing, drop that one chart, note
  which field was missing, and build the rest of the page.
- Never invent a value for a dropdown field. Read the values the field really has.
```

---

## 4. "Loss events report for past 3 months"

```
Build a detail report called "Loss Events - Last 3 Months" from my IBM OpenPages
data.

Cover only loss events whose date of occurrence or date discovered falls in the
last three months from today, together with their impacts and recoveries.

Records to use: loss events, loss impacts, loss recoveries, risks, processes and
business entities. A loss event sits under a business entity or under a risk, and
a loss event holds its impacts and its recoveries.

KPI CARDS
- Loss events in the window.
- Total gross loss amount in the window.
- Total amount recovered in the window.
- Loss events still open.

CHARTS - first six
1. Loss events by month of occurrence across the window.
2. Loss events by loss category.
3. Loss events by status.
4. Loss events by severity.
5. Total gross loss amount by business entity, biggest first.
6. Loss events by business line or process, most first.

DETAIL TABLE - loss events
Columns: event name, business entity, process, date of occurrence, date
discovered, loss category, gross amount, recovered amount, net amount, status.

CHARTS - next six
7. Gross loss against recovered amount by business entity.
8. Loss impacts by impact type, such as financial, reputational or regulatory.
9. Total impact amount by impact type.
10. Recoveries by recovery type, such as insurance or third party.
11. Loss events grouped by how long they took to discover: 1 to 10 days, 11 to 30
    days, 31 to 60 days, and above 60 days.
12. Loss events by the risk they were raised against, most first.

DETAIL TABLE - impacts and recoveries
Columns: record name, the loss event it belongs to, impact or recovery, type,
amount, currency, date recorded, business entity, status.

CHARTS - closing row
13. Running total of gross loss by week across the window.
14. Loss events above the reporting threshold against those below it.
15. Loss events by owner, most first.

LAYOUT
- Put 3 to 4 KPI cards across the top. Each card counts one kind of record only -
  never add two kinds together and never count a record twice.
- Below the cards, build 12 to 15 charts, laid out three per row.
- After every six charts, place one detail summary table across the full width,
  with at least eight columns, showing the records those six charts were built
  from.
- Give the report a subtitle that states the date window it covers and the date
  it was run.
- Put a business entity filter and a date-range filter at the top of the page,
  with the date range pre-set to the window named in this prompt.

DRILL-DOWN
- Every KPI card, every chart slice and every bar is clickable.
- Clicking a KPI card filters the whole page to the records behind that number.
- Clicking a chart slice or bar filters the rest of the page to that value and
  scrolls to the detail table underneath, already filtered the same way.
- Clicking a row in a detail table opens the full record, with its parent record
  named and linked.
- A second click on the same slice or bar clears that filter.
- Show the filters currently applied as removable chips under the report title.
- From a loss event, the drill path runs event to its impacts and recoveries, and
  upwards event to risk to process to business entity.

HOUSE RULES
- Count one kind of record at a time. Do not count and link to a related record
  in the same step.
- Only link records that are directly related as parent and child. If two records
  are related through a third one, go through it step by step.
- Break records down by fields that hold a fixed list of values - status, rating,
  type, severity, priority, yes or no. Do not sort by one of those fields; sort by
  the count instead.
- Read plain dates and roll them up to day, week, month or quarter when building
  the chart. Do not group dates while reading the data.
- Bring back amounts and total them when building the chart.
- Read the real field list of each record type first and use the fields that are
  actually there. If a field a chart needs is missing, drop that one chart, note
  which field was missing, and build the rest of the page.
- Never invent a value for a dropdown field. Read the values the field really has.
```
