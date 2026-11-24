"""
Turning a one-line request into the detail report it asks for.

"Get me control test report for past 3 months" is a complete request to a person and almost
nothing to a model: it names a subject and a window and leaves the shape, the charts, the tables
and the drill paths to be guessed. Guessed, it comes back as four charts and no table, which is
not what anyone meant by "report".

So the four subjects people actually ask for in those words - control testing, the risk register,
indicator trend, loss events - are written out in full here, once, and the matching one is sent in
place of the sentence. No AI model is used to decide which: the subject is read from the words, and
a request that matches nothing is passed through untouched, because a wrong expansion is far worse
than none.

The window is read from the request too ("past 3 months", "last 6 weeks", "this year") and resolved
to two real dates before the prompt is sent. A relative phrase left in the prompt drifts - the same
report run on the 1st and on the 31st covers different months and nobody can tell from looking at
it - and dates on the page are what make two runs comparable.

Each prompt is about twenty widgets: 3 to 4 KPI cards, 12 to 15 charts three to a row, and a detail
table after every six charts. MAX_WIDGETS (schemas.py) is 60, so they are not cut short.

Source: Openpages_model/Backend expansion prompts - detail reports.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# Where a request names no window of its own, each report falls back to the one it is usually
# asked for with. Months, because that is the unit these reports are asked about in.
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "quarter": 91, "year": 365}

_RELATIVE = re.compile(
    r"\b(?:past|last|previous|prior|latest|recent)\s+(\d{1,3})\s*(day|week|month|quarter|year)s?\b",
    re.I)
_RELATIVE_ONE = re.compile(
    r"\b(?:past|last|previous|prior|this)\s+(day|week|month|quarter|year)\b", re.I)
_YTD = re.compile(r"\b(?:year[ -]to[ -]date|ytd|so far this year)\b", re.I)


@dataclass(frozen=True)
class Window:
    """The stretch of time a report covers, already resolved to real dates."""

    start: date
    end: date
    label: str  # "the last 3 months", for the sentence inside the prompt
    title: str  # "Last 3 Months", for the report title

    @property
    def sentence(self) -> str:
        return (f"{self.start.strftime('%d %B %Y')} and {self.end.strftime('%d %B %Y')} "
                f"({self.label})")


def _window(text: str, default_months: int, today: date) -> Window:
    """The window the request asks for, or the report's usual one when it doesn't say."""
    if _YTD.search(text):
        start = date(today.year, 1, 1)
        return Window(start, today, "this year to date", "Year to Date")

    m = _RELATIVE.search(text)
    if m:
        count, unit = int(m.group(1)), m.group(2).lower()
    else:
        one = _RELATIVE_ONE.search(text)
        if one:
            count, unit = 1, one.group(1).lower()
        else:
            count, unit = default_months, "month"

    count = max(1, min(count, 60))  # a window nobody meant is not worth building
    days = _UNIT_DAYS[unit] * count
    start = date.fromordinal(max(1, today.toordinal() - days))
    plural = unit if count == 1 else unit + "s"
    return Window(start, today, f"the last {count} {plural}",
                  f"Last {count} {plural.capitalize()}")


# The three blocks every detail report carries. They are appended rather than written into each
# body so that a change to the house layout reaches all four, and so the bodies stay readable.
LAYOUT = """LAYOUT
- Put 3 to 4 KPI cards across the top. Each card counts one kind of record only - never add two
  kinds together and never count a record twice.
- Below the cards, build 12 to 15 charts, laid out three per row.
- After every six charts, place one detail summary table across the full width, with at least
  eight columns, showing the records those six charts were built from.
- Give the report a subtitle that states the date window it covers and the date it was run.
- Do not design any filters. The business entity, the window and the two fields this report is
  read by are added to the page afterwards, from the fields each chart's record types really
  have."""

DRILL_DOWN = """DRILL-DOWN
- Every KPI card, every chart slice and every bar is clickable.
- Clicking a KPI card filters the whole page to the records behind that number.
- Clicking a chart slice or bar filters the rest of the page to that value and scrolls to the
  detail table underneath, already filtered the same way.
- Clicking a row in a detail table opens the full record, with its parent record named and linked.
- A second click on the same slice or bar clears that filter.
- Show the filters currently applied as removable chips under the report title."""

HOUSE_RULES = """HOUSE RULES
- Count one kind of record at a time. Do not count and link to a related record in the same step.
- Only link records that are directly related as parent and child. If two records are related
  through a third one, go through it step by step.
