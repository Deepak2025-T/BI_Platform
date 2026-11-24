"""
What kind of report to build on this connection: recommendations, not a blank box.

A connection names its tables, so what it can answer is knowable before anyone types anything.
What someone has asked for before says which of those answers they actually want. Putting the two
together gives a short list of whole reports worth building - each a title, a reason it is being
suggested, and the request that builds it - rather than one more empty text box.

No AI model is used. Everything here comes from the connection's own object types or columns and
from the person's own past requests, so the list appears the moment a database is chosen and costs
nothing. Every suggestion is a sentence that goes into the box and can be edited before sending.

The ranking, in order of weight:
  1. what this person has asked about on this connection, most recent asks counting for most;
  2. what the connection actually shares, because a suggestion about vendors on a connection with
     no vendors is noise;
  3. what they have not built yet, so the list moves on instead of offering the report they
     already have five times over.
"""

import re
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .datasources import DataSource, table_columns
from .models import ChatConversation, ChatMessage, Report, User
from .openpages_detail_reports import REPORTS as DETAIL_REPORTS, WIDGET_COUNT
from .openpages_prompts import CURATED
from .openpages_template_prompts import FROM_TEMPLATES
from .prompt_ideas import _FREE_TEXT, _GROUP_WORDS, _MEASURE_WORDS, _NUMBER_TYPES, _label, _pick

# How many recommendations to offer. Six fits on one row of cards without a scroll, and a list
# longer than that is a menu to read rather than a suggestion to take.
MAX_IDEAS = 6
# How many of those may be a request the person made before rather than something new.
MAX_FROM_HISTORY = 2
# How far back to look. Older than this and "you asked about this recently" stops being true.
PAST_PROMPTS = 40
# A past request shorter than this is "hi" or "show me everything": nothing to learn from.
MIN_PAST_LENGTH = 12

_DATE_TYPES = ("date", "time", "year")


@dataclass
class Idea:
    """One recommended report: what it is, why it is being suggested, and what builds it."""

    id: str
    title: str
    # Why this one, in the person's own terms: "You asked about controls 3 times".
    why: str
    # Where the suggestion came from, so the panel can group them. "history" is something they
    # asked for before, "subject" is what the connection holds, "breadth" is the whole picture.
    reason: str
    # The request itself, ready to go in the box.
    prompt: str
    # Roughly how many charts it builds, so a one-chart idea doesn't look like a full report.
    charts: int = 0
    subject: str = ""
    # The headline numbers it would open with, so the card says what it measures.
    kpis: tuple[str, ...] = ()
    # For an OpenPages reference report, the namespace it is written against (openpages_model
    # keys it). Picking the card sets the data model with it, so the query writer is handed that
    # namespace's real parent/child pairs rather than left to guess which joins are legal -
    # which is the difference between a report that builds and one that drops half its charts.
    data_model: str = ""
    # What is actually sent when the request has not been edited. `prompt` is what the box shows -
    # ordinary words, nothing to fill in - while this is the same request written against the
    # Query Service. Keeping them apart means the box can be readable without the queries losing
    # the precision that makes them run. Empty when the two are the same.
    build_prompt: str = ""


# ---------------------------------------------------------------------------
# What an OpenPages connection can be asked for
#
# Each object type gets a recipe: what the report is called, the words that mean "this subject"
# in someone's request, and the charts worth having. The charts are named in the words people who
# use OpenPages use, never in field names like "OPSS-Ctl:Design Effectiveness" - the request goes
# to a model that reads the connection's real fields, and a field name guessed here that turns out
# not to exist would fail a chart for no reason.
# ---------------------------------------------------------------------------

@dataclass
class Recipe:
    """A report worth building about one subject."""

    subject: str
    title: str
    # Words that mean this subject when they turn up in somebody's request.
    words: tuple[str, ...]
    # The headline numbers, as KPI cards.
    kpis: tuple[str, ...]
    # The breakdowns, as charts.
    charts: tuple[str, ...]
    # Object types (OpenPages) or table names (SQL) this needs. The recipe is only offered when
    # the connection shares one of them.
    needs: tuple[str, ...] = ()
    extra: str = ""


