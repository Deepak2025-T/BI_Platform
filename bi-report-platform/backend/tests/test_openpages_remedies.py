"""
What to do about the refusals the OpenPages Query Service sends back.

Its messages say what is wrong but not what would work. A model given only "the query failed to be
transformed into SQL" sends the same shape back with the brackets moved, three times, and the
person is left with an error code. These turn each refusal into a next step - one for the model,
one for the person.
"""

import pytest

from app.ai.assistant import _DIALECT_TIPS
from app.connections.openpages import SQL_GUIDE, advice, remedy

# The refusals as OpenPages actually writes them, taken from real failures.
ANCESTOR = ("OpenPages returned HTTP 400: Bad Request - OP-60008: Invalid query. Using ANCESTOR() "
            "predicate in a join requires adding at least one scoping filter to the ANCESTOR type "
            "in the WHERE clause. Ancestor Type is [SOXProcess] [W6TPM981SZW1]")
NO_SQL = ("OpenPages returned HTTP 400: Bad Request - null OP-60002: The query failed to be "
          "transformed into SQL [W6TPMBXNMB7T]")


@pytest.mark.parametrize("error", [ANCESTOR, NO_SQL])
def test_a_refusal_tells_the_model_what_to_write_instead(error):
    """Not what went wrong - the error already says that - but what would work."""
    fix = remedy(error)
    assert fix
    assert fix != error


def test_the_ancestor_refusal_points_at_the_join_that_does_work():
    fix = remedy(ANCESTOR)
    assert "PARENT" in fix and "Location" in fix


def test_the_transform_refusal_names_its_usual_cause():
    """Counting across a join is the one people hit, and it can never be written."""
    assert "COUNT" in remedy(NO_SQL) and "JOIN" in remedy(NO_SQL)


@pytest.mark.parametrize("error", [ANCESTOR, NO_SQL])
def test_the_person_is_told_what_to_ask_instead(error):
    """"Use a PARENT join" is no use to someone typing a question, so they get their own wording."""
    said = advice(error)
    assert said and "JOIN" not in said and "SELECT" not in said
    assert said.endswith(".")
    assert said != remedy(error)


def test_an_unknown_refusal_is_left_to_speak_for_itself():
    """Inventing advice for a code nobody has seen would send someone the wrong way."""
    unknown = "OpenPages returned HTTP 400: Bad Request - OP-61234: Something new [ABC]"
    assert remedy(unknown) == ""
    assert advice(unknown) == ""


def test_nothing_is_matched_in_an_empty_error():
    assert remedy("") == "" and advice("") == ""
    assert remedy(None) == "" and advice(None) == ""


# ---------------------------------------------------------------- what the model is told up front

def test_the_guide_says_ancestor_cannot_group_by_a_parent():
    """The first attempt is worth more than a corrected third one."""
    assert "scoping filter" in SQL_GUIDE
    assert "[Location]" in SQL_GUIDE


def test_the_guide_rules_out_counting_across_a_join():
    assert "COUNT and JOIN can never appear in the same query" in SQL_GUIDE


def test_the_short_dialect_line_carries_the_same_two_rules():
    """It is the line that reaches the model even when the schema is trimmed for context."""
    tip = _DIALECT_TIPS["openpages"]
    assert "COUNT never in the same query as a JOIN" in tip
    assert "one hierarchy join at most" in tip


# ---------------------------------------------------------------- the retry loop

def _openpages_source():
    from app.datasources import DataSource
    return DataSource(id=1, name="OP", db_type="openpages", tables=["openpages.SOXControl"], version="v")


def _failing_run(monkeypatch, error: str) -> list[str]:
    """Makes every query fail with `error`, and returns the list the prompts are collected into."""
    from app.ai import assistant
    from app.datasources import QueryFailed

    prompts: list[str] = []

    def answer(spec, system, user, schema):
        prompts.append(user)
        return {"action": "query", "reply": "", "title": "t",
                "sql": "SELECT [SOXProcess].[Name], COUNT([SOXControl].[Resource ID]) FROM [SOXProcess] "
                       "JOIN [SOXControl] ON ANCESTOR([SOXProcess])",
                "chart": {"type": "bar", "x": "Name", "y": ["Count_Resource ID"]}}

    def fail(source, sql, params=None, **kw):
        raise QueryFailed(error)

    monkeypatch.setattr(assistant, "complete_json", answer)
    monkeypatch.setattr(assistant, "run_sql", fail)
    return prompts


def test_a_failed_try_tells_the_next_one_what_to_write_instead(monkeypatch):
    """Three tries at the same broken shape is what the screenshot showed. The error goes back to
    the model either way; what is new is the fix going back with it."""
    from app.ai import assistant

    prompts = _failing_run(monkeypatch, ANCESTOR)
    with pytest.raises(assistant.AssistantError):
        assistant._query_with_retries(assistant.ModelSpec(provider="ollama", model="x"),
                                      _openpages_source(), "system", "Controls by process")

    assert len(prompts) == assistant.MAX_ATTEMPTS
    # The first try has nothing to go on; every one after it carries the remedy.
    assert "How to fix it:" not in prompts[0]
    for retry in prompts[1:]:
        assert "How to fix it:" in retry
        assert "PARENT" in retry


def test_what_is_left_on_screen_says_what_to_ask_instead(monkeypatch):
    from app.ai import assistant

    _failing_run(monkeypatch, NO_SQL)
    with pytest.raises(assistant.AssistantError) as raised:
        assistant._query_with_retries(assistant.ModelSpec(provider="ollama", model="x"),
                                      _openpages_source(), "system", "How many controls per process")

    message = str(raised.value)
    assert advice(NO_SQL) in message
    # The raw error is still there, after the part someone can act on.
    assert message.index(advice(NO_SQL)) < message.index("Last error:")


def test_a_plain_database_is_left_alone(monkeypatch):
    """None of this is about SQL databases, whose errors say what is wrong perfectly well."""
    from app.ai import assistant
    from app.datasources import DataSource

    prompts = _failing_run(monkeypatch, "syntax error at or near \"FROM\"")
    source = DataSource(id=None, name="s", db_type="postgresql", tables=["public.orders"], version="v")
    with pytest.raises(assistant.AssistantError) as raised:
        assistant._query_with_retries(assistant.ModelSpec(provider="ollama", model="x"),
                                      source, "system", "orders")

    assert all("How to fix it:" not in p for p in prompts)
    assert str(raised.value).endswith('syntax error at or near "FROM"')