- Break records down by fields that hold a fixed list of values - status, rating, type, severity,
  priority, yes or no. Do not sort by one of those fields; sort by the count instead.
- Read plain dates and roll them up to months when building the chart. Do not group dates while
  reading the data. Every date on a chart is shown as mm/yy and every date in a table as
  dd/mm/yyyy, so a chart axis is never a list of timestamps.
- Bring back amounts and total them when building the chart.
- Read the real field list of each record type first and use the fields that are actually there.
  If a field a chart needs is missing, drop that one chart, note which field was missing, and
  build the rest of the page.
- Never invent a value for a dropdown field. Read the values the field really has.
- No date conditions. No WHERE on a date, no "in the last three months", no date in a KPI's
  count. The window is applied to every query after it is written, on the date field each record
  type actually has. A date written here is a second condition on top of that one, and when it
  names a field this installation spells differently it matches nothing - which is how a report
  of twenty tiles comes back reading nought."""


@dataclass(frozen=True)
class DetailReport:
    """One subject, written out as the report people mean when they ask for it in one line."""

    id: str
    title: str  # "Control Testing", the window is added when the prompt is built
    # Every one of these words, or one from each group, must be in the request for it to match.
    # Written as groups so "control test", "control testing" and "testing of controls" all land.
    must: tuple[tuple[str, ...], ...]
    # A word here rules the report out, so that "control test" never answers as "risk report".
    never: tuple[str, ...]
    default_months: int
    body: str  # carries {window} and {title}
    extra_drill: str = ""
    # The one line someone types to get this, and what it is for. Both are shown on the build
    # panel, where the sentence is the request itself: it goes into the box as it stands and is
    # expanded here when it is sent, so editing "3 months" to "6" is all it takes to move it.
    ask: str = ""
    why: str = ""
    # The filters the built report opens with, beyond the business entity and the window that
    # every one of them gets. Named in the words people read, not as field names: the column is
    # chosen per chart from the fields that chart's object types really have. See report_filters.
    filters: tuple[str, ...] = ()

    def matches(self, words: set[str], text: str) -> bool:
        if any(bad in text for bad in self.never):
            return False
        return all(any(w in words or w in text for w in group) for group in self.must)

    def build(self, window: Window) -> str:
        body = self.body.format(window=window.sentence, title=f"{self.title} - {window.title}")
        parts = [body.strip(), LAYOUT, DRILL_DOWN + (("\n" + self.extra_drill) if self.extra_drill else ""),
                 HOUSE_RULES]
        return "\n\n".join(parts)


CONTROL_TESTS = DetailReport(
    id="detail-control-tests",
    title="Control Testing",
    must=(("control", "controls"), ("test", "tests", "testing")),
    never=("loss event", "indicator"),
    default_months=3,
    ask='Get me control test report for past 3 months',
    why='Every test run in the window with its result, the control it covers and the risk that control mitigates - what passed, what failed, and what is being done about the failures.',
    filters=('Test status', 'Test result'),
    extra_drill="- From a failed result, the drill path runs result to test to control to risk to "
                "process to\n  business entity, and every step is clickable.",
    body="""Build a detail report called "{title}" from my IBM OpenPages data.

This report covers {window}. Do not write that window into any query - it is applied to every
one of them afterwards, on each record type's own date field. Ask for the control tests, the test
results underneath them and the controls they belong to, over all time.

Records to use: control tests, test results, controls, risks, processes and business entities.
A control belongs to a risk, a risk sits under a process, a process sits under a business entity,
a control holds its tests, and a test holds its results.

KPI CARDS
- Control tests carried out.
- Test results recorded.
- Results that failed or raised an exception.
- Controls covered by at least one test.

CHARTS - first six
1. Tests by status.
2. Test results by outcome, passed against failed.
3. Tests by month of test date across the window.
4. Tests by test method.
5. Controls tested by control type.
6. Tests by business entity, most first.

DETAIL TABLE - control tests
Columns: test name, the control tested, the risk that control mitigates, business entity, test
method, scheduled date, completed date, tester, status.

CHARTS - next six
7. Failed results by deficiency severity.
8. Tests by month of completion, to show the testing run-rate.
9. Tested controls split automated against manual.
10. Failed results by process, most first.
11. Tests by control frequency.
12. Exceptions by remediation status.