_OP_RECIPES: tuple[Recipe, ...] = (
    Recipe(
        subject="risk", title="Risk overview", needs=("soxrisk",),
        words=("risk", "risks", "inherent", "residual", "tolerance", "appetite", "rcsa"),
        kpis=("the total number of risks", "how many are approved", "how many are major residual risks",
              "how many sit outside risk tolerance"),
        charts=("risks by status", "risks by inherent risk rating", "risks by residual risk rating",
                "risks by risk domain", "risks by treatment", "risks by whether they are within tolerance",
                "risks by owner", "inherent rating against residual rating"),
    ),
    Recipe(
        subject="control", title="Control effectiveness", needs=("soxcontrol",),
        words=("control", "controls", "effectiveness", "effective", "automated", "preventive", "detective",
               "testing", "test"),
        kpis=("the total number of controls", "how many are automated", "how many are manual",
              "how many are ineffective"),
        charts=("controls by status", "controls by control type", "controls by design effectiveness",
                "controls by operating effectiveness", "controls by method", "controls by frequency",
                "controls by business entity", "design effectiveness against operating effectiveness"),
    ),
    Recipe(
        subject="issue", title="Issues and remediation", needs=("soxissue",),
        words=("issue", "issues", "finding", "findings", "remediation", "root cause", "priority"),
        kpis=("the total number of issues", "how many are open", "how many are high priority",
              "how many are overdue"),
        charts=("issues by status", "issues by priority", "issues by issue type", "issues by risk domain",
                "issues by root cause", "issues by the group that identified them",
                "issues by status and priority together"),
    ),
    Recipe(
        subject="action item", title="Action item tracking", needs=("actionitem",),
        words=("action", "actions", "action item", "task", "tasks", "overdue", "due", "remediation plan"),
        kpis=("the total number of action items", "how many are open", "how many are overdue",
              "how many are complete"),
        charts=("action items by status", "overdue against not yet due", "action items by ageing bucket",
                "action items by percent complete", "action items by owner", "action items by due month"),
        extra=("OpenPages SQL has no date arithmetic, so take ageing and overdue from the stored ageing "
               "bucket and overdue fields rather than calculating them."),
    ),
    Recipe(
        subject="loss event", title="Loss events", needs=("lossevent",),
        words=("loss", "losses", "loss event", "incident", "incidents", "basel", "severity"),
        kpis=("the total number of loss events", "how many had a loss outcome",
              "how many are high severity", "the total loss amount"),
        charts=("loss events by outcome", "loss events by severity", "loss events by Basel risk category",
                "loss events by business entity", "loss amount by month over the last year",
                "outcome against severity"),
    ),
    Recipe(
        subject="indicator", title="Key risk indicators", needs=("keyriskindicator", "kriindicator"),
        words=("kri", "kris", "indicator", "indicators", "breach", "threshold", "trend"),
        kpis=("the total number of indicators", "how many are active", "how many are in red breach",
              "how many are in yellow breach"),
        charts=("indicators by status", "indicators by breach status", "indicators by indicator trend",
                "indicators by collection frequency", "indicators by risk domain",
                "breach status by risk domain"),
    ),
    Recipe(
        subject="process", title="Business processes", needs=("soxprocess",),
        words=("process", "processes", "sox", "in scope", "scoping"),
        kpis=("the total number of business processes", "how many are in scope",
              "how many are in SOX scope", "how many are awaiting assessment"),
        charts=("processes by status", "processes by what they are in scope for", "processes by risk domain",
                "processes by process owner", "processes by approval status"),
    ),
    Recipe(
        subject="entity", title="Business entities", needs=("soxbusentity",),
        words=("entity", "entities", "business entity", "organisation", "organization", "region", "country"),
        kpis=("the total number of business entities", "how many are in scope",
              "how many are in RCSA scope"),
        charts=("entities by entity type", "entities by whether they are in scope",
                "entities by RCSA scope", "entities by framework", "entity type against RCSA scope"),
    ),
    Recipe(
        subject="policy", title="Policies", needs=("policy",),
        words=("policy", "policies", "attestation", "review due"),
        kpis=("the total number of policies", "how many are approved", "how many are due for review"),
        charts=("policies by approval status", "policies by department", "policies by review month"),
    ),
    Recipe(
        subject="vendor", title="Third parties", needs=("vendor", "thirdparty"),
        words=("vendor", "vendors", "supplier", "third party", "third-party", "outsourc"),
        kpis=("the total number of vendors", "how many are high risk", "how many are due for review"),
        charts=("vendors by risk tier", "vendors by status", "vendors by country",
                "vendors by the business entity that owns them"),
    ),
    Recipe(
        subject="audit", title="Audit coverage", needs=("auditplan", "sauditaction", "audit"),
        words=("audit", "audits", "auditable", "engagement", "fieldwork"),
        kpis=("the total number of audits", "how many are in progress", "how many are complete"),
        charts=("audits by status", "audits by year", "audit actions by status",
                "overdue audit actions by owner", "audit coverage by business entity"),
    ),
)


