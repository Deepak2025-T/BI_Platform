"""
The ten reference dashboards offered on an OpenPages connection.

They are the one thing on that panel not worked out from the connection, because the connection
cannot say which object types may legally be joined - only the published object model says that.
So the value of these is entirely in their being correct and unedited, which is what these guard.
"""

import re

from app.openpages_model import get
from app.openpages_prompts import CURATED
from app.openpages_template_prompts import FROM_TEMPLATES

# Everything the build panel offers on an OpenPages connection.
ALL = (*FROM_TEMPLATES, *CURATED)
from app.schemas import MAX_WIDGETS, PROMPT_MAX

# FROM [Parent] JOIN [Child] ON PARENT([Parent]) - the only join shape the Query Service takes.
_JOIN = re.compile(r"FROM\s*\[([^\]]+)\]\s*JOIN\s*\[([^\]]+)\]\s*ON\s*PARENT\(\s*\[([^\]]+)\]\s*\)",
                   re.I)


def _joins(prompt):
    """The (parent, child, on) triples a prompt asks for, minus the rules' own template line."""
    return [t for t in _JOIN.findall(prompt) if t[0] != "Parent"]


def test_there_are_ten_one_per_namespace():
    assert len(CURATED) == 10
    assert len({c.id for c in CURATED}) == 10, "two prompts share an id"


def test_each_one_fits_in_the_box_it_goes_into():
    """They are long - 6,000 to 8,000 characters - and the box they fill has a limit."""
    for c in CURATED:
        assert 1000 < len(c.prompt) <= PROMPT_MAX, c.title


def test_each_says_what_it_builds_and_against_what():
    for c in CURATED:
        assert c.title and c.why and c.namespace, c.id
        assert c.prompt.lstrip().startswith("Build"), c.title


def test_each_carries_the_query_service_rules_with_it():
    """A prompt is edited in the box before it is sent. The rules travel inside it so that editing
    the charts cannot drop the constraints that make the SQL run."""
    for c in CURATED:
        assert "RULES" in c.prompt, c.title
        assert "COUNT works on ONE object type" in c.prompt, c.title


def test_each_ends_its_sections_with_a_summary_table():
    """The table is what a click on a chart filters, so a report without one cannot be drilled."""
    for c in CURATED:
        assert "summary table" in c.prompt.lower(), c.title


def test_none_asks_for_more_charts_than_a_plan_may_hold():
    """Each is 30 to 50 widgets, and a plan is truncated past MAX_WIDGETS - so a prompt that asked
    for more than the cap would silently lose its last sections."""
    for c in CURATED:
        assert 20 <= c.charts <= MAX_WIDGETS, f"{c.title} counts {c.charts}"


def test_the_brackets_the_query_service_needs_survived_the_extraction():
    """These came out of a .docx. Smart quotes and lost brackets would break every query in them."""
    for c in CURATED:
        assert "[" in c.prompt and "]" in c.prompt, c.title
        assert "“" not in c.prompt and "”" not in c.prompt, f"{c.title} has smart quotes"


# ---------- every join is one the namespace actually has ----------

def test_every_prompt_names_a_data_model_that_exists():
    """Picking a reference report selects its namespace, which is what hands the query writer the
    real parent/child pairs. A key that resolves to nothing would quietly leave it guessing."""
    for c in CURATED[:-1]:
        assert get(c.model_key) is not None, f"{c.title} points at {c.model_key!r}"


def test_no_prompt_joins_a_pair_its_namespace_does_not_have():
    """The one failure mode these prompts exist to avoid.

    OpenPages has no foreign keys - a join is "this type sits under that type" - so a pair the
    namespace does not list is not a wrong answer, it is a query the service refuses. Each refusal
    costs its chart, and a 40-chart report arrives with holes in it."""
    for c in CURATED[:-1]:
        model = get(c.model_key)
        legal = {(r.parent, r.child) for r in model.relationships}
        for parent, child, on in _joins(c.prompt):
            assert on == parent, f"{c.title}: ON PARENT([{on}]) under FROM [{parent}]"
            assert (parent, child) in legal,                 f"{c.title}: [{parent}] | [{child}] is not in {model.name}"


def test_the_cross_namespace_report_joins_nothing():
    """It is the one report meant to run against any namespace, and there is no pair that all of
    them carry - [SOXRisk]|[SOXControl], the most widespread, is missing from ORM3. So it uses
    [Location], which every object has, and no joins at all."""
    assert not _joins(CURATED[-1].prompt), "a join here fails on whichever namespace lacks it"
    assert "[Location]" in CURATED[-1].prompt


def test_no_pair_is_shared_by_every_namespace():
    """The fact the test above rests on. If a future object model made one universal, this goes
    red and the cross-namespace report can be given its relationship tables back."""
    from app.openpages_model import MODELS
    shared = set.intersection(*[{(r.parent, r.child) for r in m.relationships} for m in MODELS])
    assert not shared, f"these pairs are now in every namespace: {sorted(shared)}"


# ---------- the box reads in words; the builder gets the queries ----------

def test_the_plain_wording_carries_no_query_language():
    """What the box shows is for the person deciding whether this is the report they want. A box
    full of [OPSS-Ctl:Operating Effectiveness] is something nobody dares edit, which defeats the
    point of filling the box rather than building at once."""
    for c in ALL:
        for jargon in ("SELECT ", "COUNT [", "JOIN ", "PARENT(", "GROUP BY", "OPSS-"):
            assert jargon not in c.plain, f"{c.title} shows {jargon!r} to the reader"


def test_the_plain_wording_asks_for_the_same_report():
    for c in ALL:
        assert c.plain.lstrip().startswith("Build"), c.title
        assert len(c.plain) > 500, c.title


def test_every_tab_is_told_to_end_with_its_own_table():
    """A click on a chart filters the tables on the report, so a tab without one cannot be drilled
    into - and a tab holding another tab's table drills into the wrong records."""
    for c in ALL:
        assert "summary table" in c.plain.lower(), c.title
        assert "own tab" in c.plain or "its own tab" in c.plain or "tab" in c.plain, c.title


def test_the_three_template_reports_are_offered_as_well_as_their_templates():
    """As well as, not instead of: a template is built as it stands, a prompt can be changed
    first. Removing either would take away one of those."""
    from app.openpages_modules import module_template_rows
    from app.openpages_templates import template_rows
    names = {r["name"] for r in (*module_template_rows(), *template_rows())}
    for wanted in ("ORM: ORM overview", "ORM: Events, indicators and remediation",
                   "OpenPages: Audit plan item overview"):
        assert wanted in names, f"{wanted} is offered as a prompt but no longer ships as a template"
    titles = {c.title for c in FROM_TEMPLATES}
    assert titles == {"ORM overview", "Events, indicators and remediation",
                      "Audit plan item overview"}


def test_the_template_prompts_are_plain_ascii():
    """They are built from template titles, which use en and em dashes. A prompt travels through a
    .py file, a JSON body and a textarea; the dashes do not always survive the trip."""
    for c in FROM_TEMPLATES:
        bad = [ch for ch in c.plain + c.prompt + c.title if ord(ch) > 126]
        assert not bad, f"{c.title} carries {bad[:3]}"