DETAIL TABLE - test results and exceptions
Columns: result name, the test, the control, result date, outcome, deficiency severity, exception
note, remediation owner, remediation status.

CHARTS - closing row
13. Tests by tester, most first.
14. Tests completed on time against tests completed late.
15. Pass rate by business entity.""",
)

RISKS = DetailReport(
    id="detail-risks",
    title="Risk Register",
    must=(("risk", "risks"),),
    never=("kri", "key risk indicator", "indicator", "loss event", "control test",
           "control testing", "test result"),
    default_months=2,
    ask='Get me risk report for past 2 months',
    why='The register as it stands: inherent against residual, what sits outside tolerance, how many controls each risk carries and which risks carry none.',
    filters=('Residual risk rating', 'Within tolerance'),
    extra_drill="- From a risk, the drill path runs risk to its controls to those controls' "
                "tests, and upwards\n  risk to process to business entity.",
    body="""Build a detail report called "{title}" from my IBM OpenPages data.

This report covers {window}. Do not write that window into any query - it is applied to every
one of them afterwards, on each record type's own date field. Ask for the risks over all time,
together with the
controls under them and the evaluations behind their ratings.

Records to use: risks, controls, risk evaluations, processes, sub-processes and business entities.
A risk sits under a process or a sub-process, a process sits under a business entity, a risk holds
its controls, and a risk holds its evaluations.

KPI CARDS
- Risks on the register.
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
Columns: risk name, business entity, process, inherent rating, residual rating, within tolerance,
risk category, owner, last assessed date, status.

CHARTS - next six
7. Inherent rating against residual rating side by side, to show the effect of controls.
8. Risks added by month across the window.
9. Number of controls under each risk, most first.
10. Risks with no control beneath them against risks with at least one.
11. Controls by effectiveness rating.
12. Controls split automated against manual.

DETAIL TABLE - controls on those risks
Columns: control name, the risk it mitigates, business entity, control type, automation,
frequency, effectiveness, last tested date, owner, status.

CHARTS - closing row
13. Risk evaluations by rating given.
14. Risks by owner, most first.
15. Risks by review due month over the next six months.""",
)

KRI_TREND = DetailReport(
    id="detail-kri-trend",
    title="Key Risk Indicator Trend",
    must=(("kri", "kris", "indicator", "indicators", "key risk indicator"),),
    never=("loss event",),
    default_months=6,
    ask='Show me KRI trend report for past 6 months',
    why='Where the indicators are heading, month by month: breaches over time, which went red, which came back, and how the breaches line up against actual losses.',
    filters=('Breach status', 'Measurement frequency'),
    extra_drill="- Clicking a point on any trend line filters the page to that month and lists "
                "the readings taken\n  in it.\n"
                "- From a reading, the drill path runs reading to indicator to risk to business "
                "entity.",
    body="""Build a detail report called "{title}" from my IBM OpenPages data.

This report covers {window}. Do not write that window into any query - it is applied to every
one of them afterwards, on each record type's own date field. Ask for the readings over all time,
together with the indicators
they belong to and the risks those indicators monitor. This report is about movement over time, so
most charts are lines across the window.

Records to use: key risk indicators, indicator readings, risks, business entities and loss events.
An indicator holds its readings, an indicator monitors a risk or sits under a business entity, and
a risk holds its loss events.

KPI CARDS
- Indicators with at least one reading.
- Indicator readings recorded.
- Indicators currently in red breach.
- Readings that were in breach when taken.

CHARTS - first six
1. Line chart of the number of readings in breach, by month across the window.
2. Line chart of average reading value by month, for the ten most-read indicators.
3. Indicators by current breach status, red against amber against green.
4. Indicators by measurement frequency.
5. Indicators by business entity, split by breach status.
6. Bar chart of readings by month, showing total readings against breached ones.

DETAIL TABLE - indicators
Columns: indicator name, the risk it monitors, business entity, threshold, latest value, breach
status, direction of travel over the window, frequency, owner, last reading date.

CHARTS - next six
7. Line chart of breach count by month across the window.
8. Indicators that moved from green to red during the window.
9. Indicators that improved from red to green during the window.
10. Number of readings per indicator, most first.
11. Indicators overdue for a reading against those up to date.
12. Readings by who recorded them, most first.

