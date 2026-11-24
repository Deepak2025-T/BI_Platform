"""
The ten reference dashboards offered on an OpenPages connection.

They are the one thing on that panel not worked out from the connection, because the connection
cannot say which object types may legally be joined - only the published object model says that.
So the value of these is entirely in their being correct and unedited, which is what these guard.
"""

from app.openpages_prompts import CURATED
from app.schemas import MAX_WIDGETS, PROMPT_MAX


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