# ---------------------------------------------------------------------------
# Reading what someone has asked for before
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z][a-z'-]+")
# Words that say nothing about the subject. Kept short on purpose: this is here to stop "report"
# and "show" from matching a recipe, not to be a linguist's stop list.
_NOISE = frozenset("""a an and are as at be build by chart charts create dashboard data display each
every for from get give graph have how in into is it its list make many me much of on one or page
please report reports show shows that the their them there these this those to total up us use
want was we what when where which who will with would you your""".split())


def past_prompts(db: Session, user: User, source: DataSource) -> list[str]:
    """What this person has asked of this connection before, most recent first.

    Both halves of the product count: a report they built is a strong signal, and a question they
    typed into chat is a weaker but much more frequent one. Someone else's requests are never
    read - a recommendation has to be about your own work to be worth anything.
    """
    out: list[str] = []
    reports = db.scalars(select(Report).where(Report.owner_id == user.id)
                         .order_by(Report.updated_at.desc()).limit(PAST_PROMPTS * 2)).all()
    for r in reports:
        if (r.config or {}).get("source_id") == source.id and len(r.prompt or "") >= MIN_PAST_LENGTH:
            out.append(r.prompt)

    chats = db.scalars(select(ChatConversation).where(ChatConversation.user_id == user.id)
                       .order_by(ChatConversation.updated_at.desc()).limit(PAST_PROMPTS)).all()
    ours = [c.id for c in chats if c.source_id == source.id]
    if ours:
        questions = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id.in_(ours))
                               .order_by(ChatMessage.id.desc()).limit(PAST_PROMPTS)).all()
        out.extend(m.question for m in questions if len(m.question or "") >= MIN_PAST_LENGTH)
    return out[:PAST_PROMPTS]


def _affinity(prompts: list[str], recipe: Recipe) -> tuple[float, int]:
    """How much this person's own history points at this subject: (score, how many times asked).

    Recent asks count for more than old ones, because what someone wanted last week is a better
    guess at what they want now than what they wanted in March. The count comes back separately
    because the reason shown on screen says "3 times", not "2.7".
    """
    score = 0.0
    hits = 0
    for at, prompt in enumerate(prompts):
        text = prompt.lower()
        if any(word in text for word in recipe.words):
            hits += 1
            score += 1 / (1 + at * 0.25)      # the most recent ask is worth four of the twelfth
    return score, hits


def _already_built(prompts_of_reports: list[str], recipe: Recipe) -> bool:
    """Whether a report on this subject already exists, so the list can move on to another."""
    return any(any(word in p.lower() for word in recipe.words) for p in prompts_of_reports)


# ---------------------------------------------------------------------------
# Turning a recipe into a request
# ---------------------------------------------------------------------------