DETAIL TABLE - readings
Columns: the indicator, reading date, value recorded, threshold at the time, breach status,
variance against threshold, business entity, recorded by, comment.

CHARTS - closing row
13. Line chart comparing breached readings against loss events, by month.
14. Indicators by risk category.
15. Breach count by business entity, most first.""",
)

LOSS_EVENTS = DetailReport(
    id="detail-loss-events",
    title="Loss Events",
    must=(("loss", "losses"),),
    never=("indicator", "kri"),
    default_months=3,
    ask='Loss events report for past 3 months',
    why='What was lost and what came back: events by month, category and entity, with their impacts, their recoveries and how long each took to discover.',
    filters=('Loss category', 'Loss event status'),
    extra_drill="- From a loss event, the drill path runs event to its impacts and recoveries, "
                "and upwards event\n  to risk to process to business entity.",
    body="""Build a detail report called "{title}" from my IBM OpenPages data.

This report covers {window}. Do not write that window into any query - it is applied to every
one of them afterwards, on each record type's own date field. Ask for the loss events over all
time,
together with their impacts and recoveries.

Records to use: loss events, loss impacts, loss recoveries, risks, processes and business entities.
A loss event sits under a business entity or under a risk, and a loss event holds its impacts and
its recoveries.

KPI CARDS
- Loss events.
- Total gross loss amount.
- Total amount recovered.
- Loss events still open.

CHARTS - first six
1. Loss events by month of occurrence across the window.
2. Loss events by loss category.
3. Loss events by status.
4. Loss events by severity.
5. Total gross loss amount by business entity, biggest first.
6. Loss events by business line or process, most first.

DETAIL TABLE - loss events
Columns: event name, business entity, process, date of occurrence, date discovered, loss category,
gross amount, recovered amount, net amount, status.

CHARTS - next six
7. Gross loss against recovered amount by business entity.
8. Loss impacts by impact type, such as financial, reputational or regulatory.
9. Total impact amount by impact type.
10. Recoveries by recovery type, such as insurance or third party.
11. Loss events grouped by how long they took to discover: 1 to 10 days, 11 to 30 days, 31 to 60
    days, and above 60 days.
12. Loss events by the risk they were raised against, most first.

DETAIL TABLE - impacts and recoveries
Columns: record name, the loss event it belongs to, impact or recovery, type, amount, currency,
date recorded, business entity, status.

CHARTS - closing row
13. Total gross loss by month across the window.
14. Loss events above the reporting threshold against those below it.
15. Loss events by owner, most first.""",
)

# 3 to 4 KPI cards, 12 to 15 charts and 2 detail tables: what every one of these builds, give or
# take the charts a connection has no field for. Shown on the card so nobody mistakes one of these
# for a four-chart answer. MAX_WIDGETS is 60, so none of them is cut short.
WIDGET_COUNT = 21

# Order matters only for a request that somehow matches two: the more specific subject wins, so
# "control test" is tried before "risk" - a control test report names risks in passing.
REPORTS: tuple[DetailReport, ...] = (CONTROL_TESTS, KRI_TREND, LOSS_EVENTS, RISKS)

# Below this the sentence is not a request for a report, it is a word. "risks" on its own should
# go to the model, which can ask what about them.
_MIN_WORDS = 3
# A request this long has said what it wants in its own words, and replacing it with one of these
# would throw that away.
_MAX_CHARS = 400

_WORD = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class Expansion:
    """What a short request was read as, and the prompt that is sent in its place."""

    report: DetailReport
    window: Window
    prompt: str


def expand(request: str, today: date | None = None) -> Expansion | None:
    """The detail report this request is asking for, or None to send it through as written.

    Deliberately conservative: a request that says what it wants, or that names no subject this
    knows, is left exactly as the person typed it.
    """
    text = (request or "").strip().lower()
    if not text or len(text) > _MAX_CHARS:
        return None
    words = set(_WORD.findall(text))
    if len(words) < _MIN_WORDS:
        return None
    # The person has already described the page. Expanding over that would overwrite their request
    # with a different one.
    if any(w in words for w in ("tab", "tabs", "pie", "donut", "gauge", "heatmap", "matrix")):
        return None

    for report in REPORTS:
        if report.matches(words, text):
            window = _window(text, report.default_months, today or date.today())
            return Expansion(report, window, report.build(window))
    return None