def _request(recipe: Recipe, source: DataSource, types: list[str]) -> str:
    """The request that builds this report, written the way one would be typed."""
    where = f" on the {source.name} connection" if source.name else ""
    named = ", ".join(f"[{t}]" for t in types)
    # "Build a control effectiveness on ..." is not a sentence, and "a risk overview report" is a
    # word too many. Only the titles that are not already the name of a thing get "report".
    name = recipe.title.lower()
    if not re.search(r"(overview|report|dashboard|summary)$", name):
        name += " report"
    article = "an" if name[:1] in "aeiou" else "a"
    lines = [f"Build {article} {name}{where}."]
    if named:
        lines.append(f"Use {named}.")
    if recipe.kpis:
        lines.append("KPI cards for " + _and_list(recipe.kpis) + ".")
    if recipe.charts:
        lines.append("Then charts for " + _and_list(recipe.charts) + ".")
    lines.append("Count records, skip empty values, and put the largest first. "
                 "Colour the ratings in the usual way - green for good, red for bad - and show "
                 "the figures as well as the colours.")
    if recipe.extra:
        lines.append(recipe.extra)
    return " ".join(lines)


def _and_list(items) -> str:
    items = list(items)
    if len(items) < 2:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---------------------------------------------------------------------------
# SQL connections: a recipe worked out from one table's own columns
# ---------------------------------------------------------------------------

def _table_recipe(source: DataSource, table: str) -> Recipe | None:
    """What one table can carry a report about, or None when it has nothing worth charting."""
    columns = table_columns(source, table)
    if not columns:
        return None
    thing = _label(table.rpartition(".")[2])
    number = _pick(columns, _NUMBER_TYPES, _MEASURE_WORDS)
    group = _pick(columns, ("char", "text", "string", "enum"), _GROUP_WORDS, avoid=_FREE_TEXT)
    second = _pick([c for c in columns if c[0] != group],
                   ("char", "text", "string", "enum"), _GROUP_WORDS, avoid=_FREE_TEXT)
    date = _pick(columns, _DATE_TYPES, ("date", "created", "posted", "order", "invoice"))
    if not group and not number:
        return None

    kpis = [f"how many {thing} there are"]
    charts = []
    if number:
        kpis.append(f"the total {_label(number)}")
        kpis.append(f"the average {_label(number)}")
    if number and group:
        charts.append(f"total {_label(number)} by {_label(group)}")
        charts.append(f"the top 10 {_label(group)} by {_label(number)}")
    if group:
        charts.append(f"how many {thing} by {_label(group)}")
    if second and second != group:
        charts.append(f"{thing} by {_label(group)} and {_label(second)}")
    if date:
        charts.append(f"how many {thing} each month over the last year")
        if number:
            charts.append(f"monthly {_label(number)} over the last year")
    if not charts:
        return None
    # The table's own name and the columns it is charted by are what someone would say when they
    # mean this table, so they are what a past request is matched against.
    words = tuple({thing, *thing.split(), *(w for w in (group, number, second) if w)})
    return Recipe(subject=thing, title=f"{thing.capitalize()} overview", words=words,
                  kpis=tuple(kpis), charts=tuple(charts), needs=(table,))


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

def _recipes_for(source: DataSource) -> list[tuple[Recipe, list[str]]]:
    """The recipes this connection can actually carry, with the types or tables each one uses."""
    shared = [t.split(".", 1)[-1] for t in source.tables]
    lower = {t.lower(): t for t in shared}
    if source.is_openpages:
        out = []
        for recipe in _OP_RECIPES:
            used = [source.op_type(lower[n]) for n in recipe.needs if n in lower]
            if used:
                out.append((recipe, used))
        return out
    out = []
    for table in list(source.tables)[:8]:
        recipe = _table_recipe(source, table)
        if recipe:
            out.append((recipe, [table.rpartition(".")[2]]))
    return out


def _from_history(report_prompts: list[str]) -> list[Idea]:
    """The person's own past requests, offered back as something to run again.

    Only requests that built a report are offered, not chat questions: a chat question is one
    chart, and this list is about whole reports. Near-duplicates are dropped, because asking the
    same thing three weeks running should give one card, not three.
    """
    out: list[Idea] = []
    seen: set[str] = set()
    for prompt in report_prompts:
        key = " ".join(sorted(set(_WORD.findall(prompt.lower())) - _NOISE))[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(Idea(id=f"past-{len(out)}", title=_title_of(prompt), reason="history",
                        why="You built this before", prompt=prompt,
                        charts=_charts_in(prompt), subject="history"))
        if len(out) >= MAX_FROM_HISTORY:
            break
    return out


def _title_of(prompt: str) -> str:
    """A card-sized name for a request: its first clause, tidied up."""
    first = re.split(r"[.\n:;]", prompt.strip(), maxsplit=1)[0].strip()
    # The article alternatives are longest first and end on a word boundary, or "an orders
    # overview" loses its "a" and starts "n orders".
    first = re.sub(r"^(?:please\s+)?(?:build|create|make|generate|show|give)\s+(?:me\s+)?"
                   r"(?:(?:an|a|the)\b\s*)?", "", first, flags=re.I).strip()
    first = first[:1].upper() + first[1:] if first else prompt[:60]
    return first[:60].rstrip(" ,") + ("…" if len(first) > 60 else "")


def _charts_in(prompt: str) -> int:
    """A rough count of how many charts a request asks for, for the "about N charts" line."""
    numbers = [int(n) for n in re.findall(r"\b(\d{1,2})\s*(?:kpis?|charts?|cards?|tiles?)", prompt.lower())]
    return sum(numbers)


def _scorecards(source: DataSource, report_prompts: list[str]) -> list[Idea]:
    """KPI scorecards: the period-over-period numbers people track, for each table with a date
    and an amount. Skipped when a scorecard on that table has been built already."""
    out = []
    for table in list(source.tables)[:8]:
        columns = table_columns(source, table)
        number = _pick(columns, _NUMBER_TYPES, _MEASURE_WORDS)
        date = _pick(columns, _DATE_TYPES, ("date", "created", "posted", "order", "invoice"))
        if not (number and date):
            continue
        group = _pick(columns, ("char", "text", "string", "enum"), _GROUP_WORDS, avoid=_FREE_TEXT)
        thing, num, bare = _label(table.rpartition(".")[2]), _label(number), table.rpartition(".")[2]
        if any("scorecard" in p.lower() and thing in p.lower() for p in report_prompts):
            continue
        kpis = (f"total {num} this month", f"total {num} last month", "the change from last month",
                f"total {num} year to date", f"how many {thing} this month")
        charts = [f"monthly {num} this year against last year"]
        if group:
            charts.append(f"total {num} by {_label(group)}, this month against last month")
            charts.append(f"the top 5 {_label(group)} by {num} year to date")
        where = f" on the {source.name} connection" if source.name else ""
        prompt = (f"Build a {thing} KPI scorecard{where}. Use [{bare}], dated by {_label(date)}. "
                  f"KPI cards for {_and_list(kpis)} (as a percentage). Then charts for {_and_list(charts)}.")
        out.append(Idea(id=f"kpi-{thing.replace(' ', '-')}", title=f"{thing.capitalize()} KPI scorecard",
                        why="Common KPIs: this month against last, year to date and the trend",
                        reason="kpi", prompt=prompt, charts=len(kpis) + len(charts), subject=thing,
                        kpis=kpis[:4]))
    return out


def recommend(db: Session, user: User, source: DataSource, limit: int = MAX_IDEAS) -> list[dict]:
    """Reports worth building on this connection, best first.

    Never raises for want of history or tables: a connection nobody has touched still gets the
    subjects it can carry, and one with nothing recognisable on it gets an empty list, which the
    page shows as its own plain suggestions rather than as an error.
    """
    # An OpenPages connection gets the ten reference dashboards and nothing else. They are written
    # against the published object model - the real parent/child pairs of each namespace - which is
    # knowledge this code does not have and cannot derive from the connection: the connection says
    # which object types are shared, not which of them may legally be joined. Offering a guess
    # beside them would only invite someone to pick the guess.
    if source.is_openpages:
        # The box gets the plain-English wording and the builder gets the technical one. The
        # person reading the box is deciding whether this is the report they want, not auditing
        # its SQL - and a box full of [OPSS-Ctl:Operating Effectiveness] is something nobody
        # dares edit, which defeats the point of filling the box rather than building at once.
        # Ahead of them, the four subjects people ask for in one line. These carry no second
        # wording: the sentence on the card IS the request, and openpages_detail_reports expands
        # it when it is sent. That is what lets someone change "3 months" to "6" in the box and
        # still get the written-out report, which a stored technical wording could not do.
        detail = [asdict(Idea(id=r.id, title=f"{r.title} - detail report", why=r.why,
                              reason="curated", prompt=r.ask, charts=WIDGET_COUNT,
                              subject="Written out in full"))
                  for r in DETAIL_REPORTS]
        return [*[asdict(Idea(id=c.id, title=c.title, why=c.why, reason="curated", prompt=c.plain,
                              build_prompt=c.prompt, charts=c.charts, subject=c.namespace,
                              data_model=c.model_key))
                  for c in FROM_TEMPLATES],
                *detail,
                *[asdict(Idea(id=c.id, title=c.title, why=c.why, reason="curated", prompt=c.plain,
                              build_prompt=c.prompt, charts=c.charts, subject=c.namespace,
                              data_model=c.model_key))
                  for c in CURATED]]

    prompts = past_prompts(db, user, source)
    report_prompts = [r.prompt for r in db.scalars(
        select(Report).where(Report.owner_id == user.id).order_by(Report.updated_at.desc())
        .limit(PAST_PROMPTS)).all() if (r.config or {}).get("source_id") == source.id
        and len(r.prompt or "") >= MIN_PAST_LENGTH]

    ideas = _from_history(report_prompts)
    scorecards = [] if source.is_openpages else _scorecards(source, report_prompts)[:1]
    room = limit - len(scorecards)

    scored = []
    for recipe, types in _recipes_for(source):
        score, hits = _affinity(prompts, recipe)
        built = _already_built(report_prompts, recipe)
        # Asked about but never built is the single most useful thing to suggest; already built
        # drops down the list without disappearing, since people do rebuild reports.
        rank = score * 2 - (3 if built else 0)
        scored.append((rank, hits, built, recipe, types))
    scored.sort(key=lambda s: -s[0])

    for rank, hits, built, recipe, types in scored:
        if len(ideas) >= room:
            break
        if hits and not built:
            why = f"You asked about {recipe.subject}s {hits} times but have no report on them" \
                if hits > 1 else f"You asked about {recipe.subject}s recently"
        elif hits and built:
            why = f"You asked about {recipe.subject}s {hits} times" if hits > 1 else \
                f"You have a report on {recipe.subject}s already"
        else:
            why = f"{_and_list([f'[{t}]' for t in types])} is shared on this connection"
        ideas.append(Idea(id=f"subject-{recipe.subject.replace(' ', '-')}", title=recipe.title,
                          why=why, reason="subject", prompt=_request(recipe, source, types),
                          charts=len(recipe.kpis) + len(recipe.charts), subject=recipe.subject,
                          kpis=tuple(recipe.kpis[:4])))

    # The common KPIs - this month against last, year to date, the trend - come right after the
    # subjects, so a connection with dated numbers always offers a scorecard.
    ideas.extend(scorecards)

    # One idea that crosses subjects, because the question people ask of a whole connection is
    # rarely about one object type. Only offered when there is enough on the connection for it to
    # mean something, and only in the space left over.
    covered = [r for r, _ in _recipes_for(source)]
    if len(covered) >= 3 and len(ideas) < limit:
        names = _and_list([r.subject + "s" for r in covered[:6]])
        ideas.append(Idea(
            id="breadth-overview", title=f"{source.name} overview", reason="breadth",
            why=f"One page across {len(covered)} subjects this connection holds",
            charts=len(covered) * 4,
            prompt=(f"Build an overview of the {source.name} connection with a tab for each subject: "
                    f"{names}. On every tab, start with KPI cards for the headline counts, then "
                    f"charts of that subject broken down by its status and its main categories. "
                    f"Count records, skip empty values, largest first, and show the figures as well "
                    f"as the colours.")))
    return [asdict(i) for i in ideas[:limit]]
